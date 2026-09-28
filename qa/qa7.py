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
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile, base64, zlib, struct
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         pin_popup_visibility as _qa_pin)
_qa_pin(NO)
fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app = NO.NoteOrganizer(); app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.ask_yes_no = lambda *a, **k: True
app.geometry('1100x850'); app.update()

def find_widget(w, cls, text_contains=None):
    for c in w.winfo_children():
        if isinstance(c, cls):
            if text_contains is None or text_contains in str(c.cget('text')):
                return c
        r = find_widget(c, cls, text_contains)
        if r:
            return r
    return None

def find_all_labels(w, acc=None):
    if acc is None: acc = []
    for c in w.winfo_children():
        if isinstance(c, tk.Label):
            acc.append(str(c.cget('text')))
        find_all_labels(c, acc)
    return acc

os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)

# ============================================================
# 1. ATTACHMENT CLEANUP ON PERMANENT DELETE (the other 3 paths)
# ============================================================

# 1a. delete_forever (single trash entry)
fname_a = '20260101000000000001_a.txt'
path_a = os.path.join(NO.ATTACHMENTS_DIR, fname_a)
with open(path_a, 'w') as f: f.write('x')
entry_a = {'id': 901, 'title': 'DelForever', 'attachments': [{'filename': 'a.txt', 'stored_as': fname_a}],
           'deleted_at': '2026-01-01 00:00:00'}
app.trash = [entry_a]
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
del_btn = find_widget(app.settings_trash_panel, tk.Button, 'Delete')
del_btn.invoke()
app.update()
check('delete_forever removes the attachment file from disk', not os.path.isfile(path_a))
check('delete_forever removes the trash entry', len(app.trash) == 0)

# 1b. empty_trash (all entries)
fnames_b = []
for i in range(3):
    fn = f'2026010100000000000{i}_b{i}.txt'
    with open(os.path.join(NO.ATTACHMENTS_DIR, fn), 'w') as f: f.write('x')
    fnames_b.append(fn)
app.trash = [{'id': 910 + i, 'title': f'N{i}', 'attachments': [{'filename': f'b{i}.txt', 'stored_as': fn}],
              'deleted_at': '2026-01-01 00:00:00'} for i, fn in enumerate(fnames_b)]
app.hide_settings_page(); app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
empty_btn = find_widget(app.settings_trash_panel, tk.Button, 'Empty trash')
empty_btn.invoke()
app.update()
check('empty_trash removes ALL attachment files',
      all(not os.path.isfile(os.path.join(NO.ATTACHMENTS_DIR, fn)) for fn in fnames_b))
check('empty_trash clears the trash list', len(app.trash) == 0)

# 1c. purge_expired_trash (automatic, on load)
fname_c = '20260101000000000099_old.txt'
path_c = os.path.join(NO.ATTACHMENTS_DIR, fname_c)
with open(path_c, 'w') as f: f.write('x')
old_entry = {'id': 920, 'title': 'VeryOld', 'attachments': [{'filename': 'old.txt', 'stored_as': fname_c}],
             'deleted_at': '2020-01-01 00:00:00'}
kept, purged_count = NO.purge_expired_trash([old_entry])
check('purge_expired_trash removes the attachment file', not os.path.isfile(path_c))
check('purge_expired_trash reports 1 purged', purged_count == 1 and len(kept) == 0)

app.hide_settings_page(); app.update()

# ============================================================
# 2. DELETE NOTE FROM CALENDAR
# ============================================================
app.notes = [{'id': 1, 'title': 'CalDelete', 'body': 'x', 'category': 'General', 'date': '2026-07-15',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar()
app.open_day_popup('2026-07-15')
app.update()

# The day list carries no delete button of its own. It used to carry the
# only per-row note delete in the app -- a lone grey glyph with no word,
# packed hard against the scrollbar -- while the sidebar's note cards,
# which are the same kind of thing, have always offered their actions
# through the right-click menu and no button at all.
check('the day list carries no bare delete button of its own',
      find_widget(app.day_panel, tk.Button, '🗑') is None)

# Deleting from the day list still works, through the actions menu that
# was already bound to every row -- and that menu carries six other
# things besides, which is why it was never "the delete system".
_cal_posted = []
_cal_real_popup = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _cal_posted.append(_m)
try:
    app.show_note_context_menu(
        type('E', (), {'x_root': 0, 'y_root': 0})(),
        app.notes[0], occurrence_date='2026-07-15')
    _cal_labels = []
    if _cal_posted:
        for _i in range(_cal_posted[-1].index('end') + 1):
            try:
                _cal_labels.append(str(_cal_posted[-1].entrycget(_i, 'label')))
            except tk.TclError:
                _cal_labels.append('---')
    check('a day-list row offers the actions menu (%d entries)' % len(_cal_labels),
          any('Delete' in _l for _l in _cal_labels))
    check('...and it is the whole menu, not a delete on its own',
          any('Open' in _l for _l in _cal_labels)
          and any('Export' in _l for _l in _cal_labels))

    # ---- AND IT CAN CHANGE A CATEGORY NOW (C-17) ----
    # The selection bar could recategorise but not duplicate; this menu
    # could duplicate but not recategorise. Neither gap was a rule anyone
    # could learn, and the bulk popup was the only route that did not mean
    # opening the note first.
    check('the menu offers to move the note to a category',
          any('Move to category' in _l for _l in _cal_labels))
    _c17_idx = next((_i for _i, _l in enumerate(_cal_labels)
                     if 'Move to category' in _l), None)
    if _c17_idx is not None:
        _c17_sub = _cal_posted[-1].entrycget(_c17_idx, 'menu')
        _c17_menu = app.nametowidget(_c17_sub)
        # index('end') is None on an EMPTY menu, and range(None + 1) raises
        # -- so a submenu that listed nothing crashed the script instead of
        # failing this check, and the runner's summary reports a crash as a
        # failure either way. Found by a mutant that emptied the loop.
        _c17_end = _c17_menu.index('end')
        _c17_labels = ([] if _c17_end is None else
                       [str(_c17_menu.entrycget(_i, 'label'))
                        for _i in range(_c17_end + 1)])
        check(f'the submenu lists every category ({len(_c17_labels)})',
              len(_c17_labels) == len(NO.CATEGORY_COLORS))
        # A tick beside the one it is in now, so the menu answers "which is
        # this?" as well as offering to change it.
        _c17_note = app.notes[0]
        check(f'and marks the one it is in now '
              f'({_c17_note.get("category")!r})',
              any(_l.startswith('✓') and _c17_note.get('category') in _l
                  for _l in _c17_labels))
        _c17_target = next(
            (_i for _i, _l in enumerate(_c17_labels)
             if not _l.startswith('✓')), None)
        if _c17_target is not None:
            _c17_want = _c17_labels[_c17_target].strip()
            _c17_id = _c17_note['id']
            # THE SEAM the bulk route learned the hard way, and it only
            # exists while the EDITOR IS HOLDING THIS NOTE with its own
            # category dropdown on the old value -- the editor's next save
            # writes that dropdown back and undoes the change with nothing
            # on screen to say so. Without this line the reconciliation is a
            # no-op and removing it changes nothing a check can see: a
            # mutant that deleted it survived until the note was loaded here.
            app.load_note(app.find_note(_c17_id))
            app.update()
            check(f'fixture: the editor is holding the note, on its old '
                  f'category ({app.category_var.get()!r})',
                  app.selected_note_id == _c17_id
                  and app.category_var.get() == _c17_note.get('category'))
            _c17_menu.invoke(_c17_target)
            app.update()
            check(f'picking one moves the note to it ({_c17_want!r})',
                  app.find_note(_c17_id).get('category') == _c17_want)
            app._flush_autosave()
            app.update()
            check('and the editor does not undo it on its next save',
                  app.find_note(_c17_id).get('category') == _c17_want)
    if _cal_posted and any('Delete' in _l for _l in _cal_labels):
        _cal_posted[-1].invoke(
            [_i for _i, _l in enumerate(_cal_labels) if 'Delete' in _l][0])
        app.update()
finally:
    NO.tk.Menu.tk_popup = _cal_real_popup
check('calendar day-list delete removes the note', len(app.notes) == 0)

# detail view + Cancel doesn't bounce
app.notes = [{'id': 2, 'title': 'CalDetailDelete', 'body': 'x', 'category': 'General', 'date': '2026-07-15',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}]
app.save_notes()
app.render_calendar()
app.open_day_popup('2026-07-15')
app.update()
app.show_day_note(app.notes[0], '2026-07-15')
app.update()
del_btn_detail = find_widget(app.day_panel, tk.Button, '🗑 Delete')
check('calendar detail-view delete button exists', del_btn_detail is not None)

app.ask_yes_no = lambda *a, **k: False  # Cancel
del_btn_detail.invoke()
app.update()
check('Cancel on calendar delete leaves the note intact', len(app.notes) == 1)
check('Cancel does NOT bounce back to the day list', app._day_panel_mode == 'note')

app.ask_yes_no = lambda *a, **k: True  # Confirm
del_btn_detail2 = find_widget(app.day_panel, tk.Button, '🗑 Delete')
del_btn_detail2.invoke()
app.update()
check('Confirm on calendar delete removes the note', len(app.notes) == 0)
check('panel falls back to list after a real delete', app._day_panel_mode == 'list')

# recurring note asks for scope
app.notes = [{'id': 3, 'title': 'RecurringCal', 'body': 'x', 'category': 'General', 'date': '2026-07-01',
              'recurrence': {'freq': 'daily'}, 'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}}]
app.save_notes()
app.render_calendar()
app.open_day_popup('2026-07-08')
app.update()
scope_asked = {'called': False}
app.ask_occurrence_scope = lambda *a, **k: (scope_asked.__setitem__('called', True), 'occurrence')[1]
app.ask_yes_no = lambda *a, **k: True
_cal_posted2 = []
_cal_real_popup2 = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _cal_posted2.append(_m)
try:
    app.show_note_context_menu(
        type('E', (), {'x_root': 0, 'y_root': 0})(),
        app.notes[0], occurrence_date='2026-07-08')
    _lbl2 = []
    if _cal_posted2:
        for _i in range(_cal_posted2[-1].index('end') + 1):
            try:
                _lbl2.append(str(_cal_posted2[-1].entrycget(_i, 'label')))
            except tk.TclError:
                _lbl2.append('---')
    # A repeating note's menu says so, which is the reason the panel had
    # to be given the menu at all: it is opened ON a day, so the menu
    # must offer that day rather than act on the series behind it.
    check('a repeating note offers its per-day actions in the menu',
          any('only this occurrence' in _l for _l in _lbl2))
    if _cal_posted2 and any('Delete' in _l for _l in _lbl2):
        _cal_posted2[-1].invoke(
            [_i for _i, _l in enumerate(_lbl2) if 'Delete' in _l][0])
        app.update()
finally:
    NO.tk.Menu.tk_popup = _cal_real_popup2
check('recurring note delete via calendar asks for scope', scope_asked['called'])
check('only that occurrence removed, series intact', '2026-07-08' in app.notes[0].get('exceptions', []))

app.close_day_panel(); app.update()
# Un-shadow the real scope prompt: leaving this section's always-'occurrence'
# mock in place once leaked it into every later section (a save/restore
# further down dutifully "restored" this mock, believing it was the real
# method). Deleting the instance attribute brings the class method back.
del app.ask_occurrence_scope

# ---- CALENDAR PREVIEW IS A QUICK LOOK: text + chips, not the editor ----
# A note with a table drew raw pipe soup in the day preview, and its
# comments were dumped inline. The preview now shows plain text only and,
# like the note-list cards, just SAYS what else the note carries.
from noteorganizer.core import tables as _core_tables_q7
app.notes = [{'id': 9, 'title': 'PreviewNote', 'category': 'General',
              'date': '2026-07-20', 'updated': '2026-01-01 00:00',
              'created': '2026-01-01 00:00', 'attachments': [],
              'body': 'Text sus\n| A | B |\n| --- | --- |\n| 1 | 2 |\nText jos',
              'comments': 'a comment that must not be shown',
              'checklist': [{'text': 'a', 'done': True},
                            {'text': 'b', 'done': False}]}]
app.save_notes()
app.render_calendar()
app.open_day_popup('2026-07-20')
app.update()
app.show_day_note(app.notes[0], '2026-07-20')
app.update()
_pv_texts = []
def _walk_q7(w):
    _pv_texts.append(w)
    for c in w.winfo_children():
        _walk_q7(c)
_walk_q7(app.day_panel)
_pv_text = next((w.get('1.0', 'end-1c') for w in _pv_texts
                 if isinstance(w, tk.Text)), '')
_pv_chip = next((w.cget('text') for w in _pv_texts
                 if isinstance(w, tk.Label)
                 and ('▦' in str(w.cget('text')) or '💬' in str(w.cget('text')))),
                '')
check('calendar preview strips the table to plain text',
      '|' not in _pv_text and 'Text sus' in _pv_text and 'Text jos' in _pv_text)
check('calendar preview does not dump the comments inline',
      'a comment that must not' not in _pv_text)
check('calendar preview flags table + checklist + comments as chips',
      '▦' in _pv_chip and '1/2' in _pv_chip and '💬' in _pv_chip)
app.close_day_panel(); app.update()

# ---- NOTHING HOVERS OVER AN OPEN MENU ----
# A right-click menu keeps the app's event loop running -- tk_popup
# blocks the caller but not the loop -- so drifting the mouse a few
# pixels onto a neighbouring cell still fired the hover preview, which
# then drew itself OVER the menu being read. Field-reported with a
# screenshot.
app.notes = [{'id': 60, 'title': 'HoverMe', 'body': 'some words',
              'category': 'General', 'date': '2026-07-20',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
app.render_calendar()
app.update()
app.hide_day_tooltip()
app._context_menu_open = False
app.show_day_summary_tooltip('2026-07-20')
app.update()
check('hovering a day normally does show its preview',
      getattr(app, '_day_tooltip', None) is not None)
app.hide_day_tooltip()
app._context_menu_open = True
app.show_day_summary_tooltip('2026-07-20')
app.update()
check('...but not while a right-click menu is open',
      getattr(app, '_day_tooltip', None) is None)
app.show_note_hover_preview(app.notes[0], '2026-07-20')
app.update()
check('...and the single-note preview stays away too',
      getattr(app, '_day_tooltip', None) is None)
app._context_menu_open = False

# The flag is only worth anything if it is actually up WHILE the menu is
# posted. The stub stands exactly where the real, blocking tk_popup
# stands, so what it sees is what the menu's whole life sees.
_flag_seen = []
_flag_real = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _flag_seen.append(
    getattr(app, '_context_menu_open', False))
try:
    app.show_note_context_menu(
        type('E', (), {'x_root': 0, 'y_root': 0})(), app.notes[0])
finally:
    NO.tk.Menu.tk_popup = _flag_real
check('the menu raises the flag for as long as it is posted',
      _flag_seen == [True])
check('...and lowers it once the menu is gone',
      getattr(app, '_context_menu_open', False) is False)

# ---- A PREVIEW SHOWS WORDS, NOT PUNCTUATION ----
# Both calendar previews used to put table rows on screen as raw pipes.
# The panel filtered them with is_table_row(), which is strict because it
# decides what the EDITOR treats as a row -- so a line typed past its
# last cell was neither counted nor removed, and the panel announced
# five tables and drew a sixth as bars. The hover preview did not filter
# at all. Reported as "I only see vertical lines".
# Two runs on purpose, and the second one is a line the strict test
# refuses: it starts with a pipe and was typed past its last cell. Under
# the old rule that run was neither counted nor stripped -- so this
# fixture asks for "2 tables" where the old code would have said one and
# then drawn the other.
_ragged = '|   |   |   | [x] |   |   |   |fig2efwfwe'
app.notes = [{'id': 61, 'title': 'HasTables',
              'body': 'real words here\n| a | b |\n| c | d |\n\n' + _ragged,
              'category': 'General', 'date': '2026-07-21',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
app.render_calendar()
app.update()


def _all_text(widget):
    """Everything readable in there -- labels AND text widgets.

    The panel puts the note's body in a disabled tk.Text, so a sweep
    that only asks cget('text') sees the chips and misses the very
    thing under test.
    """
    out = []

    def walk(w):
        try:
            out.append(str(w.cget('text')))
        except tk.TclError:
            pass
        if isinstance(w, tk.Text):
            try:
                out.append(w.get('1.0', 'end-1c'))
            except tk.TclError:
                pass
        for k in w.winfo_children():
            walk(k)
    walk(widget)
    return ' '.join(out)


app.hide_day_tooltip()
app.show_note_hover_preview(app.notes[0], '2026-07-21')
app.update()
_hov = _all_text(app._day_tooltip) if getattr(app, '_day_tooltip', None) else ''
check('the hover preview shows the note\'s words', 'real words here' in _hov)
check('...and not one vertical bar of its tables', '|' not in _hov)
check('...but does say a table is there', 'table' in _hov)
app.hide_day_tooltip()

app.open_day_popup('2026-07-21')
app.show_day_note(app.notes[0], '2026-07-21')
app.update()
_pan = _all_text(app.day_panel)
check('the day panel shows the words too', 'real words here' in _pan)
check('...with no bars left over from a row it could not parse',
      '|' not in _pan)
check('...and counts every run of them, including that one',
      '2 tables' in _pan)
app.close_day_panel(); app.update()

# ---- THE PREVIEW ANSWERS TO RIGHT-CLICK LIKE EVERY OTHER NOTE SURFACE ----
# It was the only one in the app that did not. What it lacked was not a
# second way to delete -- it was Open/Edit, Pin, Export as file, and, for
# a repeating note, editing just this day, editing the whole series, and
# resetting this day back to the series content. Arriving here from the
# History register was arriving somewhere with fewer actions than the
# list you could have reached the same note from.
app.notes = [{'id': 77, 'title': 'PreviewMenu', 'body': 'x',
              'category': 'General', 'date': '2026-07-01',
              'recurrence': {'freq': 'daily'}, 'updated': '2026-01-01 00:00',
              'created': '2026-01-01 00:00', 'checklist': [],
              'attachments': [], 'exceptions': [], 'overrides': {}}]
app.save_notes()
app.render_calendar()
app.open_day_popup('2026-07-09')
app.show_day_note(app.notes[0], '2026-07-09')
app.update()
_pm_posted = []
_pm_real = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _pm_posted.append(_m)
try:
    _qa_fire(app.day_panel, '<Button-3>')
    app.update()
    check('right-clicking the preview posts a menu', bool(_pm_posted))
    _pm_labels = []
    if _pm_posted:
        for _i in range(_pm_posted[-1].index('end') + 1):
            try:
                _pm_labels.append(str(_pm_posted[-1].entrycget(_i, 'label')))
            except tk.TclError:
                _pm_labels.append('---')
    # Not "Open / Edit": that entry is deliberately left out for a
    # repeating note shown on a day, because the two explicit scope
    # entries below replace it (field-reported, and commented where it
    # is decided). What must be there is everything unconditional, so
    # the menu is the whole menu rather than a delete wearing a hat.
    check('...the same actions the day list offers (%s)'
          % ' | '.join(_l.strip() for _l in _pm_labels),
          any('Pin' in _l for _l in _pm_labels)
          and any('Export' in _l for _l in _pm_labels)
          and any('Duplicate' in _l for _l in _pm_labels)
          and any('Delete' in _l for _l in _pm_labels))
    # The day it was opened on, not the series behind it. Without the
    # occurrence date the menu would quietly offer to edit every
    # occurrence while the panel shows one.
    check('...and it knows which DAY the preview is showing',
          any('only this occurrence' in _l for _l in _pm_labels))
finally:
    NO.tk.Menu.tk_popup = _pm_real
app.close_day_panel(); app.update()

# ============================================================
# 3. MULTI-SELECT BULK ACTIONS
# ============================================================
NO.CATEGORY_COLORS.setdefault('Work', '#7c5cff')
app.notes = [
    {'id': 10, 'title': 'A', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': [{'filename': 'x.png', 'stored_as': 'x.png'}]},
    {'id': 11, 'title': 'B', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
with open(os.path.join(NO.ATTACHMENTS_DIR, 'x.png'), 'w') as f: f.write('x')
app.save_notes()
app.notebook.select(app.TAB_NOTES); app.update()
app.refresh_note_list(); app.update()

check('selection mode starts off', app.selection_mode is False)
app._toggle_selection_mode()
app.update()
check('selection mode toggles on', app.selection_mode is True)
check('bulk action bar becomes visible', app.bulk_action_bar.winfo_ismapped())

# Regression: the bulk-action bar's 4 widgets used to overflow the fixed
# 280px-wide sidebar, cramping the "Category" button. Rather than assert an
# absolute pixel width (which depends on which font is actually available —
# "Segoe UI" isn't installed on the Linux CI runner, so Tk silently
# substitutes a fallback with different, wider metrics there than on a real
# Windows machine), compare the real fixed bar against a reconstruction of
# the original pre-fix sizing, built with whatever font actually resolves
# on THIS machine. That keeps the check meaningful across environments: it
# verifies the fix made things narrower, not that it hits a Windows-specific
# pixel number.
app.bulk_action_bar.update_idletasks()
fixed_width = app.bulk_action_bar.winfo_reqwidth()

_old_bar = tk.Frame(app)
tk.Label(_old_bar, text="0 selected", font=("Segoe UI", 8, "bold")
          ).pack(side="left", padx=(0, 8))
tk.Button(_old_bar, text="Select all", font=("Segoe UI", 8)
          ).pack(side="left", padx=(0, 4), ipadx=4, ipady=2)
tk.Button(_old_bar, text="\U0001F5D1 Trash", font=("Segoe UI", 8, "bold")
          ).pack(side="left", padx=(0, 4), ipadx=4, ipady=2)
tk.Button(_old_bar, text="\U0001F5C2 Category ▾", font=("Segoe UI", 8)
          ).pack(side="left", padx=(0, 4), ipadx=4, ipady=2)
# The bar gained an Export button since this check was written; the
# reconstruction carries it too, in the original sizing idiom, so the
# comparison stays four-against-four -- compact styling vs pre-fix
# styling, not four buttons vs three.
tk.Button(_old_bar, text="\U0001F4BE Export ▾", font=("Segoe UI", 8)
          ).pack(side="left", ipadx=4, ipady=2)
_old_bar.update_idletasks()
old_width = _old_bar.winfo_reqwidth()
_old_bar.destroy()

check(f'bulk action bar is narrower than the pre-fix sizing '
      f'({fixed_width}px vs {old_width}px reconstructed original)',
      fixed_width < old_width)

card_ids_before = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
app._toggle_note_selected(10, True)
app.update()
card_ids_after = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
check('selecting a note does NOT rebuild the list (no flicker)', card_ids_before == card_ids_after)
check('selection recorded correctly', app.selected_note_ids == {10})

app._bulk_select_all()
app.update()
check('Select all picks up every visible note', app.selected_note_ids == {10, 11})

# ---- Select all agrees with the FILTER about "visible" (audit Z03-F01) ----
# The list strips table plumbing from bodies before matching the search
# ("---" no longer matches every table note); Select all used to match
# the RAW body, so it quietly selected notes the filter had hidden — and
# bulk trash then hit invisible notes. One shared predicate now.
from noteorganizer.core import tables as _tbl7
app.notes.append({'id': 77, 'title': 'TableOnly', 'body': f'{_tbl7.CELL} alfa {_tbl7.CELL} beta {_tbl7.CELL}',
                  'category': 'General', 'updated': '2026-01-01 00:00',
                  'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []})
app.search_var.set(_tbl7.CELL)
app.refresh_note_list(); app.update()
_visible_cards = len(app._note_card_widgets)
app._bulk_select_all()
check('searching table plumbing shows nothing and selects nothing',
      _visible_cards == 0 and app.selected_note_ids == set())
app.search_var.set('alfa')
app.refresh_note_list(); app.update()
app._bulk_select_all()
check('searching cell CONTENT shows and selects exactly that note',
      app.selected_note_ids == {77})
app.search_var.set(''); app.refresh_note_list(); app.update()
app.notes = [n for n in app.notes if n['id'] != 77]
app.refresh_note_list(); app.update()
# Leave the selection exactly as the pre-existing bulk-trash block below
# expects it: everything visible ({10, 11}) selected again.
app._bulk_select_all(); app.update()

# bulk trash, with attachment mention
app.trash = []  # earlier sections (calendar delete tests) left entries here
captured = {}
app.ask_yes_no = lambda t, m, **k: (captured.__setitem__('msg', m), True)[1]
app._bulk_move_to_trash()
app.update()
check('bulk trash confirmation mentions the attachment', '1 attached file' in captured.get('msg', ''))
check('both notes moved to trash', len(app.trash) == 2 and len(app.notes) == 0)
check('selection mode auto-exits after a bulk action', app.selection_mode is False)

# highlight border: correct note, moves correctly, matches theme accent
app.notes = [
    {'id': 20, 'title': 'C', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 21, 'title': 'D', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.find_note(20))
app.update()
# Asked of the COLOUR, not the thickness. Every card carries a two-pixel
# ring now, because the same border does double duty: Tk paints
# `highlightbackground` while a widget has no keyboard focus and
# `highlightcolor` while it does, so one border says both "this is the
# note you have open" (accent) and "this is where the keyboard is"
# (text). Uniform thickness is what stops the list shifting by two pixels
# as the focus walks down it -- and it means thickness no longer answers
# the question this check is about.
check('opened note is highlighted',
      str(app._note_card_widgets[20]['card'].cget('highlightbackground'))
      == str(app.colors['accent']))
check('other note is not highlighted',
      str(app._note_card_widgets[21]['card'].cget('highlightbackground'))
      == str(app.colors['card']))

# ============================================================
# A NOTE'S ACTIONS ARE REACHABLE FROM THE KEYBOARD (C-9)
# ============================================================
# Pinning, exporting, duplicating and deleting all live in the right-click
# menu and nowhere else, so anyone working by keyboard could reach none of
# them. The row asked for two bindings; measured first, a card's takefocus
# was '0' and nothing in the app ever focused one -- so the bindings would
# have been bindings that could never fire, and the missing piece was a
# way for a person to get there.
_c9_card = app._note_card_widgets[20]['card']
_c9_other = app._note_card_widgets[21]['card']
check('a note card is in the keyboard traversal now',
      str(_c9_card.cget('takefocus')) in ('1', 'True'))
_c9_card.focus_set()
app.update(); app.update_idletasks()
check('fixture: the keyboard really is on the card',
      app.focus_get() is _c9_card)
# The ring does double duty, so a focused card must be distinguishable
# from the open one rather than sharing its colour.
check(f'the focus ring is a different colour from the open-note ring '
      f'(ring={str(_c9_card.cget("highlightcolor"))!r}, '
      f'text={str(app.colors["text"])!r}, '
      f'accent={str(app.colors["accent"])!r})',
      str(_c9_card.cget('highlightcolor')) != str(app.colors['accent'])
      and str(_c9_card.cget('highlightcolor')) == str(app.colors['text']))

# The menu, from the keyboard, posted where the note is.
_c9_posted = []
_c9_real = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _c9_posted.append((_m, a))
try:
    _c9_card.event_generate('<Shift-F10>')
    app.update()
    check('Shift+F10 on a focused card opens its actions menu',
          bool(_c9_posted))
    if _c9_posted:
        _c9_menu, _c9_at = _c9_posted[-1]
        # A separator carries no -label and raises, so each entry is asked
        # for on its own -- the same shape the calendar block below uses.
        _c9_labels = []
        for _i in range(_c9_menu.index('end') + 1):
            try:
                _c9_labels.append(str(_c9_menu.entrycget(_i, 'label')))
            except tk.TclError:
                _c9_labels.append('---')
        check('...and it is the whole menu, not a fragment',
              any('Pin' in _l for _l in _c9_labels)
              and any('Export' in _l for _l in _c9_labels)
              and any('Duplicate' in _l for _l in _c9_labels))
        # Posted at the CARD, not at wherever the pointer happens to rest:
        # a menu that opens under the mouse when the mouse was not used is
        # a menu nobody can see.
        check(f'...and it opens at the card rather than at the pointer '
              f'({_c9_at})',
              len(_c9_at) == 2
              and abs(_c9_at[0] - _c9_card.winfo_rootx()) < 200
              and abs(_c9_at[1] - _c9_card.winfo_rooty()) < 200)
    # The dedicated menu key, by whichever name this platform knows it --
    # "App" on Windows, "Menu" on X11, and Tk raises on the other one.
    # Asked of the binding rather than by generating a key that may not
    # exist here: what the row promises is that the key IS bound wherever
    # it exists, and the Shift+F10 route above already proves the handler.
    _c9_bound = set(_c9_card.bind())
    check(f'the dedicated menu key is bound under a name this platform '
          f'knows ({sorted(s for s in _c9_bound if "App" in s or "Menu" in s or "F10" in s)})',
          '<Key-App>' in _c9_bound or '<Key-Menu>' in _c9_bound)
finally:
    NO.tk.Menu.tk_popup = _c9_real

# Walking the list. Asked of the order the cards are PACKED in, because
# the list is sorted, filtered and grouped -- the note after this one in
# the file is very often not the one underneath it on screen.
_c9_card.focus_set()
app.update(); app.update_idletasks()
_c9_card.event_generate('<Down>')
app.update(); app.update_idletasks()
_c9_order = [w for w in app.list_frame.winfo_children()
             if getattr(w, '_card_note_id', None) is not None]
_c9_expected = _c9_order[_c9_order.index(_c9_card) + 1] \
    if _c9_order.index(_c9_card) + 1 < len(_c9_order) else None
check('Down moves the keyboard to the next card on screen',
      _c9_expected is not None and app.focus_get() is _c9_expected)
if _c9_expected is not None:
    _c9_expected.event_generate('<Up>')
    app.update(); app.update_idletasks()
    check('and Up brings it back', app.focus_get() is _c9_card)
# THE CONTROL: Up at the top must not wrap or crash -- it should simply
# stay put, which is what a list does.
_c9_order[0].focus_set()
app.update(); app.update_idletasks()
_c9_order[0].event_generate('<Up>')
app.update(); app.update_idletasks()
check('Up on the first card stays there rather than wrapping',
      app.focus_get() is _c9_order[0])

# The keyboard survives a rebuild. The list is destroyed and rebuilt on a
# save, a search keystroke, a note switch -- a focus left pointing at a
# widget that no longer exists would make this route unusable after the
# first thing that happens.
_c9_card.focus_set()
app.update(); app.update_idletasks()
check('fixture: the keyboard is on a known card before the rebuild',
      app.focus_get() is _c9_card)
app.refresh_note_list()
app.update(); app.update_idletasks()
import time as _c9_time
for _ in range(60):
    if app.focus_get() is app._note_card_widgets[20]['card']:
        break
    app.update(); app.update_idletasks(); _c9_time.sleep(0.01)
check('a rebuilt list puts the keyboard back on the same note',
      app.focus_get() is app._note_card_widgets[20]['card'])
check('highlight color matches the theme accent',
      app._note_card_widgets[20]['card'].cget('highlightbackground') == app.colors['accent'])

# Settle every timer that can rebuild the list on its own before
# measuring, and say out loud that they are settled.
#
# This check compares the cards' Tk paths across a note switch, and for
# months it passed on timing rather than on its subject: the sidebar
# search debounces with after(180, self.refresh_note_list), and the work
# ahead of this point used to take long enough that the timer had always
# fired already. When deleting a note stopped rebuilding the whole list
# (185ms -> 31ms), that slack disappeared, the timer landed BETWEEN the
# two readings, and the check went red without the switch doing anything
# wrong. A check that can be decided by how fast the code above it runs
# is not measuring what it names.
app._flush_autosave()
if getattr(app, '_search_debounce_job', None) is not None:
    app.after_cancel(app._search_debounce_job)
    app._search_debounce_job = None
app.update()
check('nothing is queued to rebuild the list before the measurement',
      getattr(app, '_search_debounce_job', None) is None
      and getattr(app, '_autosave_job', None) is None)
card_ids_before2 = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
app.open_note_in_tab(app.find_note(21))
app.update()
card_ids_after2 = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
check('switching notes does NOT rebuild the list (no flicker)', card_ids_before2 == card_ids_after2)
check('highlight correctly moved to the new note', app._note_card_widgets[21]['card'].cget('highlightthickness') == 2)

# bulk category change
app.ask_yes_no = lambda *a, **k: True
app._toggle_selection_mode()
app._toggle_note_selected(20, True)
app.update()
app._bulk_change_category()
app.update()
work_lbl = find_widget(app._mini_popup, tk.Label, 'Work')
# The category list is a popup: a click generated before Tk has MAPPED it
# is silently dropped (the documented dropped-click class — qa/README).
# Re-generate until the promised state (the category change itself)
# lands, capped into a red check; the pick handler closes the popup, so
# a landed click also stops the re-clicking on its own.
import time as _t7
for _ in range(60):
    if app.find_note(20)['category'] == 'Work':
        break
    try:
        if work_lbl.winfo_exists():
            _qa_click(work_lbl)
    except tk.TclError:
        pass
    app.update()
    _t7.sleep(0.02)
check('bulk category change applied', app.find_note(20)['category'] == 'Work')

# ============================================================
# 4. IMAGE PREVIEW (Pillow)
# ============================================================
png_bytes = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
with open(os.path.join(NO.ATTACHMENTS_DIR, 'preview.png'), 'wb') as f:
    f.write(png_bytes)

def make_png(width, height, color=(255, 0, 0)):
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    row = bytes([0]) + bytes(color) * width
    raw = row * height
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

with open(os.path.join(NO.ATTACHMENTS_DIR, 'big.png'), 'wb') as f:
    f.write(make_png(2000, 1000))
with open(os.path.join(NO.ATTACHMENTS_DIR, 'corrupt.png'), 'wb') as f:
    f.write(b'not a real png')

app.new_note()
app.current_attachments = [
    {'filename': 'preview.png', 'stored_as': 'preview.png'},
    {'filename': 'big.png', 'stored_as': 'big.png'},
]
app.refresh_attachments_list(); app.update()

app.open_attachment(0)
app.update()
img = app._image_preview_ref
check('small image gets zoomed up for visibility (capped at 8x)', img[0].width() == 8 and img[0].height() == 8)
app._dismiss_mini_popup(); app.update()

app.open_attachment(1)
app.update()
target_w = app.winfo_width() * 0.7
img2 = app._image_preview_ref
check('large image is shrunk to fit within the window', img2[0].width() <= target_w + 5)

close_btn = find_widget(app._mini_popup, tk.Button, '✕ Close')
close_btn.invoke()
app.update()
check('Close button dismisses the preview', app._mini_popup is None)

app.current_attachments = [{'filename': 'corrupt.png', 'stored_as': 'corrupt.png'}]
app.refresh_attachments_list(); app.update()
app.open_attachment(0)
app.update()
check('corrupt image file handled gracefully, no crash', app._mini_popup is None)

# ---- A shortcut file is dangerous too (product review T0-8) ----
# The warn-before-opening list covered the 1990s executables and missed
# every vehicle actually used to deliver code today. A .lnk carries an
# arbitrary command line behind an innocent name and icon, and one
# arriving inside an imported backup reached os.startfile through this
# gate with no question asked at all.
for _dangerous in ('.lnk', '.url', '.iso', '.scf', '.appref-ms'):
    check('%s counts as dangerous' % _dangerous,
          _dangerous in app.DANGEROUS_EXTENSIONS)

with open(os.path.join(NO.ATTACHMENTS_DIR, 'stored_invoice.lnk'), 'wb') as f:
    f.write(b'shortcut')
# filename and stored_as DIFFER on purpose: the display name says .pdf,
# the on-disk file is the .lnk. Only a gate keyed off stored_as can pass
# this pair -- with both set to .lnk (the first version of this fixture)
# a gate reading the DISPLAY name would have passed identically, so the
# checks could not tell the honest gate from the fooled one.
app.current_attachments = [{'filename': 'invoice.pdf',
                            'stored_as': 'stored_invoice.lnk'}]
app.refresh_attachments_list(); app.update()
_opened = []
_real_startfile = NO.os.startfile if hasattr(NO.os, 'startfile') else None
NO.os.startfile = lambda p, *a, **k: _opened.append(p)
_asked = []
_real_ask_lnk = app.ask_yes_no
app.ask_yes_no = lambda t, m, **k: (_asked.append((t, k)), False)[1]
try:
    app.open_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _real_ask_lnk
check('opening a .lnk asks first, with the warning glyph',
      len(_asked) == 1 and _asked[0][1].get('icon') == 'warning'
      and _asked[0][1].get('default') == 'no')
check('and answering No does not launch it',
      _opened == [])
app.ask_yes_no = lambda *a, **k: True
try:
    app.open_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _real_ask_lnk
    if _real_startfile is not None:
        NO.os.startfile = _real_startfile
check('answering Yes is what actually opens it', len(_opened) == 1)

# ---- A trailing dot cannot smuggle it past the gate ----
# Windows strips trailing dots/spaces when it OPENS a path, so
# "evil.lnk. " names evil.lnk on disk while splitext sees no extension
# at all: the gate said "safe" about a name the OS then executed.
# normalize_note now stores clean names AND the gate rstrips before
# deciding, so the smuggled spelling must ask exactly like the clean one.
_dirty_note = NO.normalize_note(
    {'title': 'smuggle', 'attachments': [{'filename': 'evil.pdf',
                                          'stored_as': 'evil.lnk. '}]})
check('normalize strips the trailing-dot disguise from stored names',
      _dirty_note['attachments'][0]['stored_as'] == 'evil.lnk')
# Created through the DIRTY spelling on purpose: Windows strips the
# trailing dot+space at creation (landing on evil.lnk, exactly the
# smuggle), while Linux keeps the literal name — either way the path the
# gate resolves from stored_as exists on that platform.
with open(os.path.join(NO.ATTACHMENTS_DIR, 'evil.lnk. '), 'wb') as f:
    f.write(b'shortcut')
# The gate itself must ALSO rstrip (a record that predates the normalize
# rule can still carry the disguise), so feed it the dirty spelling raw.
app.current_attachments = [{'filename': 'evil.pdf', 'stored_as': 'evil.lnk. '}]
app.refresh_attachments_list(); app.update()
_asked2 = []
_opened2 = []
_real_startfile2 = NO.os.startfile if hasattr(NO.os, 'startfile') else None
NO.os.startfile = lambda p, *a, **k: _opened2.append(p)
app.ask_yes_no = lambda t, m, **k: (_asked2.append((t, k)), False)[1]
try:
    app.open_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _real_ask_lnk
    if _real_startfile2 is not None:
        NO.os.startfile = _real_startfile2
check('a trailing-dot .lnk still meets the warning, and No still blocks',
      len(_asked2) == 1 and _asked2[0][1].get('default') == 'no'
      and _opened2 == [])

# non-previewable file still gets the "opens externally" hint
app.current_attachments = [{'filename': 'doc.pdf', 'stored_as': 'doc.pdf'}]
app.refresh_attachments_list(); app.update()
texts = find_all_labels(app.attachments_frame)
check('non-image attachment shows the external-open hint',
      any('Opens in your default app' in t for t in texts))

# ============================================================
# 5. ATTACHMENT MENTION IN DELETE CONFIRMATIONS (single delete)
# ============================================================
app.notes = [{'id': 30, 'title': 'SingleDeleteAttach', 'body': 'x', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [],
              'attachments': [{'filename': 'y.png', 'stored_as': 'y.png'}]}]
app.save_notes()
app.load_note(app.notes[0])
captured2 = {}
app.ask_yes_no = lambda t, m, **k: (captured2.__setitem__('msg', m), False)[1]
app.delete_current_note()
check('single-delete confirmation mentions the attachment', '1 attached file' in captured2.get('msg', ''))

# ============================================================
# 6. "NOTE MISSING" BUG REGRESSION
# ============================================================
app.notes = [
    {'id': 40, 'title': 'KeepOpen', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 41, 'title': 'ToDeleteViaContext', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.find_note(40))
app.update()
app.title_entry.insert(tk.END, ' - unsaved')

error_shown = {'called': False}
app.show_error = lambda t, m: error_shown.update(called=True)
app.ask_yes_no = lambda *a, **k: True
app._context_delete_note(app.find_note(41))
app.update()
check('no spurious "Note missing" error when deleting an unrelated note', not error_shown['called'])
check('the genuinely-open note stays open', app.selected_note_id == 40)
check('its unsaved edit was correctly flushed and saved', 'unsaved' in app.find_note(40)['title'])

# ============================================================
# 6b. CANCELLED CONTEXT-DELETE MUST NOT HIJACK THE SELECTION
# ============================================================
# The delete-selection-hijack bug: _context_delete_note used to repoint
# selected_note_id at the right-clicked note so delete_current_note
# would act on it. Answering No to the confirm (or cancelling the
# occurrence-scope prompt) returned with the selection still on the
# WRONG note, and the next autosave silently overwrote that note with
# the open note's content. The delete target travels as a parameter
# now; a cancel must leave every bit of state exactly as it was.
import copy as _copy_q7

app.notes = [
    {'id': 45, 'title': 'OpenNote', 'body': 'open body', 'category': 'General',
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 46, 'title': 'VictimNote', 'body': 'victim body', 'category': 'General',
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.find_note(45))
app.update()

victim_before = _copy_q7.deepcopy(app.find_note(46))
trash_before = len(app.trash)
app.ask_yes_no = lambda *a, **k: False  # user answers No
app._context_delete_note(app.find_note(46))
app.update()
check('cancelled context-delete keeps the selection on the open note',
      app.selected_note_id == 45)

# Keep typing, then let the autosave path the bug rode fire for real.
app.title_entry.insert(tk.END, ' typed-after-cancel')
app._autosave_now()
app.update()
check('autosave after a cancelled context-delete lands in the OPEN note',
      'typed-after-cancel' in app.find_note(45)['title'])
check('the right-clicked note is untouched bit for bit',
      app.find_note(46) == victim_before)
check('a cancelled delete moves nothing to trash', len(app.trash) == trash_before)

# Same contract on the occurrence-scope cancel (the calendar route).
app.notes = app.notes + [
    {'id': 48, 'title': 'RecurringVictim', 'body': 'x', 'category': 'General', 'date': '2026-07-01',
     'recurrence': {'freq': 'daily'}, 'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.ask_occurrence_scope = lambda *a, **k: None  # user cancels the scope prompt
app._context_delete_note(app.find_note(48), '2026-07-09')
app.update()
check('cancelled scope prompt keeps the selection on the open note',
      app.selected_note_id == 45)
check('cancelled scope prompt leaves the series untouched',
      app.find_note(48).get('exceptions') == [])
check('cancelled scope prompt leaves the occurrence date alone',
      app.current_occurrence_date is None)

# ============================================================
# 6c. THE CALENDAR WRAPPER, THE RE-ANCHOR, AND THE POSITIVE DELETE
# ============================================================
# Three gaps a post-merge review found in 6b's coverage: the calendar
# wrapper (_delete_note_from_calendar) carried no selection assertions,
# so a hijack reintroduced in THAT frame would pass the whole suite;
# nothing proved _delete_note's find_note re-anchor (mutations must
# land in the store even when a caller hands over a copy); and no check
# anywhere asserted the editor Delete button's own confirmed delete.

# The wrapper, scope-cancel: same contract as 6b, one frame higher.
recur_before = _copy_q7.deepcopy(app.find_note(48))
app.ask_occurrence_scope = lambda *a, **k: None
app._delete_note_from_calendar(app.find_note(48), '2026-07-09')
app.update()
check('wrapper scope-cancel keeps the selection on the open note',
      app.selected_note_id == 45)
check('wrapper scope-cancel leaves the occurrence date alone',
      app.current_occurrence_date is None)
app.title_entry.insert(tk.END, ' wrap-cancel')
app._autosave_now()
app.update()
check('autosave after a wrapper cancel lands in the OPEN note',
      'wrap-cancel' in app.find_note(45)['title'])

# The wrapper, whole-series confirm-cancel.
app.ask_occurrence_scope = lambda *a, **k: 'series'
app.ask_yes_no = lambda *a, **k: False
app._delete_note_from_calendar(app.find_note(48), '2026-07-09')
app.update()
check('wrapper series-confirm-cancel keeps the selection on the open note',
      app.selected_note_id == 45)
check('the recurring note survives both wrapper cancels bit for bit',
      app.find_note(48) == recur_before)

# The re-anchor: a caller handing over a COPY must still mutate the store.
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
stale_copy = _copy_q7.deepcopy(app.find_note(48))
app._delete_note(stale_copy, '2026-07-10')
app.update()
check('occurrence delete via a stale copy still lands in the store',
      '2026-07-10' in app.find_note(48).get('exceptions', []))
check("deleting another note's occurrence leaves the editor alone",
      app.selected_note_id == 45)

# The editor Delete button's own route, confirmed for real.
app.ask_yes_no = lambda *a, **k: True
app.open_note_in_tab(app.find_note(46))
app.update()
trash_before2 = len(app.trash)
app.delete_current_note()
app.update()
check('editor-route confirmed delete removes the note', app.find_note(46) is None)
check('editor-route confirmed delete lands in trash',
      len(app.trash) == trash_before2 + 1 and any(t.get('id') == 46 for t in app.trash))
check('editor resets to a fresh note after deleting the open note',
      app.selected_note_id is None)
check('the neighbour note survives the confirmed delete', app.find_note(45) is not None)

# Mock hygiene: un-shadow the real scope prompt rather than "restoring" a
# saved value that could itself be an earlier section's leaked mock.
del app.ask_occurrence_scope

# ============================================================
# 6d. CALENDAR OCCURRENCE UX: WAY BACK, DAY BANNER, MENU, RETURN RULES
# ============================================================
# Field feedback, four pieces: the right-click edit routes lost the
# "Back to Calendar" button (only the panel's Edit button kept it); the
# editor showed only the series' start date, never WHICH day you were
# editing; the calendar menu offered a generic Open/Edit beside the two
# explicit edit scopes; and with occurrence saves riding on explicit
# gestures, Save yanked the user back to the calendar on every one.
import types as _types_q7

app.notes = [
    {'id': 60, 'title': 'SeriesUX', 'body': 'series body', 'category': 'General',
     'date': '2026-07-01', 'recurrence': {'freq': 'daily'},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}},
    {'id': 61, 'title': 'PlainDated', 'body': 'x', 'category': 'General',
     'date': '2026-07-15', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.render_calendar(); app.update()

# The right-click edit routes remember the way back now.
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()
check('ctx-open from a calendar day sets the way back (origin edit)',
      (app._pending_calendar_return or {}).get('date_str') == '2026-07-15'
      and (app._pending_calendar_return or {}).get('origin') == 'edit')
check('the Back to Calendar button is mapped on the ctx route',
      bool(app.calendar_return_btn.winfo_ismapped()))
check('the banner names the day being edited',
      bool(app.occurrence_banner.winfo_ismapped())
      and '15 July 2026' in app.occurrence_banner.cget('text'))

app.load_note(app.find_note(61)); app.update()
check('the banner hides on a plain note',
      not app.occurrence_banner.winfo_ismapped())
app.load_note(app.find_note(60)); app.update()
check('the banner switches to the series text on the series view',
      bool(app.occurrence_banner.winfo_ismapped())
      and 'edits here apply to every day' in app.occurrence_banner.cget('text'))

# An explicit Save on an EDIT-origin visit stays in the editor...
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app.body_text.insert('end', ' ux-edit')
app.save_current_note(auto=False); app.update()
check('an explicit Save on an edit-origin visit stays in the editor',
      app.notebook.index(app.notebook.select()) == app.TAB_NOTES
      and bool(app._pending_calendar_return))
# The mechanism behind the re-asking bug, pinned directly: an occurrence
# compares only its overridable fields, so a just-saved one reads CLEAN.
# (With the old base-note formatting compare it read dirty forever, and
# every later flush re-raised the scope prompt — this sentinel sits
# inside the mocked block, so it names the failure before any unmocked
# flush can hang the run.)
check('a just-saved occurrence reads as clean, not dirty forever',
      app.editor_state_matches_saved(app.capture_editor_state()))
del app.ask_occurrence_scope

# ...while the quick add-a-note flow still returns to the calendar.
app._add_note_for_date('2026-08-20'); app.update()
app.body_text.insert('1.0', 'quick add body')
app.save_current_note(auto=False); app.update()
check('an explicit Save on an add-origin visit returns to the calendar',
      app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
      and not app._pending_calendar_return)
app.close_day_panel(); app.update()

# Back to Calendar saves the pending occurrence edit, asking once.
app._open_note_from_calendar(app.find_note(60), '2026-07-16'); app.update()
scope_ux = []
app.ask_occurrence_scope = lambda *a, **k: (scope_ux.append(1), 'occurrence')[1]
app.body_text.insert('end', ' flushed-on-return')
app._return_to_calendar(); app.update()
check('Back to Calendar saves the pending edit, asking exactly once',
      len(scope_ux) == 1
      and 'flushed-on-return'
      in app.find_note(60)['overrides'].get('2026-07-16', {}).get('body', ''))
# The half the field found missing: answering the question must also
# NAVIGATE. A just-saved occurrence used to still read as dirty (the
# base note's formatting never matches an override body), so the
# cancel guard blocked the trip and every further click re-asked.
check('answering the question actually lands on the calendar',
      app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
      and app._day_panel_mode != 'empty')
app._open_note_from_calendar(app.find_note(60), '2026-07-16'); app.update()
app._return_to_calendar(); app.update()
check('a clean occurrence returns without asking again',
      len(scope_ux) == 1
      and app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR)
# Settle any still-deferred edit while the mock is armed — under the
# no-flush mutant the editor stays dirty here, and a later section's
# flush would otherwise raise the REAL scope dialog and hang the run.
app.open_blank_tab(); app.update()
del app.ask_occurrence_scope
app.close_day_panel(); app.update()

# The calendar menu drops the generic Open/Edit for a recurring note —
# menu labels are captured by patching tk.Menu, popup suppressed.
_labels_q7 = []
_orig_addc = tk.Menu.add_command
_orig_casc = tk.Menu.add_cascade
_orig_pop = tk.Menu.tk_popup
tk.Menu.add_command = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), kw.get('command')))
tk.Menu.add_cascade = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), None))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    _ev_q7 = _types_q7.SimpleNamespace(x_root=100, y_root=100)
    app.show_note_context_menu(_ev_q7, app.find_note(60),
                               occurrence_date='2026-07-15')
    _rec_items = list(_labels_q7); _labels_q7.clear()
    app.show_note_context_menu(_ev_q7, app.find_note(61),
                               occurrence_date='2026-07-15')
    _plain_items = list(_labels_q7)
finally:
    tk.Menu.add_command = _orig_addc
    tk.Menu.add_cascade = _orig_casc
    tk.Menu.tk_popup = _orig_pop
_rec_labels = [l for l, _ in _rec_items]
_plain_labels = [l for l, _ in _plain_items]
check('the calendar menu drops generic Open/Edit for a recurring note',
      not any('Open / Edit' in l for l in _rec_labels)
      and any('only this occurrence' in l for l in _rec_labels)
      and any('Edit whole series' in l for l in _rec_labels))
check('a plain dated note keeps Open/Edit in the calendar menu',
      any('Open / Edit' in l for l in _plain_labels))

# In the NOTE LIST the same entry is redundant: clicking the card opens
# the note, so the menu was offering a longer way to do what the click
# had just done (field feedback). The calendar keeps it, because a click
# there opens the note inside the day panel instead, and the History
# register keeps it too, where a click jumps to a day -- one surface's
# duplication is another's only one-step route to the editor.
_labels_q7.clear()
tk.Menu.add_command = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), kw.get('command')))
tk.Menu.add_cascade = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), None))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    app.show_note_context_menu(_ev_q7, app.find_note(61), click_opens=True)
    _list_labels = [l for l, _ in _labels_q7]
    _labels_q7.clear()
    app.show_note_context_menu(_ev_q7, app.find_note(61))
    _history_labels = [l for l, _ in _labels_q7]
finally:
    tk.Menu.add_command = _orig_addc
    tk.Menu.add_cascade = _orig_casc
    tk.Menu.tk_popup = _orig_pop
check('the note list menu leaves out Open/Edit, which the click already did',
      not any('Open / Edit' in l for l in _list_labels))

# Through the REAL card, not by calling the method with the argument the
# app is supposed to pass: a mutant that dropped click_opens from the
# list's own binding survived the check above, which proved only that the
# method obeys an argument nobody had to send.
app.notebook.select(app.TAB_NOTES)
app.refresh_note_list()
app.update()
_card_labels = None
_card = (app._note_card_widgets.get(61) or {}).get('card')
if _card is not None and _card.winfo_ismapped():
    _labels_q7.clear()
    tk.Menu.add_command = lambda self, **kw: _labels_q7.append(
        (kw.get('label', ''), kw.get('command')))
    tk.Menu.add_cascade = lambda self, **kw: _labels_q7.append(
        (kw.get('label', ''), None))
    tk.Menu.tk_popup = lambda self, *a, **k: None
    try:
        _card.event_generate('<Button-3>', x=5, y=5)
        app.update()
        _card_labels = [l for l, _ in _labels_q7]
    finally:
        tk.Menu.add_command = _orig_addc
        tk.Menu.add_cascade = _orig_casc
        tk.Menu.tk_popup = _orig_pop
check('...and the card itself raises that menu, not one with the entry back',
      _card_labels is not None
      and not any('Open / Edit' in l for l in _card_labels)
      and any('Delete' in l for l in _card_labels))
check('...while keeping everything the click cannot do',
      any('Pin to top' in l or 'Unpin' in l for l in _list_labels)
      and any('Export as file' in l for l in _list_labels)
      and any('Delete' in l for l in _list_labels))
check('...and a menu raised where a click does NOT open the note keeps it',
      any('Open / Edit' in l for l in _history_labels))

# ---- DELETE NAMES ITS SCOPE BEFORE THE CLICK, NOT AFTER IT ----
# Finding C-4 claimed the two History rows destroy different amounts with
# one label and nothing to tell them apart. Measured, that is not what
# happens: a DAY row asks which scope first (Cancel / the entire series /
# this occurrence only), and a SERIES row asks a yes/no that names the
# series and then moves it to the Trash with an Undo. What was true is the
# label -- both rows read "Delete" -- so the menu said nothing about scope
# until after the click. The entry now says it, on the two surfaces that
# open this menu with no date: the sidebar card and the History series row.
#
# A day row keeps the plain word deliberately: from there the scope is
# still a question the user answers, and naming one in the label would
# pre-empt a choice nobody has made.
_c4_labels = {}
for _c4_key, _c4_kwargs in (
        ('series_row', {}),
        ('sidebar_card', {'click_opens': True}),
        ('day_row', {'occurrence_date': '2026-07-15'})):
    _labels_q7.clear()
    tk.Menu.add_command = lambda self, **kw: _labels_q7.append(
        (kw.get('label', ''), kw.get('command')))
    tk.Menu.add_cascade = lambda self, **kw: _labels_q7.append(
        (kw.get('label', ''), None))
    tk.Menu.tk_popup = lambda self, *a, **k: None
    try:
        app.show_note_context_menu(_ev_q7, app.find_note(60), **_c4_kwargs)
        _c4_labels[_c4_key] = [l for l, _ in _labels_q7]
    finally:
        tk.Menu.add_command = _orig_addc
        tk.Menu.add_cascade = _orig_casc
        tk.Menu.tk_popup = _orig_pop
_labels_q7.clear()


def _c4_delete(key):
    return next((l for l in _c4_labels[key] if 'Delete' in l), '')


check('a repeating series row says Delete names the whole series',
      _c4_delete('series_row') == '🗑  Delete the whole series')
check('...and so does the sidebar card, which aims at the same thing',
      _c4_delete('sidebar_card') == '🗑  Delete the whole series')
check('a day row keeps the plain word, because the scope is still a question',
      _c4_delete('day_row') == '🗑  Delete')
# A plain dated note has no series to name, so it must not inherit the
# longer wording from the same branch.
_labels_q7.clear()
tk.Menu.add_command = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), kw.get('command')))
tk.Menu.add_cascade = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), None))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    app.show_note_context_menu(_ev_q7, app.find_note(61))
    _c4_plain = [l for l, _ in _labels_q7]
finally:
    tk.Menu.add_command = _orig_addc
    tk.Menu.add_cascade = _orig_casc
    tk.Menu.tk_popup = _orig_pop
_labels_q7.clear()
check('a note that does not repeat still just says Delete',
      next((l for l in _c4_plain if 'Delete' in l), '') == '🗑  Delete')

# ---- CLEARING A DAY'S DECORATION CAN BE UNDONE ----
# Three routes discarded it and none of them asked: the two "Clear day …"
# menu entries, which sit DIRECTLY under the entries that create the same
# thing, and the palette's own "No color" -- a route finding C-5 did not
# mention. A mis-aim by one menu row turned "change this" into "discard
# it", permanently. No confirmation added: the app's rule is proportion to
# recoverability, and a question in front of every colour change would
# cost more than the loss. So the loss stopped being permanent.
#
# The marker POPUP is deliberately untouched -- it works on a copy, writes
# only on Save and discards on ✕ -- and a check below holds that, so a
# later "consistency" pass does not helpfully break it.
_cc_saved_colors = dict(app.day_colors)
_cc_saved_emoji = dict(app.day_emoji)
_CC_COLOUR = '#cc4444'
_CC_MARKERS = ['🎂', '🎉']
app.notebook.select(app.TAB_CALENDAR)
app.update()
# A day in the month the calendar is SHOWING. A fixed date failed here
# while passing in isolation: earlier checks in this file navigate the
# calendar to another month, and a cell outside the visible month is not
# drawn at all -- so the paint assertions were reading an absent widget
# rather than a wrong colour.
_CC_DAY = '%04d-%02d-10' % (app.cal_year, app.cal_month)


def _cc_seed():
    app.day_colors = {_CC_DAY: _CC_COLOUR}
    app.day_emoji = {_CC_DAY: list(_CC_MARKERS)}
    app._persist_day_colors()
    app._persist_day_emoji()
    app._hide_toast()
    app.render_calendar()
    app.update()
    _cc_stored = NO.load_settings()
    return (_cc_stored.get('day_colors', {}).get(_CC_DAY) == _CC_COLOUR
            and _cc_stored.get('day_emoji', {}).get(_CC_DAY) == _CC_MARKERS)


def _cc_menu(needle):
    """The day menu's own command, captured -- tk_popup blocks, so it is
    suppressed for the duration the way every other menu check here does."""
    _cc_caught = []
    _cc_real_add, _cc_real_pop = tk.Menu.add_command, tk.Menu.tk_popup
    tk.Menu.add_command = lambda self, **kw: _cc_caught.append(
        (kw.get('label', ''), kw.get('command')))
    tk.Menu.tk_popup = lambda self, *a, **k: None
    try:
        app.show_day_context_menu(
            _types_q7.SimpleNamespace(x_root=200, y_root=200), _CC_DAY)
    finally:
        tk.Menu.add_command = _cc_real_add
        tk.Menu.tk_popup = _cc_real_pop
    for _cc_l, _cc_c in _cc_caught:
        if needle in _cc_l and _cc_c is not None:
            return _cc_c
    return None


def _cc_disk():
    _cc_stored = NO.load_settings()
    return (_cc_stored.get('day_colors', {}).get(_CC_DAY),
            _cc_stored.get('day_emoji', {}).get(_CC_DAY))


def _cc_cell_bg():
    """What the calendar cell is painted -- so the undo is proved on the
    screen, not only in the store."""
    _cc_cell = getattr(app, '_cal_cell_widgets', {}).get(_CC_DAY)
    if _cc_cell is None:
        return None
    try:
        return str(_cc_cell.cget('bg'))
    except tk.TclError:
        return None


_cc_toasts = []
_cc_real_toast = app._show_toast


def _cc_record():
    _cc_toasts.clear()
    app._show_toast = (
        lambda text, kind='success', action=None, action_text='Undo',
        yield_to_action=False: (
            _cc_toasts.append((str(text), kind)),
            _cc_real_toast(text, kind=kind, action=action,
                           action_text=action_text,
                           yield_to_action=yield_to_action))[1])


check('clear day: fixture sets a colour and two markers, both on disk',
      _cc_seed())
check('clear day: the calendar really painted the day', _cc_cell_bg() == _CC_COLOUR)
_cc_menu('Clear day color')()
app.update()
check('clear day: the colour goes', _CC_DAY not in app.day_colors
      and _cc_disk()[0] is None)
_cc_undo = app._toast_action
check('clear day: clearing a colour now offers a way back', _cc_undo is not None)
if _cc_undo is not None:
    _cc_undo()
    app.update()
check('clear day: Undo restores the exact colour, in memory and on disk',
      app.day_colors.get(_CC_DAY) == _CC_COLOUR and _cc_disk()[0] == _CC_COLOUR)
check('clear day: ...and repaints the day on screen',
      _cc_cell_bg() == _CC_COLOUR)
check('clear day: clearing a colour never touched the markers',
      _cc_disk()[1] == _CC_MARKERS)

# The palette's "No color" is the same loss by a second door.
_cc_seed()
app._color_day(_CC_DAY, _types_q7.SimpleNamespace(x_root=200, y_root=200))
app.update()
_cc_reset = []


def _cc_find_reset(w):
    for ch in w.winfo_children():
        try:
            if isinstance(ch, tk.Button) and 'No color' in str(ch.cget('text')):
                _cc_reset.append(ch)
        except Exception:
            pass
        _cc_find_reset(ch)


_cc_pop = getattr(app, '_mini_popup', None)
if _cc_pop is not None and _cc_pop.winfo_exists():
    _cc_find_reset(_cc_pop)
check('clear day: the palette carries a "No color" button', bool(_cc_reset))
if _cc_reset:
    _cc_reset[0].invoke()
    app.update()
check('clear day: "No color" discards it like the menu entry does',
      _CC_DAY not in app.day_colors)
_cc_undo = app._toast_action
check('clear day: the palette route offers a way back too', _cc_undo is not None)
if _cc_undo is not None:
    _cc_undo()
    app.update()
check('clear day: Undo works from the palette route',
      app.day_colors.get(_CC_DAY) == _CC_COLOUR)

# Choosing a real colour is not a loss and must stay silent.
_cc_seed()
app._color_day(_CC_DAY, _types_q7.SimpleNamespace(x_root=200, y_root=200))
app.update()
_cc_record()
_cc_swatch = []


def _cc_find_swatch(w):
    for ch in w.winfo_children():
        if ch.winfo_class() == 'Canvas':
            _cc_swatch.append(ch)
        _cc_find_swatch(ch)


_cc_pop = getattr(app, '_mini_popup', None)
if _cc_pop is not None and _cc_pop.winfo_exists():
    _cc_find_swatch(_cc_pop)
if _cc_swatch:
    _qa_click(_cc_swatch[0])
    app.update()
app._show_toast = _cc_real_toast
check('clear day: picking an actual colour offers nothing, nothing was lost',
      not any('cleared' in _t for _t, _k in _cc_toasts))

# The markers.
_cc_seed()
_cc_menu('Clear day markers')()
app.update()
check('clear day: the markers go', _CC_DAY not in app.day_emoji
      and _cc_disk()[1] is None)
_cc_undo = app._toast_action
check('clear day: clearing markers offers a way back', _cc_undo is not None)
if _cc_undo is not None:
    _cc_undo()
    app.update()
check('clear day: Undo restores the exact markers, in order',
      app.day_emoji.get(_CC_DAY) == _CC_MARKERS
      and _cc_disk()[1] == _CC_MARKERS)
check('clear day: clearing markers never touched the colour',
      _cc_disk()[0] == _CC_COLOUR)

# The offer only fits the state the clear left: an EMPTY slot. Anything
# there now is either the same value back or one chosen by hand since, and
# a stale memory must overwrite neither.
_cc_seed()
_cc_menu('Clear day color')()
app.update()
_cc_undo = app._toast_action
_cc_undo()
app.update()
_cc_record()
_cc_undo()
app.update()
app._show_toast = _cc_real_toast
check('clear day: a second Undo says the day is occupied, not that it worked',
      any('has a colour again' in _t and _k == 'info' for _t, _k in _cc_toasts))
check('clear day: ...and leaves the colour the first Undo restored',
      app.day_colors.get(_CC_DAY) == _CC_COLOUR)

_cc_seed()
_cc_menu('Clear day markers')()
app.update()
_cc_undo = app._toast_action
app.day_emoji[_CC_DAY] = ['🗓']
app._persist_day_emoji()
_cc_record()
_cc_undo()
app.update()
app._show_toast = _cc_real_toast
check('clear day: Undo does not overwrite a marker chosen in between',
      app.day_emoji.get(_CC_DAY) == ['🗓'])
check('clear day: ...and says the day is occupied',
      any('has markers again' in _t and _k == 'info' for _t, _k in _cc_toasts))

# The popup was already safe. Hold that, so a later consistency pass does
# not helpfully give it an undo it does not need.
_cc_seed()
app._mark_day_emoji(_CC_DAY, _types_q7.SimpleNamespace(x_root=200, y_root=200))
app.update()
_cc_chips = []


def _cc_find_chip(w, glyph):
    for ch in w.winfo_children():
        try:
            if isinstance(ch, tk.Label) and str(ch.cget('text')) == glyph:
                _cc_chips.append(ch)
        except Exception:
            pass
        _cc_find_chip(ch, glyph)


_cc_pop = getattr(app, '_mini_popup', None)
if _cc_pop is not None and _cc_pop.winfo_exists():
    _cc_find_chip(_cc_pop, _CC_MARKERS[0])
check('clear day: the marker popup still draws its chips', bool(_cc_chips))
if _cc_chips:
    _qa_click(_cc_chips[0])
    app.update()
check('clear day: un-ticking a chip still writes nothing until Save',
      _cc_disk()[1] == _CC_MARKERS)
app._dismiss_mini_popup()
app.update()
check('clear day: dismissing still discards, as the popup promises',
      _cc_disk()[1] == _CC_MARKERS)

app._show_toast = _cc_real_toast
app.day_colors = dict(_cc_saved_colors)
app.day_emoji = dict(_cc_saved_emoji)
app._persist_day_colors()
app._persist_day_emoji()
app._hide_toast()
app.notebook.select(app.TAB_NOTES)
app.update()

# The captured commands are the REAL menu lambdas — invoke them, so the
# return_day plumbing one frame above _ctx_open is exercised too (the
# same frame class a hijack once hid in for deletes).
# "Edit whole series", named in full: the Delete entry says "Delete the
# whole series" on the surfaces that open this menu without a date, and a
# substring match on "whole series" alone would one day pick up the wrong
# lambda -- an edit check that silently exercises a delete.
_series_cmd = next((c for l, c in _rec_items if 'Edit whole series' in l), None)
if _series_cmd is not None:
    _series_cmd(); app.update()
check("the menu's Edit-whole-series lambda arms the way back",
      _series_cmd is not None
      and (app._pending_calendar_return or {}).get('date_str') == '2026-07-15'
      and (app._pending_calendar_return or {}).get('origin') == 'edit'
      and app.current_occurrence_date is None)
_repeat_cmd = next((c for l, c in _plain_items if 'Make this repeat' in l), None)
if _repeat_cmd is not None:
    _repeat_cmd(); app.update()
check('Make-this-repeat from a calendar day arms the way back too',
      _repeat_cmd is not None
      and (app._pending_calendar_return or {}).get('origin') == 'edit')

# The banner follows an occurrence-to-occurrence switch — the text must
# update even when the label is already packed.
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()
app._ctx_open(app.find_note(60), '2026-07-16', return_day='2026-07-16')
app.update()
check('the banner follows an occurrence-to-occurrence switch',
      '16 July 2026' in app.occurrence_banner.cget('text'))

# Cancelling the save question ABORTS the trip back — navigating anyway
# would show the day panel's old content while the edit sits only in
# the editor.
app._ctx_open(app.find_note(60), '2026-07-17', return_day='2026-07-17')
app.update()
app.body_text.insert('end', ' cancel-me')
_scopeN = []
app.ask_occurrence_scope = lambda *a, **k: (_scopeN.append(1), None)[1]
app._return_to_calendar(); app.update()
check('cancelling the save question aborts the trip back',
      len(_scopeN) == 1
      and app.notebook.index(app.notebook.select()) == app.TAB_NOTES
      and bool(app._pending_calendar_return)
      and bool(app.calendar_return_btn.winfo_ismapped())
      and 'cancel-me' in app.body_text.get('1.0', 'end-1c'))
check('nothing reached the store on cancel',
      'cancel-me' not in
      app.find_note(60)['overrides'].get('2026-07-17', {}).get('body', ''))
del app.ask_occurrence_scope
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app._return_to_calendar(); app.update()
check('answering the question completes the trip',
      app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
      and 'cancel-me' in app.find_note(60)['overrides']['2026-07-17']['body'])
del app.ask_occurrence_scope
app.close_day_panel(); app.update()

# Deleting ends the calendar trip on BOTH cleanup arms — a pending that
# outlived a delete once made a later, unrelated Save yank the user
# onto a stale calendar day.
app._ctx_open(app.find_note(61), None, return_day='2026-07-15'); app.update()
app.ask_yes_no = lambda *a, **k: True
app.delete_current_note(); app.update()
check('deleting the open note ends the calendar trip (fresh-editor arm)',
      not app._pending_calendar_return
      and not app.calendar_return_btn.winfo_ismapped())
app.notes.append({'id': 63, 'title': 'Bystander', 'body': 'x',
                  'category': 'General', 'updated': '2026-01-01 00:00',
                  'created': '2026-01-01 00:00', 'checklist': [],
                  'attachments': []})
app.save_notes(); app.refresh_note_list(); app.update()
app._ctx_open(app.find_note(60), '2026-07-18', return_day='2026-07-18')
app.update()
app._context_delete_note(app.find_note(63)); app.update()
check('deleting another note ends the trip too (tab-restore arm)',
      not app._pending_calendar_return
      and not app.calendar_return_btn.winfo_ismapped())

# Un-repeating via a series save retires the day banner — an occurrence
# view of a note that no longer repeats would be a lying label.
app._ctx_open(app.find_note(60), '2026-07-19', return_day='2026-07-19')
app.update()
app.write_recurrence_to_ui({})
_scopeF = []
app.ask_occurrence_scope = lambda *a, **k: (_scopeF.append(1), 'series')[1]
app.save_current_note(auto=False); app.update()
# The scope question is NOT asked any more, and that is the fix, not a
# loss: an override carries five text fields, so "this day" has no
# meaning for un-repeating -- the edit belongs to the series by
# construction. What the check is really about, the day banner retiring,
# is asserted exactly as before.
check('un-repeating asks no scope question it could not act on',
      _scopeF == [])
check('un-repeating via a series save retires the day banner',
      app.current_occurrence_date is None
      and not app.occurrence_banner.winfo_ismapped())
del app.ask_occurrence_scope

# ============================================================
# 6e. OCCURRENCE VISIBILITY: SERIES BANNER, ✎ MARKS, RESET, FILTER
# ============================================================
# The invisible-override field report: a series edit seemed to skip one
# day out of three — that day carried an "only this occurrence" edit,
# which shadows series content forever with nothing saying so and no
# way back. Now the series view names it, the calendar marks it, a menu
# entry resets it, and the sidebar filter can isolate calendar notes.
app.notes = [
    {'id': 64, 'title': 'SeriesVis', 'body': 'series body', 'category': 'General',
     'date': '2026-07-01', 'recurrence': {'freq': 'daily'},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [],
     'overrides': {'2026-07-15': {'title': 'SeriesVis', 'body': 'my special day',
                                  'comments': '', 'category': 'General',
                                  'color': ''}}},
    {'id': 65, 'title': 'DatedVis', 'body': 'x', 'category': 'General',
     'date': '2026-07-20', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 66, 'title': 'PlainVis', 'body': 'x', 'category': 'General',
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.render_calendar(); app.update()

# The series view names the repeat AND the days living on their own.
app.open_note_in_tab(app.find_note(64)); app.update()
_btext = app.occurrence_banner.cget('text')
check('the series banner says edits apply to every day',
      app.occurrence_banner.winfo_ismapped()
      and 'edits here apply to every day' in _btext)
check('the series banner counts the days with their own edits',
      '1 day keeps its own edits' in _btext)

# The calendar marks the overridden day: list row icon + preview chip.
app.open_day_popup('2026-07-15'); app.update()
_rows15 = find_all_labels(app.day_panel)
check('the day list marks an overridden day with the pencil',
      any('✎' in t and 'SeriesVis' in t for t in _rows15))
app.show_day_note(app.find_note(64), '2026-07-15'); app.update()
check('the day preview carries the edited-for-this-day chip',
      any('✎ edited for this day' in t for t in find_all_labels(app.day_panel)))
app.close_day_panel(); app.update()

# The menu offers the reset only where an override exists.
_labels6e = []
_o_add6e, _o_casc6e, _o_pop6e = (tk.Menu.add_command, tk.Menu.add_cascade,
                                 tk.Menu.tk_popup)
tk.Menu.add_command = lambda self, **kw: _labels6e.append(
    (kw.get('label', ''), kw.get('command')))
tk.Menu.add_cascade = lambda self, **kw: _labels6e.append(
    (kw.get('label', ''), None))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    _ev6e = _types_q7.SimpleNamespace(x_root=100, y_root=100)
    app.show_note_context_menu(_ev6e, app.find_note(64),
                               occurrence_date='2026-07-15')
    _with_ov = list(_labels6e); _labels6e.clear()
    app.show_note_context_menu(_ev6e, app.find_note(64),
                               occurrence_date='2026-07-16')
    _without_ov = list(_labels6e)
finally:
    tk.Menu.add_command, tk.Menu.add_cascade, tk.Menu.tk_popup = (
        _o_add6e, _o_casc6e, _o_pop6e)
check('the reset entry appears exactly where an override exists',
      any('Reset this day' in l for l, _ in _with_ov)
      and not any('Reset this day' in l for l, _ in _without_ov))

# Invoke the REAL reset command: the day follows the series again.
# (next() with a default: a missing entry must FAIL the check, not
# crash the suite mid-run — the footer rule.)
_reset_cmd = next((c for l, c in _with_ov if 'Reset this day' in l), None)
app.ask_yes_no = lambda *a, **k: True
if _reset_cmd is not None:
    _reset_cmd(); app.update()
check('reset drops the override and the day shows series content',
      _reset_cmd is not None
      and '2026-07-15' not in (app.find_note(64).get('overrides') or {})
      and NO.effective_note(app.find_note(64),
                            '2026-07-15')['body'] == 'series body')
app.close_day_panel(); app.update()

# The sidebar filter isolates calendar notes — one judgment, used by
# the list render AND bulk select-all, exercised through the render.
app.filter_var.set(app.FILTER_REPEATING)
app.refresh_note_list(); app.update()
_vis = find_all_labels(app.list_frame)
check('the Repeating filter shows only repeating notes',
      any('SeriesVis' in t for t in _vis)
      and not any('DatedVis' in t for t in _vis)
      and not any('PlainVis' in t for t in _vis))
app.filter_var.set(app.FILTER_DATED)
app.refresh_note_list(); app.update()
_vis = find_all_labels(app.list_frame)
check('the Dated filter shows only dated non-repeating notes',
      any('DatedVis' in t for t in _vis)
      and not any('SeriesVis' in t for t in _vis)
      and not any('PlainVis' in t for t in _vis))
app.filter_var.set('All')
app.refresh_note_list(); app.update()

# "Calendar: soonest" ranks by the note's NEXT relevant date from today
# (a series by its next occurrence, upcoming before past, freshest past
# first, undated last). Dates are built RELATIVE TO TODAY — soonest's
# whole point is today-anchored — and the starting order is adverse
# (a fixture whose natural order equals the expected one once let a
# disabled sort branch pass unsorted).
import datetime as _dt_q7
_today = _dt_q7.date.today()
def _d(offset):
    return (_today + _dt_q7.timedelta(days=offset)).strftime('%Y-%m-%d')
app.notes = [
    {'id': 74, 'title': 'SoonE', 'body': 'x', 'category': 'General',
     'updated': '2026-05-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': []},
    {'id': 73, 'title': 'SoonC', 'body': 'x', 'category': 'General',
     'date': _d(-10), 'updated': '2026-04-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 72, 'title': 'SoonD', 'body': 'x', 'category': 'General',
     'date': _d(-2), 'updated': '2026-03-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 71, 'title': 'SoonA', 'body': 'x', 'category': 'General',
     'date': _d(1), 'updated': '2026-02-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 70, 'title': 'SoonB', 'body': 'x', 'category': 'General',
     'date': _d(-9), 'recurrence': {'freq': 'weekly'},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}},
]
app.save_notes()
app.sort_var.set('Calendar: soonest')
app.refresh_note_list(); app.update()
_names_q7 = ('SoonA', 'SoonB', 'SoonC', 'SoonD', 'SoonE')
_ordered = [n for t in find_all_labels(app.list_frame)
            for n in _names_q7 if n in t]
# Weekly since 9 days ago -> occurrences at -9, -2, +5: the NEXT one
# (+5) sits AFTER A's date (+1) on purpose — ranked by start date
# instead (the dishonesty this sort replaces), B would wrongly lead.
check('Calendar-soonest ranks by the next relevant date from today',
      _ordered == ['SoonA', 'SoonB', 'SoonD', 'SoonC', 'SoonE'])

app.sort_var.set('Calendar: oldest')
app.refresh_note_list(); app.update()
_ordered = [n for t in find_all_labels(app.list_frame)
            for n in _names_q7 if n in t]
# Plain chronology by the note's own date: C(-10), B(start -9), D(-2),
# A(+1), undated E at the bottom.
check('Calendar-oldest walks the archive chronologically',
      _ordered == ['SoonC', 'SoonB', 'SoonD', 'SoonA', 'SoonE'])
app.sort_var.set('Recently updated')
app.refresh_note_list(); app.update()

# ============================================================
# 6f. CALENDAR HISTORY: THE REGISTER OF DAYS WITH CONTENT
# ============================================================
# The History view lists dated notes plus each series' separately
# edited days (grouped, collapsible), searchable — including inside a
# day's own override content — and filterable by year. Rows land back
# on the day panel; the grid returns untouched.
app.notes = [
    {'id': 80, 'title': 'HistSeries', 'body': 'agenda', 'category': 'General',
     'date': '2026-01-05', 'recurrence': {'freq': 'weekly'},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [],
     'overrides': {
         '2026-08-17': {'title': '', 'body': 'discutat bugetul',
                        'comments': '', 'category': 'General', 'color': ''},
         '2026-06-15': {'title': 'HistSpecial', 'body': 'plan',
                        'comments': '', 'category': 'General', 'color': ''}}},
    {'id': 81, 'title': 'HistDated', 'body': 'x', 'category': 'General',
     'date': '2026-09-20', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 82, 'title': 'HistLastYear', 'body': 'x', 'category': 'General',
     'date': '2025-11-10', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.render_calendar(); app.update()

app._toggle_calendar_history(); app.update()
_hl = find_all_labels(app._history_rows)
check('History opens over the grid and lists the calendar dwellers',
      app._history_visible and not app.cal_grid_frame.winfo_ismapped()
      and any('HistDated' in t for t in _hl)
      and any('HistSeries' in t for t in _hl)
      and any('HistLastYear' in t for t in _hl))
check('a series group starts collapsed (no ✎ children yet)',
      not any('2026-08-17' in t for t in _hl))

app._history_toggle_group(80); app.update()
_hl = find_all_labels(app._history_rows)
check('expanding the group reveals its edited days, newest first',
      any('2026-08-17' in t for t in _hl)
      and any('2026-06-15' in t and 'HistSpecial' in t for t in _hl))
app._history_toggle_group(80); app.update()

# Search reaches into a day's own override content and auto-expands.
app._history_search_var.set('bugetul')
app.update(); import time as _t7; _t7.sleep(0.4); app.update()
_hl = find_all_labels(app._history_rows)
check('search finds override content and auto-expands its group',
      any('2026-08-17' in t for t in _hl)
      and not any('HistDated' in t for t in _hl))
app._history_search_var.set('')
app.update(); _t7.sleep(0.4); app.update()

# ---- A PASTE ONTO THIS SEARCH BOX'S PLACEHOLDER ----
# The check above drives the search through the VARIABLE, which steps over
# the widget entirely -- so it could never see that a right-click Paste
# landed glued to the placeholder: "Search all calendar entries...bugetul",
# a query that matches nothing, which reads as the search being broken. Set
# through the var it works; set through the field it did not. The fix lives
# in add_placeholder, so this is the sibling of qa1's title checks on the
# one other field shipping with both a placeholder and a paste menu.
#
# The entry is a local in the History builder, not an attribute, so it is
# found by the variable it is wired to -- the one thing that cannot be
# confused with another box on the same screen.
def _entry_for_var(root, var_name):
    for ch in root.winfo_children():
        if isinstance(ch, tk.Entry) and str(ch.cget('textvariable')) == var_name:
            return ch
        found = _entry_for_var(ch, var_name)
        if found is not None:
            return found
    return None


_hist_entry = _entry_for_var(app.history_frame,
                             str(app._history_search_var))
check('the History search box is reachable to press on', _hist_entry is not None)
if _hist_entry is not None:
    _PH_HIST = 'Search all calendar entries...'
    _hist_entry.delete(0, 'end')
    _hist_entry.event_generate('<FocusOut>')
    app.update()
    check('fixture: the History search shows its placeholder',
          _hist_entry.get() == _PH_HIST)
    app.clipboard_clear(); app.clipboard_append('bugetul'); app.update()
    _hist_entry.event_generate('<<Paste>>')
    app.update(); _t7.sleep(0.4); app.update()
    check('pasting into the History search replaces the placeholder',
          _hist_entry.get() == 'bugetul')
    # And the consequence, not just the contents: the query the user pasted
    # is the query that ran. The same hit the var-driven check above proved,
    # so a failure here is about the paste and not about the fixture.
    _hl = find_all_labels(app._history_rows)
    check('and the pasted query is the one the register searched for',
          any('2026-08-17' in t for t in _hl)
          and not any('HistDated' in t for t in _hl))
    # The control: a paste must not wipe a query someone typed.
    _hist_entry.delete(0, 'end')
    _hist_entry.insert(0, 'bug')
    _hist_entry.icursor('end')
    app.update()
    check('fixture: the History search holds real text, no placeholder',
          _hist_entry.get() == 'bug')
    app.clipboard_clear(); app.clipboard_append('etul'); app.update()
    _hist_entry.event_generate('<<Paste>>')
    app.update(); _t7.sleep(0.4); app.update()
    check('a paste into a typed History query leaves that text alone',
          _hist_entry.get() == 'bugetul')
    _hist_entry.delete(0, 'end')
    app.update(); _t7.sleep(0.4); app.update()
app._history_search_var.set('')
app.update(); _t7.sleep(0.4); app.update()

# Year chips filter by the year of the activity.
app._history_set_bucket('Last year'); app.update()
_hl = find_all_labels(app._history_rows)
check('the Last-year chip keeps only that year',
      any('HistLastYear' in t for t in _hl)
      and not any('HistDated' in t for t in _hl))
app._history_set_bucket('All'); app.update()

# Theme switch while open: rows re-render in the new palette.
app.set_theme('light'); app.update()
_row_bgs = [w.cget('bg') for w in app._history_rows.winfo_children()
            if isinstance(w, tk.Frame)]
check('a theme switch recolors the open History rows',
      app._history_visible and _row_bgs
      and all(bg == app.colors['card'] for bg in _row_bgs))
app.set_theme('dark'); app.update()

# A row click lands on the day panel, grid restored, right month.
app._history_open_day(app.find_note(80), '2026-06-15'); app.update()
check('a row click returns the grid on the right month with the preview',
      not app._history_visible and app.cal_grid_frame.winfo_ismapped()
      and (app.cal_year, app.cal_month) == (2026, 6)
      and app._day_panel_mode == 'note')
app.close_day_panel(); app.update()

# Pagination: many dated notes render 50 + Show more.
app.notes = [{'id': 100 + i, 'title': f'Bulk{i}', 'body': 'x',
              'category': 'General', 'date': f'2026-03-{(i % 28) + 1:02d}',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []} for i in range(60)]
app.save_notes()
app._toggle_calendar_history(); app.update()
_bulk_shown = sum(1 for t in find_all_labels(app._history_rows) if 'Bulk' in t)
_more_btn = find_widget(app._history_rows, tk.Button, 'Show more')
check('long listings render a page plus Show more',
      _bulk_shown == 50 and _more_btn is not None)
_more_btn.invoke(); app.update()
_bulk_shown = sum(1 for t in find_all_labels(app._history_rows) if 'Bulk' in t)
check('Show more brings the rest', _bulk_shown == 60)
app._hide_calendar_history(); app.update()
check('leaving History restores the grid',
      app.cal_grid_frame.winfo_ismapped() and not app._history_visible)

# ---- The header toggle's label flips (no separate back button) ----
check('the toggle reads History on the grid',
      '📋 History' in str(app._history_toggle_btn.cget('text')))
app._toggle_calendar_history(); app.update()
check('the toggle reads Calendar while History is open',
      app._history_visible
      and '📅 Calendar' in str(app._history_toggle_btn.cget('text')))
check('there is no separate in-view back button any more',
      find_widget(app.history_frame, tk.Button, '← Calendar') is None)
app._toggle_calendar_history(); app.update()
check('toggling again returns to the grid and restores the label',
      not app._history_visible
      and '📋 History' in str(app._history_toggle_btn.cget('text')))

# ---- A delete from History shows immediately (field report: it only
# appeared after a trip out to the grid and back). render_calendar is
# the single mutation signal, so History refreshes there too.
app.notes = [
    {'id': 93, 'title': 'DelDated', 'body': 'x', 'category': 'General',
     'date': '2026-07-15', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 94, 'title': 'KeepDated', 'body': 'x', 'category': 'General',
     'date': '2026-07-16', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app._toggle_calendar_history(); app.update()
check('both dated notes show in History first',
      any('DelDated' in t for t in find_all_labels(app._history_rows))
      and any('KeepDated' in t for t in find_all_labels(app._history_rows)))
app.ask_yes_no = lambda *a, **k: True
app._delete_note_from_calendar(app.find_note(93), '2026-07-15'); app.update()
check('deleting from History drops the row on the spot, still in History',
      app._history_visible
      and not any('DelDated' in t for t in find_all_labels(app._history_rows))
      and any('KeepDated' in t for t in find_all_labels(app._history_rows)))

# ---- History resets to the grid across a tab round-trip ----
app.notebook.select(app.TAB_NOTES); app.update()
app.notebook.select(app.TAB_CALENDAR); app.update()
check('returning to the Calendar tab shows the grid, not stale History',
      not app._history_visible and app.cal_grid_frame.winfo_ismapped())
# Hygiene: force a known grid state so a mutant that breaks the reset
# above (leaving History open) can't corrupt the later 6f blocks —
# they'd toggle into the wrong state and crash before the footer. The
# check already recorded its verdict; this only lets the suite finish.
if app._history_visible:
    app._hide_calendar_history()
app.update()

# ---- The selected-day outline (field request: the open day must jump
# out) — set on open, torn down on close, surviving a grid re-render,
# and never touching today's own accent top bar.
app.notes = [{'id': 90, 'title': 'OutlineNote', 'body': 'x',
              'category': 'General', 'date': '2026-07-15',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
app.open_day_popup('2026-07-15'); app.update()
_cell = app._cal_cell_widgets.get('2026-07-15')
check('opening a day draws the accent outline on its cell',
      _cell is not None and int(str(_cell.cget('highlightthickness'))) == 2
      and str(_cell.cget('highlightbackground')) == app.colors['accent'])
_other = app._cal_cell_widgets.get('2026-07-10')
check('the other days carry no outline',
      _other is not None
      and int(str(_other.cget('highlightthickness'))) == 0)
app.render_calendar(); app.update()
_cell = app._cal_cell_widgets.get('2026-07-15')
check('the outline survives a grid re-render',
      int(str(_cell.cget('highlightthickness'))) == 2)
app.close_day_panel(); app.update()
_cell = app._cal_cell_widgets.get('2026-07-15')
check('closing the panel clears the outline',
      int(str(_cell.cget('highlightthickness'))) == 0)

# ---- The bounded-series hybrid in History (field confusion: a "10
# times" group opened to nothing) — a small bounded series lists ALL
# its occurrences, ✎ only on edited ones; a childless live series has
# no arrow and jumps straight to its day.
app.notes = [
    {'id': 91, 'title': 'Bounded3', 'body': 'x', 'category': 'General',
     'date': '2026-06-01', 'recurrence': {'freq': 'monthly', 'count': 3},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [],
     'overrides': {'2026-07-01': {'title': 'MidRun', 'body': 'edited',
                                  'comments': '', 'category': 'General',
                                  'color': ''}}},
    {'id': 92, 'title': 'LonelyLive', 'body': 'x', 'category': 'General',
     'date': '2026-05-01', 'recurrence': {'freq': 'weekly'},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}},
]
app.save_notes()
app._toggle_calendar_history(); app.update()
_hl = find_all_labels(app._history_rows)
check('a bounded series announces its occurrence count',
      any('Bounded3' in t and '3 occurrences' in t and '1 edited (✎)' in t
          for t in _hl))
check('a childless live series wears the jump arrow, not a dropdown one',
      any('LonelyLive' in t and t.startswith('→') for t in _hl))
app._history_toggle_group(91); app.update()
_hl = find_all_labels(app._history_rows)
check('expanding the bounded group lists all three days, ✎ only where edited',
      any(t.startswith('✎ 2026-07-01') and 'MidRun' in t for t in _hl)
      and any(t.startswith('• 2026-08-01') for t in _hl)
      and any(t.startswith('• 2026-06-01') for t in _hl))
_lonely_lbl = next(w for w in app._history_rows.winfo_children()
                   if isinstance(w, tk.Frame)
                   and any('LonelyLive' in str(c.cget('text'))
                           for c in w.winfo_children()
                           if isinstance(c, tk.Label)))
_qa_click(_lonely_lbl); app.update()
check('clicking the childless series lands on its day in the calendar',
      not app._history_visible and app._day_panel_mode == 'note'
      and app.selected_day is not None)
app.close_day_panel(); app.update()

# ---- Header layout: History sits at the far right, arrows hug the title.
app.update_idletasks()
_hist_btn = find_widget(app.notebook, tk.Button, '📋 History')
_today_btn = find_widget(app.notebook, tk.Button, 'Today')
check('the History button sits at the far right of the header',
      _hist_btn is not None and _today_btn is not None
      and _hist_btn.winfo_rootx() > _today_btn.winfo_rootx())
app.notebook.select(app.TAB_NOTES); app.update()

# ============================================================
# 7. ATTACHMENT-ONLY NOTE AUTOSAVE
# ============================================================
tmp_file = os.path.join(tempfile.gettempdir(), 'qa7_attach_only.txt')
with open(tmp_file, 'w') as f: f.write('x')

app.open_blank_tab()
app.update()
fd.askopenfilenames = lambda **k: (tmp_file,)
app.add_attachment()
app.update()
check('adding an attachment schedules an autosave', getattr(app, '_autosave_job', None) is not None)

app.after_cancel(app._autosave_job)
app._autosave_now()
app.update()
check('attachment-only note (no title/body) gets saved', app.selected_note_id is not None)
if app.selected_note_id:
    check('saved note has the attachment', len(app.find_note(app.selected_note_id).get('attachments', [])) == 1)

# manual save on a genuinely empty note still warns (regression on the intentional guard)
app.open_blank_tab()
app.update()
warned = {'called': False}
app.show_warning = lambda t, m: warned.update(called=True)
app.save_current_note(auto=False)
app.update()
check('manual save on a truly empty note still warns', warned['called'])

# ============================================================
# 8. LAST-OPEN-NOTE MEMORY
# ============================================================
app.notes = [{'id': 50, 'title': 'RememberMe', 'body': 'remembered body', 'category': 'General',
              'comments': 'a comment', 'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [{'text': 'item', 'done': False}], 'attachments': []}]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.notes[0])
app.update()

saved_settings = NO.load_settings()
check('last-open note id persisted to settings', saved_settings.get('last_open_note_id') == 50)

# new note creation also remembers itself
app.open_blank_tab()
app.update()
app.title_entry.insert(0, 'BrandNew')
app.body_text.insert('1.0', 'x')
app.save_current_note(auto=False)
app.update()
new_id = app.selected_note_id
saved_settings2 = NO.load_settings()
check('creating a new note also updates the remembered id', saved_settings2.get('last_open_note_id') == new_id)

# ---- The SINGLE-NOTE contract (coverage-lift C12, now settled) ----
# The lift queue sent us at close_tab's 28 uncovered lines and found they
# were unreachable: nothing ever created a second tab, so the strip that
# drew them could never appear. That was recorded as a product decision —
# build real multi-note tabs, or simplify them out — and 0.73.165 took
# the second: the strip, close_tab and its unsaved-changes dialog are
# gone. What remains is the contract they were wrapped around, which is
# load-bearing: one note open at a time, its snapshot kept in step, and
# the edit flushed to the note it came from before another one loads.
app.notes = []
for i in range(3):
    app.notes.append({'id': 700 + i, 'title': f'Tab{i}', 'body': f'corp {i}',
                      'category': 'General', 'updated': '2026-01-01 00:00',
                      'created': '2026-01-01 00:00', 'checklist': [],
                      'attachments': []})
app.save_notes()
for n in app.notes:
    app.open_note_in_tab(n)
app.update()
check('opening three notes keeps the single-note contract (one entry)',
      len(app.open_tabs) == 1 and app.active_tab_index == 0
      and app.title_entry.get() == 'Tab2')
check('nothing draws a tab row above the editor any more',
      not hasattr(app, 'tab_strip')
      and not any(w.__class__.__name__ == 'Frame' and w.winfo_height() == 34
                  for w in app.editor_outer.master.winfo_children()
                  if w is not app.editor_outer))
# Switching notes flushes the previous one first — edit, switch, check disk.
app.body_text.insert('end', ' FLUSHED')
app.open_note_in_tab(app.notes[0])
app.update()
check('switching notes flushes the edit to the note it came from',
      'FLUSHED' in app.notes[2]['body'] and app.title_entry.get() == 'Tab0')
# The snapshot the removed strip used to refresh on its way past: it is
# what a restore after a bulk delete reads, so it has to stay in step
# with the editor rather than with whatever was true when the note opened.
app.body_text.insert('end', ' LATER EDIT')
app._sync_editor_snapshot()
check('the stored snapshot follows the live editor',
      'LATER EDIT' in app.open_tabs[0]['state']['body'])
app.open_blank_tab(); app.update()

# ---- DUPLICATES PANEL shortcuts (coverage-lift C15, targeted) ----
# The panel's "Tick all but first" and its cleanup button had never
# been driven through the real widgets.
app.notes = []
for i in range(3):
    app.notes.append({'id': 800 + i, 'title': 'Geamana', 'body': 'idem',
                      'category': 'General', 'updated': '2026-01-01 00:00',
                      'created': '2026-01-01 00:00', 'checklist': [],
                      'attachments': []})
app.save_notes()
app.trash = []
_dpf = tk.Frame(app)
app._build_settings_duplicates_panel(_dpf)
app.update()
def _find_btns7(root, txt):
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Button) and txt in str(c.cget('text')):
                out.append(c)
            walk(c)
    walk(root)
    return out
_tick = _find_btns7(_dpf, 'Tick all but first')
check('the duplicates panel finds the triplet and offers the shortcut',
      len(_tick) == 1)
_tick[0].invoke()
app.update()
_clean = _find_btns7(_dpf, 'Move ticked')
_orig_ask7c = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
app._reopen_dup_panel = lambda: None
try:
    if _clean:
        _clean[0].invoke()
        app.update()
finally:
    app.ask_yes_no = _orig_ask7c
    del app._reopen_dup_panel
check('tick-all-but-first plus cleanup keeps exactly one twin',
      sum(1 for n in app.notes if n.get('title') == 'Geamana') == 1
      and sum(1 for e in app.trash if e.get('title') == 'Geamana') == 2)
_dpf.destroy(); app.update()

# ---- Duplicates hover PREVIEW (coverage-lift #2) ----
_pv_note = {'id': 900, 'title': 'PreviewNota', 'body': 'corp preview',
            'category': 'General', 'updated': '2026-01-01 00:00',
            'created': '2026-01-01 00:00', 'checklist': [],
            'attachments': []}
_pv_lbl = tk.Label(app, text='hover me')
_pv_lbl.pack()
app._attach_dup_preview(_pv_lbl, _pv_note)
app.update()
_qa_fire(_pv_lbl, '<Enter>')
app.update()
_tips = [w for w in _pv_lbl.winfo_children()
         if isinstance(w, tk.Toplevel)]
def _tip_txts7(tops):
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                out.append(str(c.cget('text')))
            walk(c)
    for t in tops:
        walk(t)
    return out
check('hovering a duplicate row shows its floating preview',
      _tips and any('PreviewNota' in t for t in _tip_txts7(_tips)))
_qa_fire(_pv_lbl, '<Leave>')
app.update()
check('leaving the row hides the preview',
      not any(w.winfo_exists() for w in _tips))
_pv_lbl.destroy(); app.update()

print()
# ---- Emptying a saved note survives every automatic route (T0-5 root) ----
# The emptiness guard had SIX hand-rolled copies and the first fix
# repaired one: the autosave and flush gatekeepers still refused an
# emptied note before the fixed writer was ever reached, so the finding's
# own scenario -- clear, switch away, come back -- reverted the emptying.
# These drive the GESTURES (the timer's callee, the switch-away flush,
# Ctrl+S), never save_current_note directly, precisely because the bug
# lived in front of it.
app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'DeGolit')
app.body_text.insert('1.0', 'continut vechi')
app.save_current_note(auto=False); app.update()
_gid = app.selected_note_id
app.title_entry.delete(0, 'end')
app.body_text.delete('1.0', 'end')
app._flush_autosave(); app.update()
_gn = app.find_note(_gid)
check('switch-away flush records the emptying of a saved note',
      _gn is not None and _gn['title'] == '' and _gn['body'] == '')

app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'DeGolit2')
app.body_text.insert('1.0', 'alt continut')
app.save_current_note(auto=False); app.update()
_gid2 = app.selected_note_id
app.title_entry.delete(0, 'end')
app.body_text.delete('1.0', 'end')
app._autosave_now(); app.update()
_gn2 = app.find_note(_gid2)
check('the autosave timer route records the emptying too',
      _gn2 is not None and _gn2['title'] == '' and _gn2['body'] == '')

app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'DeGolit3')
app.body_text.insert('1.0', 'iar continut')
app.save_current_note(auto=False); app.update()
_gid3 = app.selected_note_id
app.title_entry.delete(0, 'end')
app.body_text.delete('1.0', 'end')
app._shortcut_save_now(); app.update()
_gn3 = app.find_note(_gid3)
check('Ctrl+S records the emptying instead of silently refusing',
      _gn3 is not None and _gn3['title'] == '' and _gn3['body'] == '')

# The junk-note guard must HOLD where it should: an empty never-saved
# editor saves nothing on any route...
app.open_blank_tab(); app.update()
_before = len(app.notes)
app._flush_autosave(); app._autosave_now(); app._shortcut_save_now()
app.update()
check('an empty never-saved editor still saves nothing on any route',
      len(app.notes) == _before)
# ...and a date-only new editor stays junk-proof on the AUTOMATIC routes:
# the calendar's new-note-for-a-day flow prefills the date, so counting
# the date as content would autosave an abandoned day-click as a note.
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '2030-05-05')
app._flush_autosave(); app._autosave_now(); app.update()
check('a date-only new editor is not autosaved as a junk note',
      len(app.notes) == _before)

# Comments are content now, on every route -- a comments-only note used
# to be discarded in total silence with a false "Write something".
app.open_blank_tab(); app.update()
app.comments_text.insert('1.0', 'doar un comentariu')
app._autosave_now(); app.update()
check('a comments-only note is real content to the autosave',
      len(app.notes) == _before + 1
      and app.notes[-1]['comments'] == 'doar un comentariu')

# ---- Whitespace edits reach the disk (T0-4, the half in FRONT of the
# writer) ----
# The save learned to keep leading/trailing whitespace, but the dirty
# comparator stripped both sides, so a whitespace-only edit read as "no
# change" and the automatic routes never wrote it: the fix's own promise,
# defeated one frame upstream.
app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'Spatii')
app.body_text.insert('1.0', 'abc')
app.save_current_note(auto=False); app.update()
_wid = app.selected_note_id
app.body_text.insert('end', '\n\n')
_stW = app.capture_editor_state()
check('a whitespace-only edit reads as dirty to the comparator',
      not app.editor_state_matches_saved(_stW))
app._flush_autosave(); app.update()
_wn = app.find_note(_wid)
check('and the flush writes it: trailing blank lines land on disk',
      _wn is not None and _wn['body'] == 'abc\n\n')

# ---- A template asks before wiping non-text content ----
# The replace? question used to test only title/body/comments, so a
# template applied over an attachments- or checklist-only note wiped
# them with no question at all. The gate now shares the ONE content
# test; this witnesses the call site, not just the helper.
app.open_blank_tab(); app.update()
app._working_checklist = [{'text': 'doar lista', 'done': False}]
_askedT = []
app.ask_yes_no = lambda t, m, **k: (_askedT.append(t), False)[1]
try:
    app._apply_template({'name': 'T', 'title': 'TT', 'body': 'BB'})
    app.update()
finally:
    # Back to this file's TOP-OF-FILE baseline (line ~45), not del: the
    # real class method would open real blocking dialogs for every later
    # section -- restore_previous_version asks one, and the run hung
    # there the first time this finally used del.
    app.ask_yes_no = lambda *a, **k: True
check('a checklist-only editor earns the replace? question from a template',
      len(_askedT) == 1
      and app._get_checklist() == [{'text': 'doar lista', 'done': False}])

# ---- Emptying a SHORT note still leaves something to come back to ----
# The rescue copy was gated on a drastic shrink (>40 characters removed),
# written when an empty save could not happen at all. Once clearing a
# saved note became a legitimate edit on every route, a short one slipped
# under the threshold: written to disk blank, no rescue copy, nothing in
# the Trash, and the note switch that persisted it reset the undo history
# too. The case that most needs the net had none.
app.open_blank_tab(); app.update()
app.body_text.insert('1.0', 'milk, eggs, bread')
app.save_current_note(auto=False); app.update()
_sh_id = app.selected_note_id
app.body_text.delete('1.0', 'end')
app._flush_autosave(); app.update()
_sh = app.find_note(_sh_id)
check('emptying a short saved note really does persist', _sh['body'] == '')
check('...and leaves a rescue copy, however few characters it was',
      isinstance(_sh.get('_prev'), dict)
      and _sh['_prev'].get('body') == 'milk, eggs, bread')

# ---- Restore previous survives an aborted save (T0-6 hardening) ----
# The old order popped the rescue copy FIRST and then called a save with
# several legitimate abort paths -- an abort lost the copy and the
# restore in one stroke, permanently now that _prev outlives restarts.
app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'Prev')
app.body_text.insert('1.0',
                     'versiunea lunga originala care se va scurta drastic imediat')
app.save_current_note(auto=False); app.update()
_pid = app.selected_note_id
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'scurt')
app.save_current_note(auto=False); app.update()
_pn = app.find_note(_pid)
check('a drastic shrink leaves the rescue copy behind',
      _pn is not None and isinstance(_pn.get('_prev'), dict))
# A half-typed date used to abort the save the restore rode on, losing
# the copy and the restore together. The restore writes straight to the
# note now, so a mid-edit date field cannot reach it at all -- which is
# the stronger promise, and this pins it.
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '2030-1')
app.restore_previous_version(); app.update()
_pn = app.find_note(_pid)
check('a half-typed date cannot block the restore any more',
      _pn is not None and _pn.get('_prev') is None
      and 'originala' in _pn.get('body', ''))
check('...and the button is gone, because the copy was spent',
      not app.restore_prev_btn.winfo_ismapped())

# ============================================================
# UNDO ON THE DELETE TOAST: THE OCCURRENCE HALF
#
# The other two delete routes always had a way home -- Settings ->
# Recently deleted, if you knew it was there. This one had none at all.
# Removing a single day writes the date into the note's `exceptions`, and
# no screen in the app takes it out again, so the scope dialog's
# "occurrence" button was a permanent choice offering no hint that it
# was. These checks are about that date coming back out.
# ============================================================
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app.ask_yes_no = lambda *a, **k: True
app.notes = [NO.normalize_note({
    'id': 700, 'title': 'UndoOccurrence', 'body': 'every day',
    'category': 'General', 'date': '2026-07-06',
    'recurrence': {'freq': 'daily'}})]
app.save_notes()
app.new_note(); app.refresh_note_list(); app.update()

app._delete_note(app.find_note(700), '2026-07-14')
app.update()
check('removing one day writes it into the exceptions',
      '2026-07-14' in app.find_note(700).get('exceptions', []))
check('...and the toast offers that day back',
      app.toast_frame.winfo_ismapped() and app.toast_action_lbl.winfo_ismapped())

_qa_click(app.toast_action_lbl); app.update()
check('Undo takes the day back out of the exceptions',
      '2026-07-14' not in app.find_note(700).get('exceptions', []))
check('...leaving the rest of the series untouched',
      app.find_note(700).get('recurrence', {}).get('freq') == 'daily')
check('...and puts the user back on that very day',
      app.selected_note_id == 700
      and app.current_occurrence_date == '2026-07-14')

# Two days removed, then the older toast. Each offer carries its own
# date, so the newer removal must survive an Undo of the older one.
app._delete_note(app.find_note(700), '2026-07-15'); app.update()
_u7_older = app._toast_action
app._delete_note(app.find_note(700), '2026-07-16'); app.update()
check('two removals, two dates in the exceptions',
      {'2026-07-15', '2026-07-16'} <= set(app.find_note(700).get('exceptions', [])))
_u7_older(); app.update()
check('the older toast restores ITS day only',
      '2026-07-15' not in app.find_note(700).get('exceptions', [])
      and '2026-07-16' in app.find_note(700).get('exceptions', []))

# Clicked again after the day is already back: an answer, not a crash.
_u7_older(); app.update()
check('putting back a day that is already back changes nothing',
      '2026-07-15' not in app.find_note(700).get('exceptions', [])
      and '2026-07-16' in app.find_note(700).get('exceptions', []))
check('...and says so on the toast',
      'already back' in str(app.toast_lbl.cget('text')).lower())

# The whole series deleted under an offer that names one of its days.
app._delete_note(app.find_note(700), '2026-07-17'); app.update()
_u7_orphan = app._toast_action
app.ask_occurrence_scope = lambda *a, **k: 'series'
app._delete_note(app.find_note(700), '2026-07-18'); app.update()
check('the series delete removes the note itself', app.find_note(700) is None)
_u7_orphan(); app.update()
check('an Undo for a day of a note that is gone does not resurrect it',
      app.find_note(700) is None)
check('...and says the note is no longer there',
      'no longer here' in str(app.toast_lbl.cget('text')).lower())

del app.ask_occurrence_scope

print(f"=== QA7 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
