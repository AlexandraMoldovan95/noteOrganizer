# HERMETIC SEED -- BEFORE the note_organizer import below. Building the
# app calls initialise(), which resolves the data directory and runs the
# data MIGRATIONS, so this script's data directory must be its own by
# then; seeding it before the import leaves no step in between.
# hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to run at all
# outside a scratch run, or beside a notebook it cannot prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile, base64, zlib, struct
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         ignore_pointer as _qa_ignore_pointer,
                         leaves_nothing_behind as _qa_leaves_nothing_behind,
                         pin_popup_visibility as _qa_pin,
                         waiting_timers as _qa_waiting)
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

from _qa_support import find_all_labels, list_texts as _qa_list_texts  # noqa: E402


def list_texts():
    return _qa_list_texts(app)

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
kept, purged_count = NO.purge_expired_trash([old_entry], app.notes)
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
    # From a day of a series, the category entry says it moves the series:
    # read as the day's, it moved every day unasked.
    app.show_note_context_menu(
        type('E', (), {'x_root': 0, 'y_root': 0})(),
        NO.normalize_note(dict(app.notes[0], recurrence={'freq': 'weekly'})), occurrence_date='2026-07-22')
    _ser_labels = ([str(_cal_posted[-1].entrycget(_i, 'label'))
                    for _i in range(_cal_posted[-1].index('end') + 1)
                    if _cal_posted[-1].type(_i) != 'separator'] if _cal_posted else [])
    check(f'from a day of a series, the category entry says it moves the series '
          f'({[_l for _l in _ser_labels if "category" in _l]})',
          any('Move the series to category' in _l for _l in _ser_labels))
    _cal_posted.clear()
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

# ---- A RIGHT-CLICK MENU DOES NOT OUTLIVE THE NEXT ONE ----
# Every right-click builds its menu anew, and none was ever destroyed:
# three windows more per right-click on a note, each holding the note it
# was built for, and a theme switch that walks them all went from about
# 80 ms to over 400. The note's menu and the day's are asked for in turn,
# so a menu that kept its own slot would still leave one of each.
_rm_real = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: None
_rm_note = NO.normalize_note({'id': 7301, 'title': 'Menus', 'body': 'x',
                              'category': 'General', 'date': '2026-07-15'})
app.notes.append(_rm_note)
try:
    _rm_ev = type('E', (), {'x_root': 0, 'y_root': 0})()
    for _rm_i in range(5):
        app.show_note_context_menu(_rm_ev, _rm_note,
                                   occurrence_date='2026-07-15')
        app.show_day_context_menu(_rm_ev, '2026-07-15')
    app.update()
    _rm_left = [w for w in app.winfo_children() if isinstance(w, tk.Menu)]
    check('ten right-clicks on a note and on its day leave one menu behind, '
          'not ten (%d)' % len(_rm_left), len(_rm_left) <= 1)
finally:
    NO.tk.Menu.tk_popup = _rm_real
    app.notes = [n for n in app.notes if n.get('id') != 7301]

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
# It moves the note to the Trash, so it is quiet, in the warning's words:
# the dark red fill is kept for what cannot be undone.
check('the calendar\'s Delete is quiet, in the warning\'s words (a move to the '
      'Trash)',
      del_btn_detail is not None
      and str(del_btn_detail.cget('bg')).lower() == app.colors['card'].lower()
      and str(del_btn_detail.cget('fg')).lower()
      == app.colors['danger_text'].lower())

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
          any('Edit this day' in _l for _l in _lbl2))
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
              'body': 'Text above\n| A | B |\n| --- | --- |\n| 1 | 2 |\nText below',
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
      '|' not in _pv_text and 'Text above' in _pv_text and 'Text below' in _pv_text)
# The note card follows the same rule: a row typed past its last cell is
# part of the table, not words with bars in them.
_card_says = app._card_texts(NO.normalize_note(
    {'id': 991, 'title': 'Card', 'body': 'Words\n| a | b |\n| --- | --- |\n| c | d |and more'}))
check(f'a card shows the words without the table, a row typed past its last '
      f'cell included ({_card_says["preview"]!r} / {_card_says["tags"]!r})',
      '|' not in _card_says['preview'] and 'Words' in _card_says['preview']
      and '▦ 1 table' in _card_says['tags'])
# A card keeps a note's lines apart, empty ones left out: run together, two
# lines read as one sentence.
_card_lines = app._card_texts(NO.normalize_note(
    {'id': 992, 'title': 'Shopping', 'body': 'milk\n\n  bread  \neggs'}))['preview']
check(f'a card keeps the lines of a note apart ({_card_lines!r})',
      _card_lines == 'milk · bread · eggs')
# An empty list item, as Enter at a marker leaves one, is an empty line.
_card_lines = app._card_texts(NO.normalize_note(
    {'id': 995, 'title': 'Packing', 'body': 'Pack the coat\n• \n• milk'}))['preview']
check(f'...and leaves out a list item with no words ({_card_lines!r})',
      _card_lines == 'Pack the coat · • milk')
# Cut, the glimpse holds its "…" to its last word: "...", after the space the
# cut left, wrapped onto a line of its own.
_card_cut = app._card_texts(NO.normalize_note(
    {'id': 993, 'title': 'Stand-up',
     'body': 'What we shipped, what is stuck, what is next for the team'}))['preview']
check(f'a card cut short ends in an ellipsis held to its last word ({_card_cut!r})',
      _card_cut == 'What we shipped, what is stuck, what is…')
_card_cut = app._card_texts(NO.normalize_note(
    {'id': 994, 'title': 'Camping',
     'body': 'Bring the blue tent and water bottles\nCall Ann about Sunday'}))['preview']
check(f'...and a cut on the dot between two lines ends at the first ({_card_cut!r})',
      _card_cut == 'Bring the blue tent and water bottles…')
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
# Opened by call and read back: a real mouse moving over the window would
# take the preview down first (_qa_support.ignore_pointer).
_qa7_hear_pointer = _qa_ignore_pointer(app.cal_canvas)
app.show_day_summary_tooltip('2026-07-20')
app.update()
check('hovering a day normally does show its preview',
      getattr(app, '_day_tooltip', None) is not None)
# ...naming the day day first, the month short: "Monday, 20 Jul".
_dt_said = (find_all_labels(app._day_tooltip)
            if getattr(app, '_day_tooltip', None) is not None else [])
check(f'...which names the day day first ({_dt_said[:1]})',
      any(t.startswith('Monday, 20 Jul') for t in _dt_said))
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
_qa7_hear_pointer()

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
_qa7_hear_pointer = _qa_ignore_pointer(app.cal_canvas)
app.show_note_hover_preview(app.notes[0], '2026-07-21')
app.update()
_hov = _all_text(app._day_tooltip) if getattr(app, '_day_tooltip', None) else ''
_qa7_hear_pointer()
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
          any('Edit this day' in _l for _l in _pm_labels))
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

# A card drawn again has new canvas items: the item behind each card's
# background says whether the list was redrawn.
card_ids_before = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()}
app._toggle_note_selected(10, True)
app.update()
card_ids_after = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()}
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
_visible_cards = len(app._card_order())
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
import time as _c9_time


def _c9_take(widget, cap_s=4.0):
    """FORCE the keyboard onto a widget and wait until Tk agrees -- for a
    PRECONDITION only (qa/README, "Force a precondition; read back only a
    promise"). A plain focus_set() is a request the window manager may
    refuse while another program holds the desktop foreground, and this
    block went red that way whenever someone was using the PC during a
    run: the same code passed, failed, and passed again minutes apart.
    The force is re-asked every quarter second: measured, Windows refused
    the first request of a run and granted the next ones."""
    end = _c9_time.time() + cap_s
    asked = 0.0
    while _c9_time.time() < end:
        if _c9_time.time() - asked >= 0.25:
            widget.focus_force()
            asked = _c9_time.time()
        app.update(); app.update_idletasks()
        if app.focus_get() is widget:
            return True
        _c9_time.sleep(0.01)
    return False


# Asked of the COLOUR, not the thickness. Every card carries a two-pixel
# ring, and the one ring does double duty: the text colour where the
# keyboard is, accent for the note that is open. So the open note's accent
# is asked while the keyboard is somewhere else -- forced into the title
# box first, as a precondition.
check('fixture: the keyboard is off the list, in the title box',
      _c9_take(app.title_entry))
check('opened note is highlighted',
      str(app._card_view(20)['ring']) == str(app.colors['accent']))
check('other note is not highlighted',
      str(app._card_view(21)['ring']) == str(app.colors['card']))

# ============================================================
# A NOTE'S ACTIONS ARE REACHABLE FROM THE KEYBOARD (C-9)
# ============================================================
# Pinning, exporting, duplicating and deleting all live in the right-click
# menu and nowhere else, so anyone working by keyboard could reach none of
# them. The list is one stop for the keyboard now -- its cards are a
# drawing on one canvas -- and a card is "where the keyboard is" when the
# list holds the keyboard and the app has put its ring on that card. That
# second half is a decision the app records (_focused_note_id), so it is
# read back directly: no focus_get(), which answers None whenever another
# program holds the desktop foreground.
check('the note list is in the keyboard traversal',
      str(app.canvas.cget('takefocus')) in ('1', 'True'))

# Settle every timer that can rebuild the list before anything below is
# measured (qa/README).
app._flush_autosave()
if getattr(app, '_search_debounce_job', None) is not None:
    app.after_cancel(app._search_debounce_job)
    app._search_debounce_job = None
app.update()


def _c9_on_note(note_id, cap_s=2.0):
    """Poll for the ring on this NOTE's card while the list holds the
    keyboard. A PROMISE, so it is only polled, never forced."""
    end = _c9_time.time() + cap_s
    while _c9_time.time() < end:
        app.update(); app.update_idletasks()
        if (getattr(app, '_focused_note_id', None) == note_id
                and getattr(app, '_keyboard_on_card', False)):
            return True
        _c9_time.sleep(0.01)
    return False


def _c9_put(note_id):
    """PRECONDITION: the keyboard on the list, its ring on this card."""
    took = _c9_take(app.canvas)
    app._put_keyboard_on_card(note_id)
    app.update(); app.update_idletasks()
    return took and _c9_on_note(note_id)


check('fixture: the keyboard really is on the card', _c9_put(20))
# The ring does double duty, so a focused card must be distinguishable
# from the open one rather than sharing its colour.
_c9_ring = str(app._card_view(20)['ring'])
check(f'the focus ring is a different colour from the open-note ring '
      f'(ring={_c9_ring!r}, text={str(app.colors["text"])!r}, '
      f'accent={str(app.colors["accent"])!r})',
      _c9_ring != str(app.colors['accent'])
      and _c9_ring == str(app.colors['text']))

# The menu, from the keyboard, posted where the note is.
_c9_posted = []
_c9_real = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _c9_posted.append((_m, a))
try:
    app.canvas.event_generate('<Shift-F10>')
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
        # a menu nobody can see. The card's place on screen is the canvas's
        # place plus the card's own, less how far the list is scrolled.
        _c9_view = app._card_view(20)
        _c9_card_x = app.canvas.winfo_rootx()
        _c9_card_y = app.canvas.winfo_rooty() + int(
            _c9_view['y0'] - app.canvas.canvasy(0))
        check(f'...and it opens at the card rather than at the pointer '
              f'({_c9_at})',
              len(_c9_at) == 2
              and abs(_c9_at[0] - _c9_card_x) < 200
              and abs(_c9_at[1] - _c9_card_y) < 200)
    # The dedicated menu key, by whichever name this platform knows it --
    # "App" on Windows, "Menu" on X11, and Tk raises on the other one.
    # Asked of the binding rather than by generating a key that may not
    # exist here: what the row promises is that the key IS bound wherever
    # it exists, and the Shift+F10 route above already proves the handler.
    _c9_bound = set(app.canvas.bind())
    check(f'the dedicated menu key is bound under a name this platform '
          f'knows ({sorted(s for s in _c9_bound if "App" in s or "Menu" in s or "F10" in s)})',
          '<Key-App>' in _c9_bound or '<Key-Menu>' in _c9_bound)
finally:
    NO.tk.Menu.tk_popup = _c9_real

# Walking the list. Asked of the order the cards are DRAWN in, because
# the list is sorted, filtered and grouped -- the note after this one in
# the file is very often not the one underneath it on screen.
_c9_put(20)
app.canvas.event_generate('<Down>')
app.update(); app.update_idletasks()
_c9_ids = app._card_order()
_c9_pos = _c9_ids.index(20) if 20 in _c9_ids else None
_c9_next_id = (_c9_ids[_c9_pos + 1]
               if _c9_pos is not None and _c9_pos + 1 < len(_c9_ids) else None)
check('Down moves the keyboard to the next card on screen',
      _c9_next_id is not None and _c9_on_note(_c9_next_id))
if _c9_next_id is not None:
    app.canvas.event_generate('<Up>')
    app.update(); app.update_idletasks()
    check('and Up brings it back', _c9_on_note(20))
# THE CONTROL: Up at the top must not wrap or crash -- it should simply
# stay put, which is what a list does. An ABSENCE, so it cannot be polled
# for: the ring is already on the first card, and a poll would answer yes
# before a wrong move could land. What is asserted is the handler's own
# decision -- no card is asked to take the ring -- recorded where it is
# made. The precondition is part of the check: a key event only reaches
# the widget that has the keyboard, and one that went elsewhere would
# record no move and read as a pass.
_c9_first_id = _c9_ids[0] if _c9_ids else None
_c9_top_ready = _c9_first_id is not None and _c9_put(_c9_first_id)
_c9_moved = []
_c9_real_put = app._put_keyboard_on_card
app._put_keyboard_on_card = lambda nid: _c9_moved.append(nid)
try:
    app.canvas.event_generate('<Up>')
    app.update(); app.update_idletasks()
finally:
    app.__dict__.pop('_put_keyboard_on_card', None)
check('Up on the first card stays there rather than wrapping',
      _c9_top_ready and _c9_moved == []
      and getattr(app, '_focused_note_id', None) == _c9_first_id)

# The keyboard survives a rebuild. The list is rebuilt on a search
# keystroke, a sort, a filter -- a keyboard left pointing at something
# that no longer exists would make this route unusable after the first
# thing that happens. The canvas that holds the keyboard survives a
# rebuild now; what has to come back is the ring, on the same note.
check('fixture: the keyboard is on a known card before the rebuild',
      _c9_put(20))
app.refresh_note_list()
app.update(); app.update_idletasks()
check('a rebuilt list puts the keyboard back on the same note',
      _c9_on_note(20) and str(app._card_view(20)['ring']) == str(app.colors['text']))

# THE OTHER HALF, and the one that once shipped broken. A rebuild must not
# pull the keyboard ONTO the list when it was somewhere else: a person
# typing a title had the next autosave's rebuild move the keyboard onto a
# card, because a guard read focus_get() -- None whenever the process does
# not own the desktop foreground -- as "nothing has the keyboard". The
# drawn list never asks focus_get(); asserted by recording whether the
# rebuild asks the list to take the keyboard at all, with focus_get() made
# to answer None the way a lost foreground does.
check('fixture: the keyboard is in the title box, not on the list',
      _c9_take(app.title_entry))
_c9_asked = []
_c9_real_focus_set = app.canvas.focus_set
app.canvas.focus_set = lambda: _c9_asked.append('focus_set')
_c9_real_fg = app.focus_get
app.focus_get = lambda: None
try:
    app.refresh_note_list()
    for _ in range(40):
        app.update(); app.update_idletasks()
finally:
    app.focus_get = _c9_real_fg
    app.canvas.__dict__.pop('focus_set', None)
check(f'a rebuild does NOT pull the keyboard off what someone was typing '
      f'in (the list was asked to take it {len(_c9_asked)} times)',
      _c9_asked == [])
check('highlight color matches the theme accent',
      str(app._card_view(20)['ring']) == str(app.colors['accent']))

# Settle every timer that can rebuild the list on its own before
# measuring, and say out loud that they are settled.
#
# This check compares the cards across a note switch, and for months it
# passed on timing rather than on its subject: the sidebar search
# debounces with after(180, self.refresh_note_list), and the work ahead of
# this point used to take long enough that the timer had always fired
# already. When deleting a note stopped rebuilding the whole list (185ms
# -> 31ms), that slack disappeared, the timer landed BETWEEN the two
# readings, and the check went red without the switch doing anything
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
# A card drawn again has new canvas items, so the item behind each card's
# background says whether the list was redrawn.
card_ids_before2 = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()}
app.open_note_in_tab(app.find_note(21))
app.update()
card_ids_after2 = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()}
check('switching notes does NOT rebuild the list (no flicker)', card_ids_before2 == card_ids_after2)
# Asked of the colour: every card wears a two-pixel ring (the keyboard's
# focus ring shares it), so a check of the thickness passed for any card.
check('highlight correctly moved to the new note',
      str(app._card_view(21)['ring']) == app.colors['accent']
      and str(app._card_view(20)['ring']) != app.colors['accent'])

# ---- A CLICK PUTS THE KEYBOARD ON THE LIST, AND THE LIST FOLLOWS IT ----
# Field-reported: "I click a note in the list and press Down, and nothing
# happens." The click opened the note and left the keyboard wherever it
# had been -- the title box, the search box -- so Down went there. A click
# on a card now puts the keyboard on the list with the ring on that card,
# and the walk scrolls the list to keep the ring in view: it used to walk
# the keyboard off the bottom of the screen and leave the list where it
# was. The click is a real one, on the canvas at the card; what is asserted
# is the decision it makes, recorded where it is made.
_ck_saved = list(app.notes)
app.notes = [{'id': 700 + i, 'title': 'Walk %02d' % i, 'body': 'x',
              'category': 'General', 'updated': '2026-01-01 00:%02d' % (59 - i),
              'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}
             for i in range(40)]
app.save_notes()
app.new_note()
app.canvas.yview_moveto(0)
app._list_restore_px = None
app.refresh_note_list(); app.update()
_ck_order = app._card_order()
_ck_asked = []
_ck_real_fs = app.canvas.focus_set
app.canvas.focus_set = lambda: (_ck_asked.append('focus'), _ck_real_fs())[1]
try:
    _ck_at = app._card_point(_ck_order[2])
    _qa_click(app.canvas, x=_ck_at[0], y=_ck_at[1])
    app.update()
finally:
    app.canvas.__dict__.pop('focus_set', None)
check('a click on a card opens its note',
      app.selected_note_id == _ck_order[2])
check('...and puts the keyboard on the list, with the ring on that card',
      bool(_ck_asked) and app._focused_note_id == _ck_order[2])
# Down, as the handler bound to the list runs it, twenty times: the ring
# walks well past the bottom of the view, and the view has to go with it.
for _ in range(20):
    app._list_step(1)
app.update()
_ck_now = app._focused_note_id
_ck_view = app._card_view(_ck_now)
_ck_top = app.canvas.canvasy(0)
_ck_h = app.canvas.winfo_height()
check(f'walking down twenty cards moves the ring there ({_ck_now})',
      _ck_now == _ck_order[22])
check(f'...and the list scrolls to keep the ring on screen (card '
      f'{_ck_view["y0"]}-{_ck_view["y1"]}, view {_ck_top:.0f}-'
      f'{_ck_top + _ck_h:.0f})',
      _ck_view['y0'] >= _ck_top and _ck_view['y1'] <= _ck_top + _ck_h)
# Tab: the list is ONE stop. Each card used to be a widget that took the
# focus, so Tab stepped through every drawn card before leaving the list;
# drawn, the list is one widget and the ring does the walking. Asked of
# Tk's own traversal, tk_focusNext / tk_focusPrev, which is what Tab and
# Shift+Tab run.
_tab_w, _tab_presses = app.search_entry, 0
for _ in range(15):
    _tab_w = _tab_w.tk_focusNext()
    _tab_presses += 1
    if _tab_w is None or _tab_w is app.canvas:
        break
_tab_after = app.canvas.tk_focusNext()
check(f'Tab from the search box reaches the list ({_tab_presses} presses)',
      _tab_w is app.canvas)
check('...the next Tab leaves it, and Shift+Tab comes back to it',
      _tab_after is not None
      and not str(_tab_after).startswith(str(app.canvas))
      and _tab_after.tk_focusPrev() is app.canvas)
app.notes = _ck_saved
app.save_notes()
app.canvas.yview_moveto(0)
app._list_restore_px = None
app.refresh_note_list(); app.update()
# Back to the state the block below expects: note 21 open in the editor.
app.open_note_in_tab(app.find_note(21)); app.update()

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
# Tk paints a frame's border in highlightcolor while the keyboard is on
# one of its buttons: the preview's accent border must be both colours.
from _qa_support import ring_mismatches as _ring_mismatches
_pv_rings = _ring_mismatches(app)
check(f'the image preview keeps its accent border while the keyboard is on '
      f'its buttons ({_pv_rings})', not _pv_rings)
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
# It is offered to Windows now (below); answered No here, so nothing opens.
_cp_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: False
try:
    app.open_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _cp_real_ask
check('corrupt image file handled gracefully, no crash', app._mini_popup is None)

# ---- THE PREVIEW APPEARS AT ONCE, AND AGAIN FROM MEMORY ----
# Every frame of an animation used to be decoded before the first was
# shown -- 1.26 s of nothing for a 60-frame GIF, on every opening. The
# first frame now shows at once and the rest are decoded as the animation
# reaches them; a finished preview is remembered for the next opening, and
# forgotten when the file changes.
import time
from PIL import Image as _pv_Image, ImageDraw as _pv_Draw
import noteorganizer.ui.attachments as _pv_att
_pv_dir = NO.ATTACHMENTS_DIR
_pv_frames = []
for _pv_i in range(8):
    _pv_f = _pv_Image.new('RGB', (300, 200), (20, 20, 30))
    _pv_Draw.Draw(_pv_f).ellipse([_pv_i * 20, 50, _pv_i * 20 + 80, 130],
                                 fill=(230, 90, 60))
    _pv_frames.append(_pv_f)
_pv_gif = os.path.join(_pv_dir, 'anim_pv.gif')
_pv_frames[0].save(_pv_gif, save_all=True, append_images=_pv_frames[1:],
                   duration=20, loop=0)
# Read the moment the preview is built, before any update(): a frame is
# decoded on each 20 ms tick, and an update() slower than that -- any
# loaded machine -- ran ticks first and reported "2 (or 3) decoded when
# shown" about an app that had decoded one. Measured on the untouched
# base commit, red under load and green alone.
app._show_image_preview(_pv_gif, 'anim_pv.gif')
_pv_decoded_when_shown = len(app._image_preview_ref)
_pv_reading_when_shown = app._preview_source is not None
app.update()
check(f'an animation shows its first frame before decoding the rest '
      f'({_pv_decoded_when_shown} decoded when shown)',
      _pv_decoded_when_shown == 1 and _pv_reading_when_shown)
_pv_end = time.time() + 10
while app._preview_source is not None and time.time() < _pv_end:
    app.update(); time.sleep(0.01)
check(f'...decodes the rest as it plays, and lets the file go at the end '
      f'({len(app._image_preview_ref)} of 8)',
      len(app._image_preview_ref) == 8 and app._preview_source is None)
app._dismiss_mini_popup(); app.update()

# Reopened: from memory, every frame at once, without opening the file.
_pv_opened = []
_pv_real_open = _pv_att.Image.open
_pv_att.Image.open = lambda *a, **k: (_pv_opened.append(a[0]),
                                      _pv_real_open(*a, **k))[1]
try:
    app._show_image_preview(_pv_gif, 'anim_pv.gif'); app.update()
    _pv_reopen_frames = len(app._image_preview_ref)
    app._dismiss_mini_popup(); app.update()
    _pv_big = os.path.join(_pv_dir, 'big.png')
    app._show_image_preview(_pv_big, 'big.png'); app.update()
    app._dismiss_mini_popup(); app.update()
    _pv_opened.clear()
    app._show_image_preview(_pv_big, 'big.png'); app.update()
    app._dismiss_mini_popup(); app.update()
finally:
    _pv_att.Image.open = _pv_real_open
check(f'a preview seen before comes back from memory (animation: '
      f'{_pv_reopen_frames} frames at once; files opened on the second '
      f'look at a photo: {len(_pv_opened)})',
      _pv_reopen_frames == 8 and not _pv_opened)

# A file replaced under the same name is read again, not remembered.
_pv_swap = os.path.join(_pv_dir, 'swap_pv.png')
_pv_Image.new('RGB', (300, 200), (255, 0, 0)).save(_pv_swap)
app._show_image_preview(_pv_swap, 'swap_pv.png'); app.update()
_pv_w1 = app._image_preview_ref[0].width()
app._dismiss_mini_popup(); app.update()
_pv_Image.new('RGB', (200, 300), (0, 255, 0)).save(_pv_swap)
_pv_later = time.time() + 5
os.utime(_pv_swap, (_pv_later, _pv_later))
app._show_image_preview(_pv_swap, 'swap_pv.png'); app.update()
_pv_w2 = app._image_preview_ref[0].width()
app._dismiss_mini_popup(); app.update()
check(f'a file replaced under the same name is read again ({_pv_w1} -> '
      f'{_pv_w2} wide)', _pv_w1 != _pv_w2)

# Closed half-way through its first loop, the preview lets go of the file
# -- on Windows an open file cannot be renamed or deleted.
app._preview_cache.clear()
# Closed before any update(), for the reason above: eight 20 ms ticks decode
# the whole file and let it go by themselves, and a slow enough update()
# ran all of them -- after which this proved nothing about closing.
app._show_image_preview(_pv_gif, 'anim_pv.gif')
_pv_held = app._preview_source is not None
app._dismiss_mini_popup(); app.update()
try:
    os.replace(_pv_gif, _pv_gif + '.moved')
    _pv_moved = True
except OSError:
    _pv_moved = False
check(f'closing an animation mid-decode lets its file go (was reading: '
      f'{_pv_held}, then movable: {_pv_moved})', _pv_held and _pv_moved)

# An animation's memory is bounded. Every decoded frame was kept while the
# first loop played, enlarged up to 8x, and kept after the preview closed:
# a 33 KB GIF ran the app out of memory. Frames stop being kept past
# PREVIEW_MEMORY_BYTES (here room for three), and closing lets them go.
_pv_tiny = os.path.join(_pv_dir, 'tiny_anim.gif')
_pv_small = [_pv_Image.new('RGB', (10, 10), (_i * 20, 0, 0)) for _i in range(12)]
_pv_small[0].save(_pv_tiny, save_all=True, append_images=_pv_small[1:],
                  duration=20, loop=0)
app.PREVIEW_MEMORY_BYTES = 10 * 10 * 4 * 3
try:
    app._show_image_preview(_pv_tiny, 'tiny_anim.gif')
    _pv_end = time.time() + 10
    while app._preview_source is not None and time.time() < _pv_end:
        app.update(); time.sleep(0.01)
    _pv_kept = list(app._image_preview_ref)
    check(f'a long animation keeps only the frames that fit, at their own size '
          f'({len(_pv_kept)} of 12 kept, {_pv_kept[0].width()} px wide)',
          len(_pv_kept) == 4 and _pv_kept[0].width() == 10
          and app._preview_source is None)
    app._dismiss_mini_popup(); app.update()
    check('...and closing the preview lets its frames go',
          app._image_preview_ref is None)
finally:
    del app.PREVIEW_MEMORY_BYTES

# ...and so is the work of decoding it. Pillow composites every frame onto
# the whole canvas, and a 105 KB GIF of one-pixel frames on a 50-megapixel
# canvas, shown as a strip a few pixels tall, never filled the memory: the
# app was busy for minutes. The frames are judged together (here room for
# five canvases) and counted (here three), each playing the part it has.
_ab_gif = os.path.join(_pv_dir, 'wide_anim.gif')
_ab_frames = [_pv_Image.new('RGB', (200, 100), (0, 0, 0)) for _i in range(12)]
for _i, _f in enumerate(_ab_frames):
    _f.putpixel((_i * 7, _i), (255, 255, 255))
_ab_frames[0].save(_ab_gif, save_all=True, append_images=_ab_frames[1:],
                   duration=20, loop=0)
_ab_kept = {}
for _ab_attr, _ab_value in (('ANIMATION_PIXEL_BUDGET', 200 * 100 * 5),
                            ('PREVIEW_MAX_FRAMES', 3)):
    getattr(app, '_preview_cache', {}).clear()
    setattr(app, _ab_attr, _ab_value)
    try:
        app._show_image_preview(_ab_gif, 'wide_anim.gif')
        _pv_end = time.time() + 10
        while app._preview_source is not None and time.time() < _pv_end:
            app.update(); time.sleep(0.01)
        _ab_kept[_ab_attr] = (len(app._image_preview_ref or []),
                              app._preview_source is None)
        app._dismiss_mini_popup(); app.update()
    finally:
        delattr(app, _ab_attr)
check(f'an animation stops decoding once its frames together pass the pixel '
      f'budget, and once it holds as many frames as it may ({_ab_kept})',
      _ab_kept == {'ANIMATION_PIXEL_BUDGET': (5, True),
                   'PREVIEW_MAX_FRAMES': (3, True)})
check(f'...a budget that still lets a 4K animation play two dozen frames '
      f'({app.ANIMATION_PIXEL_BUDGET // (3840 * 2160)})',
      app.ANIMATION_PIXEL_BUDGET // (3840 * 2160) >= 24
      and app.ANIMATION_PIXEL_BUDGET <= 10 * app.PREVIEW_PIXEL_BUDGET)

# An animated PNG plays as a GIF does. Pillow gives its frame times as floats
# (40.0) and Tk's after() takes only integers: every animated PNG raised
# halfway through the build, its file held open and its overlay never shown.
_ap_png = os.path.join(_pv_dir, 'sticker_ap.png')
_ab_frames[0].save(_ap_png, format='PNG', save_all=True,
                   append_images=_ab_frames[1:6], duration=40, loop=0)
getattr(app, '_preview_cache', {}).clear()
_ap_raised = None
try:
    app._show_image_preview(_ap_png, 'sticker_ap.png')
    _pv_end = time.time() + 10
    while app._preview_source is not None and time.time() < _pv_end:
        app.update(); time.sleep(0.01)
except tk.TclError as _ap_exc:
    _ap_raised = str(_ap_exc)
_ap_pop = app._mini_popup
_ap_placed = _ap_pop is not None and _ap_pop.winfo_manager() == 'place'
check(f'an animated PNG shows and plays every frame, and lets its file go '
      f'(raised {_ap_raised!r}, placed {_ap_placed}, '
      f'{len(app._image_preview_ref or [])} of 6 frames)',
      _ap_raised is None and _ap_placed
      and len(app._image_preview_ref or []) == 6 and app._preview_source is None)
app._dismiss_mini_popup(); app.update()
# A frame of 0.6 ms ticked every millisecond, half a core while the
# preview was open. 10 ms and less plays at 100, as browsers play it.
_fd_got = {d: app._frame_delay({'duration': d})
           for d in (0.6, 1.5, 10, 10.4, 11, 20, 40.0, None, 'junk')}
check(f'a frame of 10 ms or less plays at 100 ms, a longer one as it says '
      f'({_fd_got})',
      _fd_got == {0.6: 100, 1.5: 100, 10: 100, 10.4: 100, 11: 11, 20: 20,
                  40.0: 40, None: 100, 'junk': 100})

# And whatever else fails halfway takes the half-built preview down with it,
# so its file is let go and no hidden popup is left behind.
getattr(app, '_preview_cache', {}).clear()
_ap_real_after = app.after
_ap_seen = {}


def _ap_after(ms, *a, **k):
    if ms == 20 and not _ap_seen:          # the first frame's tick
        _ap_seen['source'] = app._preview_source
        raise tk.TclError('a failure halfway through the build')
    return _ap_real_after(ms, *a, **k)


app.after = _ap_after
try:
    try:
        app._show_image_preview(_ab_gif, 'wide_anim.gif')
        _ap_failed = False
    except tk.TclError:
        _ap_failed = True
finally:
    del app.after
_ap_was = _ap_seen.get('source')
check(f'a preview that fails halfway lets its file go and leaves no popup '
      f'(failed {_ap_failed}, file was held {_ap_was is not None}, '
      f'now {app._preview_source}, popup {app._mini_popup})',
      _ap_failed and _ap_was is not None and app._preview_source is None
      and app._mini_popup is None
      and (getattr(_ap_was, 'fp', None) is None
           or getattr(_ap_was.fp, 'closed', False)))
app.update()

# A remove lets go of the file a preview is still reading: on Windows an open
# file is not deleted, so the record went and the file stayed for good.
from noteorganizer.core.storage import _attachment_path_within as _ap_within
import shutil as _ap_shutil
_ap_name = '20261003120000000000_held.gif'
_ap_shutil.copy(_ab_gif, os.path.join(NO.ATTACHMENTS_DIR, _ap_name))
getattr(app, '_preview_cache', {}).clear()
_ap_kept = list(app.current_attachments)
app.current_attachments = [{'filename': 'held.gif', 'stored_as': _ap_name}]
app._show_image_preview(_ap_within(_ap_name), 'held.gif')
_ap_reading = app._preview_source is not None
app.remove_attachment(0)
check(f'removing a file its preview is still reading lets the file go first '
      f'(was reading {_ap_reading}, now {app._preview_source})',
      _ap_reading and app._preview_source is None
      and not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _ap_name)))
app._dismiss_mini_popup()
app._cancel_pending_autosave()
app.current_attachments = _ap_kept
app.refresh_attachments_list(); app.update()

# An image too large to decode here is offered to the program Windows opens
# images with: a 439 KB PNG of 12000x12000 peaked at 1.7 GB in the preview.
_pv_asked = []
_pv_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (_pv_asked.append(a[0] if a else ''), False)[1]
app.PREVIEW_PIXEL_BUDGET = 1000
try:
    app._show_image_preview(os.path.join(_pv_dir, 'big.png'), 'big.png'); app.update()
    check(f'an image past the pixel budget is offered elsewhere, not decoded '
          f'({_pv_asked})',
          _pv_asked == ['Too large to preview'] and app._mini_popup is None)
finally:
    app.ask_yes_no = _pv_real_ask
    del app.PREVIEW_PIXEL_BUDGET

# A JPEG photo is decoded at the size it is shown, and still fills it.
_pv_jpg = os.path.join(_pv_dir, 'photo_pv.jpg')
_pv_Image.new('RGB', (3000, 2000), (40, 90, 160)).save(_pv_jpg, quality=85)
app.update_idletasks()
_pv_tw = max(int(app.winfo_width() * 0.7), 200)
_pv_th = max(int(app.winfo_height() * 0.7), 200)
app._show_image_preview(_pv_jpg, 'photo_pv.jpg'); app.update()
_pv_pw = app._image_preview_ref[0].width()
_pv_ph = app._image_preview_ref[0].height()
app._dismiss_mini_popup(); app.update()
check(f'a large JPEG fits the preview, and fills it ({_pv_pw}x{_pv_ph} in '
      f'{_pv_tw}x{_pv_th})',
      _pv_pw <= _pv_tw and _pv_ph <= _pv_th
      and max(_pv_pw / _pv_tw, _pv_ph / _pv_th) > 0.95)

# ---- Every frame is judged before it is decoded ----
# The pixel budget asked only the first frame: a TIFF named .png, 16x16 and
# then 13,000x13,000, showed at once and took 46 s and 2 GB for its second
# page. A JPEG holding two pictures (MPO) is the same shape through a decoder
# the preview does use. ISSUES_LOG: "The preview that kept every frame".
_mf_path = os.path.join(_pv_dir, 'two_pictures.jpg')
_pv_Image.new('RGB', (16, 16), (200, 30, 30)).save(
    _mf_path, format='MPO', save_all=True,
    append_images=[_pv_Image.new('RGB', (300, 200), (30, 30, 200))])
app.PREVIEW_PIXEL_BUDGET = 1000
try:
    app._show_image_preview(_mf_path, 'two_pictures.jpg'); app.update()
    _mf_shown = app._mini_popup is not None
    for _ in range(50):
        app.update()
        time.sleep(0.02)
        if app._preview_source is None:
            break
    _mf_frames = len(app._image_preview_ref or [])
    _mf_released = app._preview_source is None
finally:
    del app.PREVIEW_PIXEL_BUDGET
    app._dismiss_mini_popup(); app.update()
check(f'a later frame past the pixel budget is never decoded: the first shows '
      f'and the animation stops there ({_mf_frames} frame(s) kept)',
      _mf_shown and _mf_frames == 1 and _mf_released)

# Pillow knows a file by its contents, so a ".png" could be any of the forty
# kinds it reads -- a TIFF, an icon set, an EPS it hands to Ghostscript. Only
# the decoders of the pictures the preview shows may read one.
_mf_ico = os.path.join(_pv_dir, 'icon_named.png')
_pv_Image.new('RGBA', (64, 64), (0, 120, 0, 255)).save(
    _mf_ico, format='ICO', sizes=[(16, 16), (64, 64)])
# ...and it is not called unreadable with no way to open it: it is offered to
# the program the computer opens its kind with, as a picture too large is.
_mf_told, _mf_opened = [], []
_mf_real_warn, _mf_real_ask = app.show_warning, app.ask_yes_no
_mf_real_start = getattr(NO.os, 'startfile', None)
app.show_warning = lambda t, m, **k: _mf_told.append(('told', t))
app.ask_yes_no = lambda t, m, **k: (_mf_told.append(('asked', t)), True)[1]
NO.os.startfile = lambda p, *a, **k: _mf_opened.append(os.path.basename(p))
try:
    app._show_image_preview(_mf_ico, 'icon_named.png'); app.update()
    _mf_ico_shown = app._mini_popup is not None
finally:
    app.show_warning, app.ask_yes_no = _mf_real_warn, _mf_real_ask
    if _mf_real_start is None:
        del NO.os.startfile
    else:
        NO.os.startfile = _mf_real_start
    app._dismiss_mini_popup(); app.update()
check(f'a picture of another kind under a .png name is not decoded, and is '
      f'offered to the program the computer opens it with ({_mf_told}, '
      f'opened {_mf_opened})',
      _mf_told == [('asked', "Can't preview this file")] and not _mf_ico_shown
      and _mf_opened == ['icon_named.png'])

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
app.ask_yes_no = lambda t, m, **k: (_asked.append((t, k, m)), False)[1]
try:
    app.open_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _real_ask_lnk
check('opening a .lnk asks first, with the warning glyph',
      len(_asked) == 1 and _asked[0][1].get('icon') == 'warning'
      and _asked[0][1].get('default') == 'no')
# The warning names the file by the type that opens: quoting the label, it
# called a ".pdf" dangerous, which teaches a person to click past it.
check('the warning names the file by the type that opens, not the label '
      f'({_asked[0][2][:40] if _asked else None!r})',
      len(_asked) == 1 and '“invoice.lnk”' in _asked[0][2]
      and 'invoice.pdf' not in _asked[0][2])
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

# ---- The row shows the file that opens, not the label ----
# A backup can label any file as anything: "Holiday photo.jpg" over an
# .rdp drew a photo's icon and no hint, and the click handed Windows a
# remote connection. The record goes in raw, past normalize_note, with a
# right-to-left override in its label, so the row's own reading is what is
# checked. ISSUES_LOG: "The photo that was a remote connection".
with open(os.path.join(NO.ATTACHMENTS_DIR, '20261001120000000001_trip.rdp'), 'wb') as f:
    f.write(b'full address:s:example.invalid')
app.current_attachments = [{'filename': 'Holiday photo\u202e.jpg',
                            'stored_as': '20261001120000000001_trip.rdp'}]
app.refresh_attachments_list(); app.update()
_row_texts = find_all_labels(app.attachments_frame)
check(f'a photo label over another kind of file shows that kind: its name, '
      f'no picture icon, and the outside-app hint ({_row_texts!r})',
      '📄 Holiday photo.rdp' in _row_texts
      and not any('🖼' in t or '\u202e' in t for t in _row_texts)
      and any('Opens in your default app' in t for t in _row_texts))
# A label too long for the row gives way before its type, never at the edge:
# padded with blank-looking characters, "Holiday photo.jpg" over an .rdp hid
# the ".rdp" beyond the row's end.
app.current_attachments = [{'filename': 'Holiday photo.jpg' + '\u2800' * 120 + '.jpg',
                            'stored_as': '20261001120000000001_trip.rdp'}]
app.refresh_attachments_list(); app.update(); app.update()
_ll_lbl = next((w for w in app.attachments_frame.winfo_children()[0]
                .winfo_children()[0].winfo_children()
                if isinstance(w, tk.Label)), None)
_ll_text = str(_ll_lbl.cget('text')) if _ll_lbl is not None else ''
check(f'a label too long for its row keeps its type in sight ({_ll_text[:20]!r}...'
      f'{_ll_text[-6:]!r}, {_ll_lbl.winfo_reqwidth() if _ll_lbl else None} of '
      f'{_ll_lbl.winfo_width() if _ll_lbl else None} px)',
      _ll_lbl is not None and _ll_text.endswith('\u2026.rdp')
      and _ll_text.startswith('📄 Holiday photo.jpg')
      # Its own border and padding are a few pixels a side: the pieces are
      # measured one by one, so a pixel or two over still draws every letter.
      and _ll_lbl.winfo_reqwidth() <= _ll_lbl.winfo_width() + 3)
# ...and the ✕ stays in the row: packed after the name, the name's length took
# the whole row and a long-named file could not be removed from it.
_ll_row = app.attachments_frame.winfo_children()[0].winfo_children()[0]
_ll_x = next((w for w in _ll_row.winfo_children() if isinstance(w, tk.Button)), None)
check(f'a long-named attachment keeps its ✕ in the row '
      f'({_ll_x.winfo_x() if _ll_x else None} + {_ll_x.winfo_width() if _ll_x else None} '
      f'of {_ll_row.winfo_width()} px)',
      _ll_x is not None and _ll_x.winfo_ismapped() and _ll_x.winfo_width() > 10
      and _ll_x.winfo_x() + _ll_x.winfo_width() <= _ll_row.winfo_width())
# A capital dotted I lower-cases to two characters, and the cut was
# found in a lower-cased copy, so four of them moved it past the type. And a
# label with no type, or one of three hundred lines, was drawn whole: at
# 60,000 letters it ended the app at every start, the note being last open.
_ll_shown = {}
for _ll_key, _ll_label, _ll_file in (
        ('dotted', 'İİİİ Holiday' + '⠀' * 120 + '.jpg',
         '20261001120000000001_trip.rdp'),
        ('lines', 'minutes\n' * 300 + '.rdp', '20261001120000000001_trip.rdp'),
        ('no type', 'W' * 900, '20261001120000000002_plain')):
    if not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _ll_file)):
        open(os.path.join(NO.ATTACHMENTS_DIR, _ll_file), 'wb').close()
    app.current_attachments = [{'filename': _ll_label, 'stored_as': _ll_file}]
    app.refresh_attachments_list(); app.update(); app.update()
    _ll_l = next((w for w in app.attachments_frame.winfo_children()[0]
                  .winfo_children()[0].winfo_children()
                  if isinstance(w, tk.Label)), None)
    _ll_shown[_ll_key] = (str(_ll_l.cget('text')) if _ll_l else '',
                          _ll_l.winfo_reqheight() if _ll_l else 0,
                          _ll_l.winfo_reqwidth() <= _ll_l.winfo_width() + 3
                          if _ll_l else False)
_ll_line = _ll_shown['no type'][1]
check(f'...and with capital dotted Is before it too '
      f'({_ll_shown["dotted"][0][-8:]!r})',
      _ll_shown['dotted'][0].endswith('….rdp'))
check(f'a label of many lines, or long with no type, is drawn on one line that '
      f'fits its row ({[(t[:12], t[-6:], h, fits) for t, h, fits in _ll_shown.values()]})',
      '\n' not in _ll_shown['lines'][0] and _ll_shown['lines'][0].endswith('.rdp')
      and _ll_shown['lines'][1] <= _ll_line and _ll_shown['lines'][2]
      and _ll_shown['no type'][0].endswith('…') and _ll_shown['no type'][2])
# The picture's preview is as wide as what it holds, and drew the name whole
# before its two buttons: 300 letters made it wider than the window, Close
# past its edge; 60,000 passed X's limit and ended the app.
from PIL import Image as _ll_Image
_ll_Image.new('RGB', (60, 40), (40, 90, 200)).save(
    os.path.join(NO.ATTACHMENTS_DIR, '20261001120000000003_wide.png'))
app.current_attachments = [{'filename': 'Holiday at the lake ' * 15 + '.png',
                            'stored_as': '20261001120000000003_wide.png'}]
app.refresh_attachments_list(); app.update()
app.open_attachment(0); app.update(); app.update()
_ll_pop = app._mini_popup
_ll_close = find_widget(_ll_pop, tk.Button, '✕ Close') if _ll_pop is not None else None
_ll_head = _ll_close.master if _ll_close is not None else None
check(f"a picture's preview with a long name stays inside the window, its "
      f"Close in its header ({_ll_pop.winfo_width() if _ll_pop else None} of "
      f"{app.winfo_width()} px)",
      _ll_close is not None and _ll_pop.winfo_width() <= app.winfo_width()
      and _ll_close.winfo_ismapped()
      and _ll_close.winfo_x() + _ll_close.winfo_width() <= _ll_head.winfo_width())
app._dismiss_mini_popup(); app.update()

# ---- A colon never reaches a stored name ----
# The resolver refuses a stored name holding one: on Windows it names a
# stream of another file ("x.docx:Zone.Identifier"), and a backup's Trash
# entry deleted a file's Mark of the Web by it. Only Linux lets a file be
# called so; attached there, it is stored without the colon and still opens.
if os.name != 'nt':
    _co_src = os.path.join(tempfile.mkdtemp(prefix='qa7-colon-'), 'minutes 10:30.txt')
    with open(_co_src, 'w', encoding='utf-8') as f:
        f.write('minutes')
    app.current_attachments = []
    _co_real_pick = fd.askopenfilenames
    fd.askopenfilenames = lambda **k: (_co_src,)
    try:
        app.add_attachment(); app.update()
    finally:
        fd.askopenfilenames = _co_real_pick
    _co_rec = [dict(a) for a in app.current_attachments]
    _co_opened, _co_warned = [], []
    _co_real_start = getattr(NO.os, 'startfile', None)
    _co_real_warn = app.show_warning
    NO.os.startfile = lambda p, *a, **k: _co_opened.append(os.path.basename(p))
    app.show_warning = lambda t, m, **k: _co_warned.append(t)
    try:
        app.open_attachment(0); app.update()
    finally:
        app.show_warning = _co_real_warn
        if _co_real_start is None:
            del NO.os.startfile
        else:
            NO.os.startfile = _co_real_start
    app._cancel_pending_autosave()
    app.current_attachments = []
    app.refresh_attachments_list(); app.update()
    check(f'a file whose name holds a colon is stored without one, and opens '
          f'({_co_rec}, opened {_co_opened}, warned {_co_warned})',
          len(_co_rec) == 1 and ':' not in _co_rec[0]['stored_as']
          and _co_rec[0]['filename'] == 'minutes 10:30.txt'
          and _co_opened == [_co_rec[0]['stored_as']] and not _co_warned)

# ---- Only kinds that just show their contents open unasked ----
# The warn-before-opening list was a list of dangerous kinds, and such a
# list is never complete: .pyw, .rdp, .theme, .xll, macro documents, .msu
# and more went straight to Windows. Now a short list opens at once, a
# kind that runs code asks with the warning, and every other kind asks
# calmly -- while a person's own .docx, .pdf or .mp4 still meets no question.
_k_opened, _k_asked = [], []
_k_real_ask, _k_real_dlg = app.ask_yes_no, app._themed_dialog
_k_real_start = getattr(NO.os, 'startfile', None)
_k_answer = [False]
NO.os.startfile = lambda p, *a, **k: _k_opened.append(os.path.basename(p))
app.ask_yes_no = lambda t, m, **k: (_k_asked.append(('warn', t, m, k)), _k_answer[0])[1]
app._themed_dialog = lambda t, m, **k: (_k_asked.append(('ask', t, m, k)), _k_answer[0])[1]


def _k_click(name):
    stored = '20261001120000000000_' + name
    with open(os.path.join(NO.ATTACHMENTS_DIR, stored), 'wb') as f:
        f.write(b'content')
    app.current_attachments = [{'filename': name, 'stored_as': stored}]
    _k_opened.clear(); _k_asked.clear()
    app.open_attachment(0); app.update()
    return [a[0] for a in _k_asked], list(_k_opened)


try:
    _k_plain = {n: _k_click(n) for n in ('minutes.docx', 'sheet.xlsx', 'slides.pptx',
                                         'scan.pdf', 'notes.txt', 'clip.mp4')}
    check(f'a person\'s own documents, PDFs, text and video open with no question '
          f'({_k_plain})',
          all(v == ([], ['20261001120000000000_' + n]) for n, v in _k_plain.items()))
    _k_code = {n: _k_click(n) for n in ('run.pyw', 'trip.rdp', 'wall.theme', 'report.xll',
                                        'minutes.docm', 'upd.msu', 'app.msixbundle', 'c.iqy')}
    check(f'kinds that run code or reach out ask with the warning, and No opens '
          f'nothing ({_k_code})',
          all(v == (['warn'], []) for v in _k_code.values()))
    _k_unknown = {n: _k_click(n) for n in ('archive.zip', 'page.html', 'old.doc', 'odd.xyz')}
    check(f'any other kind asks first, and Cancel opens nothing ({_k_unknown})',
          all(v == (['ask'], []) for v in _k_unknown.values()))
    _k_click('archive.zip')
    _k_q = _k_asked[0] if _k_asked else ('', '', '', {})
    check(f'the question for an unknown kind is calm and plain: it names the file, '
          f'offers Cancel and Open with Cancel first, and claims nothing about '
          f'running programs ({_k_q[1]!r}: {_k_q[2][:60]!r})',
          _k_q[1] == 'Open this file?'
          and '“archive.zip”' in _k_q[2]
          and "doesn't know this kind of file" in _k_q[2]
          and 'run programs' not in _k_q[2]
          and _k_q[3].get('buttons') == [('Cancel', False), ('Open', True)]
          and _k_q[3].get('default') == 'Cancel')
    _k_answer[0] = True
    check('...and Open is what opens it',
          _k_click('archive.zip') == (['ask'], ['20261001120000000000_archive.zip']))
finally:
    app.ask_yes_no, app._themed_dialog = _k_real_ask, _k_real_dlg
    if _k_real_start is not None:
        NO.os.startfile = _k_real_start

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
# On Windows the dirty name reaches evil.lnk under another name, so the
# resolver refuses it outright ("A file with two names"); elsewhere the file
# has that literal name, and the gate asks.
check('a trailing-dot .lnk never opens unasked: the warning with No, or '
      f'refused as another name ({_asked2})',
      _opened2 == []
      and ((len(_asked2) == 1 and _asked2[0][1].get('default') == 'no')
           or (os.name == 'nt' and _asked2 == [])))

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
check('the day strip names the day being edited',
      bool(app.day_strip.winfo_ismapped())
      and '15 July 2026' in app.day_strip_lbl.cget('text'))
# Written out day first, the day without a leading nought, the names the
# app's own whatever language Windows speaks: "Monday, 6 July 2026".
app._ctx_open(app.find_note(60), '2026-07-06', return_day='2026-07-06')
app.update()
check(f'the day strip writes the day out, day first '
      f'({app.day_strip_lbl.cget("text")!r})',
      'Only this day: Monday, 6 July 2026 —' in app.day_strip_lbl.cget('text'))
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()

app.load_note(app.find_note(61)); app.update()
check('the banner and the day strip hide on a plain note',
      not app.occurrence_banner.winfo_ismapped()
      and not app.day_strip.winfo_ismapped())
app.load_note(app.find_note(60)); app.update()
check('the banner switches to the series text on the series view',
      bool(app.occurrence_banner.winfo_ismapped())
      and 'edits here apply to the whole series' in app.occurrence_banner.cget('text'))

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

# Back to Calendar saves the pending edit of a day, to that day, asking
# nothing (a day opened on its own saves to itself).
app._open_note_from_calendar(app.find_note(60), '2026-07-16'); app.update()
scope_ux = []
app.ask_occurrence_scope = lambda *a, **k: (scope_ux.append(1), 'occurrence')[1]
app.body_text.insert('end', ' flushed-on-return')
app._return_to_calendar(); app.update()
check('Back to Calendar saves the pending edit to the day, asking nothing',
      scope_ux == []
      and 'flushed-on-return'
      in app.find_note(60)['overrides'].get('2026-07-16', {}).get('body', ''))
# The half the field found missing: the save must also NAVIGATE. A
# just-saved day used to still read as dirty (the base note's formatting
# never matches an override body), so the cancel guard blocked the trip
# and every further click re-asked.
check('...and actually lands on the calendar',
      app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
      and app._day_panel_mode != 'empty')
app._open_note_from_calendar(app.find_note(60), '2026-07-16'); app.update()
app._return_to_calendar(); app.update()
check('a clean day returns without asking either',
      scope_ux == []
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
check('the calendar menu drops generic Open/Edit for a recurring note, and '
      'names its two doors in the day panel\'s words',
      not any('Open / Edit' in l for l in _rec_labels)
      and any('Edit this day' in l for l in _rec_labels)
      and any('Edit the whole series' in l for l in _rec_labels))
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
# The card is a drawing on the list's canvas: right-clicked where it is.
_card_at = app._card_point(61)
if _card_at is not None and app.canvas.winfo_ismapped():
    _labels_q7.clear()
    tk.Menu.add_command = lambda self, **kw: _labels_q7.append(
        (kw.get('label', ''), kw.get('command')))
    tk.Menu.add_cascade = lambda self, **kw: _labels_q7.append(
        (kw.get('label', ''), None))
    tk.Menu.tk_popup = lambda self, *a, **k: None
    try:
        app.canvas.event_generate('<Button-3>', x=_card_at[0], y=_card_at[1])
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
# The marker POPUP's picking is deliberately untouched -- it works on a
# copy, writes only on Save and discards on ✕ -- and a check below holds
# that, so a later "consistency" pass does not helpfully break it. (Its
# Save with nothing left, the fourth door to the loss, has the Undo: 6g.)
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
    screen, not only in the store. Read from the month's drawing."""
    _cc_view = app._cal_cell_view(_CC_DAY)
    return _cc_view['bg'] if _cc_view else None


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

# The popup's picking was already safe. Hold that, so a later consistency
# pass does not helpfully give its chips an undo they do not need.
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
# "Edit the whole series", named in full: the Delete entry says "Delete the
# whole series" on the surfaces that open this menu without a date, and a
# substring match on "whole series" alone would one day pick up the wrong
# lambda -- an edit check that silently exercises a delete.
_series_cmd = next((c for l, c in _rec_items if 'Edit the whole series' in l), None)
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

# The day strip follows a day-to-day switch — the text must update even
# when the strip is already packed.
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()
app._ctx_open(app.find_note(60), '2026-07-16', return_day='2026-07-16')
app.update()
check('the day strip follows a day-to-day switch',
      '16 July 2026' in app.day_strip_lbl.cget('text'))

# Back to Calendar from an edited day: the day is saved to the day, asking
# nothing, and the trip completes. It once asked "this occurrence or the
# whole series?" here, and its Cancel aborted the trip; a day now saves to
# itself (save_current_note).
app._ctx_open(app.find_note(60), '2026-07-17', return_day='2026-07-17')
app.update()
app.body_text.insert('end', ' kept-on-the-day')
_scopeN = []
app.ask_occurrence_scope = lambda *a, **k: (_scopeN.append(1), None)[1]
app._return_to_calendar(); app.update()
check('Back to Calendar from an edited day saves it to the day, asking nothing, '
      'and completes the trip',
      _scopeN == []
      and app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
      and 'kept-on-the-day' in app.find_note(60)['overrides']['2026-07-17']['body']
      and 'kept-on-the-day' not in app.find_note(60).get('body', ''))
del app.ask_occurrence_scope
app.close_day_panel(); app.update()

# Deleting the open note ends the calendar trip — a pending that outlived
# a delete which REPLACED the editor once made a later, unrelated Save
# yank the user onto a stale calendar day.
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
# Deleting ANOTHER note used to end the trip as a side effect: the
# delete reloaded the editor from the copy taken when it was opened
# (the "tab-restore arm"), which also cleared the way back. That reload
# put older versions back over newer ones and is gone -- the editor now
# stays exactly as it was, still on this day, so the way back to the
# calendar still means what it did. Nothing about it is stale.
check('deleting another note leaves the open day and its way back alone',
      app.selected_note_id == 60
      and app.current_occurrence_date == '2026-07-18'
      and bool(app._pending_calendar_return)
      and app._is_placed(app.calendar_return_btn))

# A repeat turned off behind a day's back -- a day shows no repeat to change
# -- is put back by its save: the series goes on repeating, and the day
# stays a day, its strip and its words true. (When a day could end its
# series, the save retired the day's line instead, a day view of a note
# that no longer repeated being a lying label.)
app._ctx_open(app.find_note(60), '2026-07-19', return_day='2026-07-19')
app.update()
app.write_recurrence_to_ui({})
_scopeF = []
app.ask_occurrence_scope = lambda *a, **k: (_scopeF.append(1), 'series')[1]
app.save_current_note(auto=False); app.update()
check('a repeat turned off behind a day\'s back asks nothing',
      _scopeF == [])
check('...and is put back: the series still repeats, and the day stays a day',
      app.find_note(60)['recurrence']['freq'] == 'daily'
      and app.current_occurrence_date == '2026-07-19'
      and bool(app.day_strip.winfo_ismapped())
      and app.selected_freq_key() == 'daily')
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
check('the series banner says edits apply to the whole series',
      app.occurrence_banner.winfo_ismapped()
      and 'edits here apply to the whole series' in _btext)
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
# Who reaches for the Repeat control: an insertion once left "Make this
# repeat"'s last lines at the end of the reset, so the reset said "Set a
# repeat frequency" about a series and sent the keyboard to the hidden
# editor, while "Make this repeat" -- which promises both -- did neither.
_rs_focus = []
app.rec_freq_menu.focus_set = lambda: _rs_focus.append('rec_freq_menu')
try:
    if _reset_cmd is not None:
        _reset_cmd(); app.update()
    _rs_status = app.status_lbl.cget('text')
    _rs_reset_focus = list(_rs_focus)
    check('reset drops the override and the day shows series content',
          _reset_cmd is not None
          and '2026-07-15' not in (app.find_note(64).get('overrides') or {})
          and NO.effective_note(app.find_note(64),
                                '2026-07-15')['body'] == 'series body')
    check(f'...and says so, leaving the keyboard where it was ({_rs_status!r}, '
          f'{_rs_reset_focus})',
          _rs_status == 'This day follows the series again'
          and _rs_reset_focus == [])
    _rs_focus.clear()
    app.notes.append(NO.normalize_note({
        'id': 7302, 'title': 'Plain dated', 'body': 'x',
        'category': 'General', 'date': '2026-07-20'}))
    app.save_notes()
    app._ctx_make_recurring(app.find_note(7302), return_day='2026-07-20')
    app.update()
    check(f'"Make this repeat" puts the keyboard on the Repeat control, as it '
          f'promises ({app.status_lbl.cget("text")!r}, {_rs_focus})',
          _rs_focus == ['rec_freq_menu']
          and app.status_lbl.cget('text')
          == 'Set a repeat frequency to make this note recurring')
finally:
    del app.rec_freq_menu.focus_set
    app._pending_calendar_return = None
    app._update_calendar_return_button()
    app.notes = [n for n in app.notes if n.get('id') != 7302]
    app.save_notes()
    app.new_note()
    app.notebook.select(app.TAB_CALENDAR); app.update()
app.close_day_panel(); app.update()

# The sidebar filter isolates calendar notes — one judgment, used by
# the list render AND bulk select-all, exercised through the render.
app.filter_var.set(app.FILTER_REPEATING)
app.refresh_note_list(); app.update()
_vis = list_texts()
check('the Repeating filter shows only repeating notes',
      any('SeriesVis' in t for t in _vis)
      and not any('DatedVis' in t for t in _vis)
      and not any('PlainVis' in t for t in _vis))
app.filter_var.set(app.FILTER_DATED)
app.refresh_note_list(); app.update()
_vis = list_texts()
check('the Dated filter shows only dated non-repeating notes',
      any('DatedVis' in t for t in _vis)
      and not any('SeriesVis' in t for t in _vis)
      and not any('PlainVis' in t for t in _vis))

# "📎 With files": the notes whose card shows 📎×N, through the same one
# judgment -- so the list, Select all and a save agree on what it shows.
app.notes.append(NO.normalize_note({
    'id': 67, 'title': 'FilesVis', 'body': 'x', 'category': 'General',
    'attachments': [{'filename': 'plan.txt',
                     'stored_as': 'q7_files_plan.txt'}]}))
app.save_notes()
app.filter_var.set(app.FILTER_FILES)
app.refresh_note_list(); app.update()
_vis = list_texts()
check(f'the With files filter shows only the notes with a file ({_vis})',
      any('FilesVis' in t for t in _vis)
      and not any(other in t for t in _vis
                  for other in ('SeriesVis', 'DatedVis', 'PlainVis')))
app.selected_note_ids = set()
app._bulk_select_all(); app.update()
check(f'Select all under it takes those notes and no other '
      f'({sorted(app.selected_note_ids)})', app.selected_note_ids == {67})
app.selected_note_ids = set()
app._update_bulk_selected_label()
# Its last file taken off, the note leaves the list at the save, as a
# Dated note does when its date is cleared.
app.load_note(app.find_note(67)); app.update()
_wf_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
try:
    app.remove_attachment(0)
finally:
    app.ask_yes_no = _wf_ask
app._flush_autosave(); app.update()
check(f'a note whose last file is removed leaves the With files list '
      f'({list_texts()})',
      not app.find_note(67).get('attachments')
      and not any('FilesVis' in t for t in list_texts()))
app.new_note(); app.update()
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
_ordered = [n for t in list_texts()
            for n in _names_q7 if n in t]
# Weekly since 9 days ago -> occurrences at -9, -2, +5: the NEXT one
# (+5) sits AFTER A's date (+1) on purpose — ranked by start date
# instead (the dishonesty this sort replaces), B would wrongly lead.
check('Calendar-soonest ranks by the next relevant date from today',
      _ordered == ['SoonA', 'SoonB', 'SoonD', 'SoonC', 'SoonE'])

app.sort_var.set('Calendar: oldest')
app.refresh_note_list(); app.update()
_ordered = [n for t in list_texts()
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
         '2026-08-17': {'title': '', 'body': 'discussed the budget',
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
      not any('17.08.2026' in t for t in _hl))

app._history_toggle_group(80); app.update()
_hl = find_all_labels(app._history_rows)
check('expanding the group reveals its edited days, newest first',
      any('17.08.2026' in t for t in _hl)
      and any('15.06.2026' in t and 'HistSpecial' in t for t in _hl))
app._history_toggle_group(80); app.update()

# Search reaches into a day's own override content and auto-expands.
app._history_search_var.set('budget')
app.update(); import time as _t7; _t7.sleep(0.4); app.update()
_hl = find_all_labels(app._history_rows)
check('search finds override content and auto-expands its group',
      any('17.08.2026' in t for t in _hl)
      and not any('HistDated' in t for t in _hl))
app._history_search_var.set('')
app.update(); _t7.sleep(0.4); app.update()

# ---- A PASTE ONTO THIS SEARCH BOX'S PLACEHOLDER ----
# The check above drives the search through the VARIABLE, which steps over
# the widget entirely -- so it could never see that a right-click Paste
# landed glued to the placeholder: "Search all calendar entries...budget",
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
    app.clipboard_clear(); app.clipboard_append('budget'); app.update()
    _hist_entry.event_generate('<<Paste>>')
    app.update(); _t7.sleep(0.4); app.update()
    check('pasting into the History search replaces the placeholder',
          _hist_entry.get() == 'budget')
    # And the consequence, not just the contents: the query the user pasted
    # is the query that ran. The same hit the var-driven check above proved,
    # so a failure here is about the paste and not about the fixture.
    _hl = find_all_labels(app._history_rows)
    check('and the pasted query is the one the register searched for',
          any('17.08.2026' in t for t in _hl)
          and not any('HistDated' in t for t in _hl))
    # The control: a paste must not wipe a query someone typed.
    _hist_entry.delete(0, 'end')
    _hist_entry.insert(0, 'bud')
    _hist_entry.icursor('end')
    app.update()
    check('fixture: the History search holds real text, no placeholder',
          _hist_entry.get() == 'bud')
    app.clipboard_clear(); app.clipboard_append('get'); app.update()
    _hist_entry.event_generate('<<Paste>>')
    app.update(); _t7.sleep(0.4); app.update()
    check('a paste into a typed History query leaves that text alone',
          _hist_entry.get() == 'budget')
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
# A chip chosen while a typed search waits renders at once, and the
# waiting render is cancelled. Only forgotten, it stayed scheduled with
# nothing tracking it, rendered again on its own, and on firing forgot
# the next one the same way -- the relay qa1's "a save run directly"
# check describes for the autosave.
app._history_search_var.set('Hist')       # the typed search's render waits
_hs_before = _qa_waiting(app, '_render_calendar_history')
app._history_set_bucket('All')
_hs_after = _qa_waiting(app, '_render_calendar_history')
check(f'a History chip chosen while a typed search waits leaves no render '
      f'waiting ({_hs_before} -> {_hs_after})',
      len(_hs_before) == 1 and not _hs_after
      and app._history_search_job is None)
app._history_search_var.set('')
app.update(); _t7.sleep(0.4); app.update()

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


def _bulk_labels():
    out, todo = [], [app._history_rows]
    while todo:
        w = todo.pop(0)
        for c in w.winfo_children():
            if isinstance(c, tk.Label) and 'Bulk' in str(c.cget('text')):
                out.append(c)
            todo.append(c)
    return out


_bulk_first = _bulk_labels()
_more_btn.invoke(); app.update()
_bulk_shown = sum(1 for t in find_all_labels(app._history_rows) if 'Bulk' in t)
check('Show more brings the rest', _bulk_shown == 60)
# ...under the rows already drawn, which stay the same rows: drawing every
# row again flickered and grew with every page (field pass).
_bulk_after = _bulk_labels()
check('...added under the rows already there, not all drawn again',
      len(_bulk_first) == 50 and all(w.winfo_exists() for w in _bulk_first)
      and set(_bulk_first) <= set(_bulk_after)
      and bool(_bulk_after[-1].bind('<MouseWheel>'))
      and find_widget(app._history_rows, tk.Button, 'Show more') is None)
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

# Read from the month's drawing: a cell is shapes on its canvas now, and
# its outline is a rectangle drawn over its edge. A day that is not drawn
# -- a stale month left on screen -- reads as a view every check here
# fails on, so the suite reports it instead of stopping at a TypeError
# before its footer (a mutant that stopped drawing did exactly that).
_CD_NONE = {'box': (0, 0, 0, 0), 'bg': '', 'day': '', 'day_fill': '',
            'today': False, 'badge': '', 'badge_fill': '', 'dots': [],
            'more_dots': '', 'chips': [], 'chip_fill': [], 'more': '',
            'selected_width': -1, 'selected_colour': ''}


def _cd_view(date_str):
    return app._cal_cell_view(date_str) or _CD_NONE


def _cd_point(date_str, chip=None):
    """Where to point at a day or one of its titles; off the grid when
    it is not drawn, so a click there lands on nothing."""
    try:
        return app._cal_point(date_str, chip=chip) or (-50, -50)
    except (IndexError, KeyError):
        return (-50, -50)


def _cd_badge_ok(badge, marks):
    """A day's corner shows its first markers -- at most three, and only as
    many as fit beside the day's number -- and counts the rest ("⭐+2")."""
    return badge in {''.join(marks[:k]) + (f'+{len(marks) - k}' if len(marks) > k else '')
                     for k in range(0, min(3, len(marks)) + 1)}


_cell = _cd_view('2026-07-15')
check('opening a day draws the accent outline on its cell',
      _cell['selected_width'] == 2
      and _cell['selected_colour'] == app.colors['accent'])
check('the other days carry no outline',
      _cd_view('2026-07-10')['selected_width'] == 0)
app.render_calendar(); app.update()
check('the outline survives a grid re-render',
      _cd_view('2026-07-15')['selected_width'] == 2)
app.close_day_panel(); app.update()
check('closing the panel clears the outline',
      _cd_view('2026-07-15')['selected_width'] == 0)

# ---- THE MONTH IS ONE DRAWING ----
# The grid was built of widgets -- a Frame per day, a Label per number, dot
# and title, a Frame per divider: 216 windows for a month holding 46 notes,
# each placed and painted again at every step of a window resize.
# It is shapes and text on one canvas now, laid out as the widgets were
# (measured on them), and these checks read the drawing back.
_cd_markers4 = [e for e, _c in app.DAY_MARKER_EMOJIS[:4]]
_cd_markers2 = [e for e, _c in app.DAY_MARKER_EMOJIS[:2]]
app.notes = [
    {'id': 95, 'title': 'Dentist appointment at the clinic', 'body': 'x',
     'category': 'General', 'date': '2026-07-08'},
    {'id': 96, 'title': 'Short', 'body': 'x', 'category': 'General',
     'date': '2026-07-08'},
    {'id': 97, 'title': 'Third', 'body': 'x', 'category': 'General',
     'date': '2026-07-08', 'color': '#2a9d8f'},
    {'id': 98, 'title': 'Alone', 'body': 'x', 'category': 'General',
     'date': '2026-07-17'},
]
app.notes = [NO.normalize_note(n) for n in app.notes]
app.save_notes()
app.day_colors = {'2026-07-17': '#e76f51'}
app._persist_day_colors()
app.day_emoji = {'2026-07-17': list(_cd_markers4), '2026-07-11': list(_cd_markers2)}
app._persist_day_emoji()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
check('the month is one drawing: the grid holds one canvas, and no widget per day',
      app.cal_grid_frame.winfo_children() == [app.cal_canvas]
      and len(app._cal_cells) == 31)
_cd8 = _cd_view('2026-07-08')
check(f'a busy day shows a dot per colour, two titles and "+1 more" '
      f'({_cd8["dots"]}, {_cd8["chips"]}, {_cd8["more"]!r})',
      len(_cd8['dots']) == 2 and _cd8['dots'][1] == '#2a9d8f'
      and len(_cd8['chips']) == 2
      and _cd8['chips'][1] == 'Short' and _cd8['more'] == '+1 more')
_cd17 = _cd_view('2026-07-17')
# Near-black, not white: white read at 3.3:1 on this paint, near-black at
# 5.3:1, and the letters for a picked colour are the ones that read best.
check('a painted day wears its colour, with its text in the near-black that reads on it',
      _cd17['bg'] == '#e76f51' and _cd17['day_fill'] == '#1a1a1a'
      and _cd17['chip_fill'] == ['#1a1a1a'])
# At most three, and only as many as fit beside the day's number -- the
# rest counted (6g holds the cap at a width where all three fit).
check(f'four markers show as the first that fit, the rest counted '
      f'({_cd17["badge"]!r})', _cd_badge_ok(_cd17['badge'], _cd_markers4)
      and _cd17['badge'] != ''.join(_cd_markers4))
# The markers were drawn in a Label's default colour -- black -- so on a
# dark theme's day they all but disappeared. The day's own text colour.
_cd11 = _cd_view('2026-07-11')
check(f"a day's markers are drawn in its own text colour, not black "
      f"({_cd11['badge_fill']}, {_cd17['badge_fill']})",
      _cd11['badge_fill'] == app.colors['text']
      and _cd17['badge_fill'] == '#1a1a1a')
# Rows are as tall as the busiest day needs, as the widget grid's were
# (its rows asked their cells), and all alike.
_cd_heights = sorted({_cd_view(d)['box'][3] - _cd_view(d)['box'][1]
                      for d in app._cal_cells})
check(f'every week row is as tall as the busiest day needs, and all alike '
      f'({_cd_heights})', len(_cd_heights) == 1 and _cd_heights[0] > 84)
# Every day's number, dots and titles sit inside its own cell.
_cd_outside = []
for _cd_d, _cd_rec in app._cal_cells.items():
    _cd_x0, _cd_y0, _cd_x1, _cd_y1 = _cd_rec['x0'], _cd_rec['y0'], _cd_rec['x1'], _cd_rec['y1']
    for _cd_item in app.cal_canvas.find_withtag(_cd_rec['tag']):
        _cd_b = app.cal_canvas.bbox(_cd_item)
        if _cd_b and not (_cd_x0 - 1 <= _cd_b[0] and _cd_b[2] <= _cd_x1 + 1
                          and _cd_y0 - 1 <= _cd_b[1] and _cd_b[3] <= _cd_y1 + 1):
            _cd_outside.append(_cd_d)
check(f'everything a day draws sits inside its own cell ({sorted(set(_cd_outside))})',
      not _cd_outside)

# A new width lays the month out again from what was worked out -- the
# notes are not gone through again for a change of size -- and the open
# day keeps its outline through it.
app.open_day_popup('2026-07-08'); app.update()
_cd_renders = []
_cd_real_render = app.render_calendar
app.render_calendar = lambda: (_cd_renders.append(1), _cd_real_render())[1]
try:
    _cd_w = app.winfo_width()
    _cd_new = _cd_w + (60 if _cd_w >= 1150 else -60)
    app.geometry('%dx%d' % (_cd_new, app.winfo_height()))
    for _ in range(5):
        app.update(); time.sleep(0.02)
    _cd_right = max((r['x1'] for r in app._cal_cells.values()), default=0)
    check(f'a new width draws the month to fit it '
          f'(right edge {_cd_right}, canvas {app.cal_canvas.winfo_width()})',
          abs(_cd_right - (app.cal_canvas.winfo_width() - app.CAL_CELL_PAD)) <= 1)
    check(f'...without working the notes out again ({len(_cd_renders)} renders)',
          not _cd_renders)
    check('...and the open day keeps its outline',
          _cd_view('2026-07-08')['selected_width'] == 2)
finally:
    app.__dict__.pop('render_calendar', None)
    app.geometry('%dx%d' % (_cd_w, app.winfo_height()))
    for _ in range(5):
        app.update(); time.sleep(0.02)
app.close_day_panel(); app.update()

# Hovering: a title previews its note, the rest of a busy day summarises
# the day, an empty day says nothing; the hand over a day, the plain
# pointer over the gap between two. Real <Motion> events on the canvas,
# the answers recorded where the app gives them.
_cd_hover = []
app.show_note_hover_preview = lambda n, d: _cd_hover.append(('note', n['id'], d))
app.show_day_summary_tooltip = lambda d: _cd_hover.append(('day', d))
try:
    for _cd_at in (_cd_point('2026-07-08', chip=0), _cd_point('2026-07-08'),
                   _cd_point('2026-07-09')):
        _qa_fire(app.cal_canvas, '<Motion>', x=_cd_at[0], y=_cd_at[1])
        app.update()
    _cd_hand = str(app.cal_canvas.cget('cursor'))
    _cd8_box = _cd_view('2026-07-08')['box']
    _qa_fire(app.cal_canvas, '<Motion>', x=_cd8_box[2] + app.CAL_CELL_PAD,
             y=(_cd8_box[1] + _cd8_box[3]) // 2)
    app.update()
    _cd_plain = str(app.cal_canvas.cget('cursor'))
finally:
    for _cd_attr in ('show_note_hover_preview', 'show_day_summary_tooltip'):
        app.__dict__.pop(_cd_attr, None)
    app.hide_day_tooltip()
check(f'hovering a title previews that note, the rest of a busy day '
      f'summarises it, an empty day says nothing ({_cd_hover})',
      _cd_hover == [('note', 95, '2026-07-08'), ('day', '2026-07-08')])
check(f'...and the pointer is a hand over a day and plain between days '
      f'({_cd_hand!r}, {_cd_plain!r})', _cd_hand == 'hand2' and _cd_plain == '')

# A click on a day's cell, away from its titles, opens the day.
_cd_at = _cd_point('2026-07-08')
_qa_click(app.cal_canvas, x=_cd_at[0], y=_cd_at[1])
app.update()
check('a click on a day opens its list, not one of its notes',
      app.selected_day == '2026-07-08' and app._day_panel_mode == 'list')
# Its header writes the day out day first, as every date in the app is.
_cd_head = [t for t in find_all_labels(app.day_panel) if '2026' in t]
check(f'the day\'s list names the day day first ({_cd_head[:1]})',
      any('Wednesday, 8 July 2026' in t for t in _cd_head))
app.close_day_panel(); app.update()

# Markers saved from the popup change that one day's corner, without the
# month being drawn again.
_cd_renders = []
app.render_calendar = lambda: (_cd_renders.append(1), _cd_real_render())[1]
try:
    app._mark_day_emoji('2026-07-12'); app.update()
    _cd_pop = app._mini_popup

    def _cd_labels(w, acc):
        for ch in w.winfo_children():
            if isinstance(ch, tk.Label):
                acc.append(ch)
            _cd_labels(ch, acc)
        return acc

    _cd_pick = [w for w in _cd_labels(_cd_pop, [])
                if str(w.cget('text')) in _cd_markers2][:2]
    for _cd_w_chip in _cd_pick:
        _qa_click(_cd_w_chip)
        app.update()
    _cd_save = find_widget(_cd_pop, tk.Button, 'Save')
    if _cd_save is not None:
        _cd_save.invoke()
        app.update()
finally:
    app.__dict__.pop('render_calendar', None)
check(f"saved markers show in that day's corner, without a redraw of the "
      f"month ({_cd_view('2026-07-12')['badge']!r}, "
      f"{len(_cd_renders)} renders)",
      len(_cd_pick) == 2 and not _cd_renders
      and _cd_view('2026-07-12')['badge'] == ''.join(_cd_markers2))

# Today wears the accent bar, and only today.
app.go_to_today(); app.update()
_cd_today = __import__('datetime').date.today().strftime('%Y-%m-%d')
check('today wears the accent bar, and only today',
      _cd_view(_cd_today)['today']
      and sum(1 for d in app._cal_cells if _cd_view(d)['today']) == 1)

# Everything in the drawing is painted in the colours of the moment it was
# drawn, so a theme switch has to draw the month again: with the calendar
# on screen, and from Settings, where the switch is made with the month out
# of sight and caught up on the way back.
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
_cd_theme_was = app.theme_name
app.set_theme('light' if _cd_theme_was != 'light' else 'dark'); app.update()
_cd_v = _cd_view('2026-07-09')
check(f'a theme switch draws the month in the new colours '
      f'({_cd_v["bg"]}, {_cd_v["day_fill"]})',
      _cd_v['bg'] == app.colors['card'] and _cd_v['day_fill'] == app.colors['text']
      and _cd_v['chip_fill'] == [] and _cd_view('2026-07-08')['chip_fill']
      == [app.colors['text']] * 2)
app.show_settings_page(); app.update()
app.set_theme(_cd_theme_was); app.update()
app.hide_settings_page(); app.update()
_cd_v = _cd_view('2026-07-09')
check(f'...and one made in Settings is drawn on the way back '
      f'({_cd_v["bg"]}, {_cd_v["day_fill"]})',
      app.theme_name == _cd_theme_was
      and _cd_v['bg'] == app.colors['card'] and _cd_v['day_fill'] == app.colors['text'])
app.day_colors = {}
app._persist_day_colors()
app.day_emoji = {}
app._persist_day_emoji()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()

# ---- WHAT SHOULD BE HIDDEN STAYS HIDDEN ----
# Show/hide decisions asked Tk whether a widget was MAPPED -- on the screen
# -- and a widget is not, for as long as its page is hidden. The editor
# sleeps while the Calendar is showing, so a note opened from there with
# "Open in editor" found the last note's Restore previous, title counter
# and share code still in place: "hide it if it shows" had read them as
# hidden already, and they woke up with the page. A person's route: the
# note with all three open, the Calendar, a day, the other note's "Open in
# editor". The same switch made from the list, where the editor never
# sleeps, is the control.
_hp_day = '2026-07-21'
app.notes = [NO.normalize_note(n) for n in (
    {'id': 101, 'title': 'L' * (app.TITLE_MAX_LEN - 3), 'body': 'updated',
     'category': 'General', '_prev': {'body': 'as it was before the update'}},
    {'id': 102, 'title': 'Nothing to restore', 'body': 'x',
     'category': 'General', 'date': _hp_day},
)]
app.save_notes()


def _hp_placed():
    return {'restore': app._is_placed(app.restore_prev_btn),
            'counter': app._is_placed(app.title_count_lbl),
            'code': app._is_placed(app.editor_code_area)}


def _hp_open_the_long_note_with_its_code():
    app.notebook.select(app.TAB_NOTES); app.update()
    app.open_note_in_tab(app.find_note(101)); app.update()
    app.share_current_note_as_code(); app.update()
    return _hp_placed()


_hp_before = _hp_open_the_long_note_with_its_code()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
app.open_day_popup(_hp_day); app.update()
app.show_day_note(app.find_note(102), _hp_day); app.update()
_hp_btn = find_widget(app.day_panel, tk.Button, 'Open in editor')
if _hp_btn is not None:
    _hp_btn.invoke()
for _ in range(3):
    app.update_idletasks(); app.update()
_hp_after = _hp_placed()
check(f"a note opened from the calendar does not keep the last note's "
      f"Restore previous, title counter or share code "
      f"({_hp_before} -> {_hp_after})",
      _hp_btn is not None and app.selected_note_id == 102
      and all(_hp_before.values()) and not any(_hp_after.values()))
_hp_before = _hp_open_the_long_note_with_its_code()
app.open_note_in_tab(app.find_note(102)); app.update()
check(f'...as the same switch made from the list never did ({_hp_placed()})',
      all(_hp_before.values()) and not any(_hp_placed().values()))
# Back to the calendar with no day open, as the blocks below expect.
app.close_day_panel()
app.notebook.select(app.TAB_CALENDAR); app.update()

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
      any(t.startswith('✎ 01.07.2026') and 'MidRun' in t for t in _hl)
      and any(t.startswith('• 01.08.2026') for t in _hl)
      and any(t.startswith('• 01.06.2026') for t in _hl))
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
# 6g. THE CALENDAR AFTER THE "BREAK IT" AUDIT
# ============================================================

# ---- A HISTORY ROW NEVER RE-DATES THE NOTE IN THE EDITOR ----
# A row's landing ended with the tail of _add_note_for_date -- the new
# note's date prefill, left behind by an insertion -- so it wrote the row's
# date into whatever note the editor held, and the next flush saved it
# without a word: a dated note moved to the row's day, a series moved its
# start (and its weekday), an undated note landed on the calendar. The
# landing check above runs after the notes were replaced, when the editor's
# note no longer exists and the flush has nothing to save, so it could
# never see it. A person's route: a note open in the editor (the app
# reopens the last one at startup), Calendar -> History -> a row, then on
# as usual: another note opened, or the window closed.
_hr_notes = [
    {'id': 120, 'title': 'Dentist', 'body': 'x', 'category': 'General',
     'date': '2026-03-10'},
    {'id': 121, 'title': 'Holiday flight', 'body': 'x', 'category': 'General',
     'date': '2025-11-20'},
    {'id': 122, 'title': 'Daily walk', 'body': 'x', 'category': 'General',
     'date': '2026-07-01', 'recurrence': {'freq': 'daily'}},
    {'id': 123, 'title': 'Groceries', 'body': 'x', 'category': 'General'},
]
_hr_asked = []


def _hr_reset():
    app.notes = [NO.normalize_note(dict(n)) for n in _hr_notes]
    app.save_notes()
    app.refresh_note_list(); app.update()


def _hr_disk_date(note_id):
    # Its own imports: the io/json aliases this first borrowed came from
    # the copied seed block, which is one call to _qa_support now.
    import io as _hr_io, json as _hr_json
    with _hr_io.open(NO.DATA_FILE, encoding='utf-8') as _hr_fh:
        for _hr_n in _hr_json.load(_hr_fh):
            if _hr_n.get('id') == note_id:
                return _hr_n.get('date', '')
    return None


def _hr_open_from_the_list(note_id, date_str):
    app.notebook.select(app.TAB_NOTES); app.update()
    app.open_note_in_tab(app.find_note(note_id)); app.update()
    # The field shows the stored date as every date is shown, day first,
    # and an undated note's field shows its form.
    return (app.selected_note_id == note_id
            and app.date_entry.get() == (NO.show_date(date_str)
                                         or NO.DATE_FORM))


def _hr_open_one_day_of_the_walk():
    """One day of the series, opened as a person opens it: its title in the
    month, then the panel's "Edit this day"."""
    app.notebook.select(app.TAB_CALENDAR); app.update()
    app.cal_year, app.cal_month = 2026, 7
    app.render_calendar(); app.update()
    _hr_at = _cd_point('2026-07-10', chip=0)
    _qa_click(app.cal_canvas, x=_hr_at[0], y=_hr_at[1]); app.update()
    _hr_btn = find_widget(app.day_panel, tk.Button, 'Edit this day')
    if _hr_btn is not None:
        _hr_btn.invoke(); app.update()
    return (app.selected_note_id == 122
            and app.current_occurrence_date == '2026-07-10'
            and app.date_entry.get() == '01.07.2026')


def _hr_click_the_row(title):
    """Calendar -> History -> the row, clicked where a person clicks it."""
    app.notebook.select(app.TAB_CALENDAR); app.update()
    if not app._history_visible:
        app._history_toggle_btn.invoke(); app.update()
    for _hr_row in app._history_rows.winfo_children():
        for _hr_lbl in _hr_row.winfo_children():
            if (isinstance(_hr_lbl, tk.Label)
                    and title in str(_hr_lbl.cget('text'))):
                _qa_click(_hr_lbl); app.update()
                return True
    return False


def _hr_close_the_window():
    """on_app_close with destroy stood in for, as the Cancel checks below
    do, so the rest of the file still has a window."""
    _hr_closed = []
    app.destroy = lambda: _hr_closed.append(1)
    try:
        app.on_app_close(); app.update()
    finally:
        del app.destroy
    return bool(_hr_closed)


# Answered and recorded, never shown: with nothing edited, nothing may ask.
app.ask_occurrence_scope = lambda *a, **k: (_hr_asked.append(a), 'series')[1]
try:
    for _hr_what, _hr_open, _hr_id, _hr_date, _hr_other in (
            ('a dated note', lambda: _hr_open_from_the_list(120, '2026-03-10'),
             120, '2026-03-10', 123),
            ('one day of a series', _hr_open_one_day_of_the_walk,
             122, '2026-07-01', 123),
            ('an undated note', lambda: _hr_open_from_the_list(123, ''),
             123, '', 120)):
        for _hr_then in ('another note is opened', 'the window is closed'):
            _hr_reset()
            del _hr_asked[:]
            _hr_ready = _hr_open()
            _hr_clicked = _hr_click_the_row('Holiday flight')
            _hr_landed = (app.selected_day == '2025-11-20'
                          and app._day_panel_mode == 'note')
            _hr_field = app.date_entry.get()
            if _hr_then == 'another note is opened':
                app.notebook.select(app.TAB_NOTES); app.update()
                app.open_note_in_tab(app.find_note(_hr_other)); app.update()
                _hr_went = app.selected_note_id == _hr_other
            else:
                _hr_went = _hr_close_the_window()
            _hr_stored = _hr_disk_date(_hr_id)
            check(f'fixture: {_hr_what} is in the editor, its History row click '
                  f'lands on the row\'s day, and {_hr_then} ({_hr_ready}, '
                  f'{_hr_clicked}, {app.selected_day}, {_hr_went})',
                  _hr_ready and _hr_clicked and _hr_landed and _hr_went)
            check(f'a History row leaves the date of {_hr_what} in the editor '
                  f'alone, and on disk once {_hr_then} (field {_hr_field!r}, '
                  f'disk {_hr_stored!r}, questions {len(_hr_asked)})',
                  _hr_field == (NO.show_date(_hr_date) or NO.DATE_FORM)
                  and _hr_stored == _hr_date and not _hr_asked)
finally:
    del app.ask_occurrence_scope
if app._history_visible:
    app._hide_calendar_history()
app.close_day_panel()
app.notebook.select(app.TAB_NOTES); app.update()


def _cal_button(text):
    """A header button by its exact label ('▶' is inside '▶▶' too)."""
    _stack = [app.notebook]
    while _stack:
        _w = _stack.pop()
        if isinstance(_w, tk.Button) and str(_w.cget('text')) == text:
            return _w
        _stack.extend(_w.winfo_children())
    return None


# ---- DECEMBER 9999 DRAWS, WHATEVER REPEATS ----
# The month picker and the arrows both go up to year 9999, and the walk
# over a repeating note's days took its next step before comparing it with
# the horizon: from 9999-12-31 that step is past the last date there is.
# With any daily, weekly or monthly note the month raised instead of
# drawing -- December's title over November's days, a click on them
# opening November -- and History raised on a "10 times" series dated in
# the 9900s. Reached here by the real ▶, with an error recorder standing
# where the crash toast would be.
_eot_errors = []
app.report_callback_exception = (
    lambda _t, _v, _tb: _eot_errors.append('%s: %s' % (_t.__name__, _v)))
try:
    app.notes = [NO.normalize_note(n) for n in (
        {'id': 130, 'title': 'EotDaily', 'body': 'x', 'category': 'General',
         'date': '2026-01-01', 'recurrence': {'freq': 'daily'}},
        {'id': 131, 'title': 'EotFriday', 'body': 'x', 'category': 'General',
         'date': '2026-01-09', 'recurrence': {'freq': 'weekly'}},
        {'id': 132, 'title': 'EotWeekend', 'body': 'x', 'category': 'General',
         'date': '2026-01-03',
         'recurrence': {'freq': 'weekly', 'weekdays': [5, 6]}},
        {'id': 133, 'title': 'EotMonthEnd', 'body': 'x', 'category': 'General',
         'date': '2026-01-31', 'recurrence': {'freq': 'monthly'}},
        {'id': 134, 'title': 'EotYearly', 'body': 'x', 'category': 'General',
         'date': '2026-12-31', 'recurrence': {'freq': 'yearly'}},
        {'id': 135, 'title': 'EotTenTimes', 'body': 'x', 'category': 'General',
         'date': '9950-06-01',
         'recurrence': {'freq': 'monthly', 'count': 10}},
    )]
    app.save_notes()
    app.notebook.select(app.TAB_CALENDAR); app.update()
    app.cal_year, app.cal_month = 9999, 11
    app.render_calendar(); app.update()
    _eot_next = _cal_button('▶')
    if _eot_next is not None:
        _eot_next.invoke(); app.update()
    _eot_days = sorted(app._cal_cells)
    _eot_by_date = (app._cal_month_data or {}).get('notes_by_date', {})

    def _eot_titles(day):
        return [n['title'] for n in _eot_by_date.get(day, [])]

    check(f'▶ into December 9999 draws December under its own title '
          f'({app.cal_month_lbl.cget("text")!r}, {_eot_days[:1]}..{_eot_days[-1:]}, '
          f'errors {_eot_errors})',
          _eot_next is not None and not _eot_errors
          and app.cal_month_lbl.cget('text') == 'December 9999  ⌄'
          and _eot_days == ['9999-12-%02d' % d for d in range(1, 32)])
    check(f"...with every repeating note on its days, to the very last one "
          f"({_eot_titles('9999-12-31')}, {_eot_titles('9999-12-26')})",
          _eot_titles('9999-12-31')
          == ['EotDaily', 'EotFriday', 'EotMonthEnd', 'EotYearly']
          and _eot_titles('9999-12-25') == ['EotDaily', 'EotWeekend']
          and _eot_titles('9999-12-26') == ['EotDaily', 'EotWeekend'])
    if _eot_next is not None:
        _eot_next.invoke(); app.update()
    check(f'...and ▶ on the last month stays there, quietly ({_eot_errors})',
          not _eot_errors and (app.cal_year, app.cal_month) == (9999, 12)
          and app.cal_month_lbl.cget('text') == 'December 9999  ⌄')
    app._history_toggle_btn.invoke(); app.update()
    _eot_rows = find_all_labels(app._history_rows)
    check(f'History opens with a "10 times" series dated in the 9900s '
          f'({[t for t in _eot_rows if "Eot" in t][:3]}, errors {_eot_errors})',
          not _eot_errors
          and any('EotTenTimes' in t and '10 occurrences' in t for t in _eot_rows))
    app._history_toggle_btn.invoke(); app.update()

    # Should a month's notes ever fail to be worked out, the title stays
    # with the days drawn under it: the month is worked out first, and only
    # then are the title and the month's record changed.
    import noteorganizer.ui.calendar_view as _eot_cv
    _eot_real_expand = _eot_cv.expand_occurrences

    def _eot_broken_expand(*_a, **_k):
        raise ValueError('a month that cannot be worked out')

    del _eot_errors[:]
    _eot_cv.expand_occurrences = _eot_broken_expand
    try:
        _eot_prev = _cal_button('◀')
        if _eot_prev is not None:
            _eot_prev.invoke(); app.update()
    finally:
        _eot_cv.expand_occurrences = _eot_real_expand
    _eot_title = str(app.cal_month_lbl.cget('text'))
    _eot_drawn = sorted(app._cal_cells)
    check(f'...and when a month cannot be worked out, the title still names '
          f'the days drawn under it ({_eot_title!r}, {_eot_drawn[:1]}, '
          f'{len(_eot_errors)} error)',
          len(_eot_errors) == 1 and _eot_title == 'December 9999  ⌄'
          and _eot_drawn[:1] == ['9999-12-01'])
finally:
    del app.report_callback_exception
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
app.notebook.select(app.TAB_NOTES); app.update()

# ---- THE OPEN DAY FOLLOWS EVERY REDRAW OF THE CALENDAR ----
# The day's panel was drawn from the notes when the day opened, and only
# some routes drew it again: Undo after a delete from the panel put the
# note back on the grid while the open list went on without it. The undos
# redraw the month, as every change to the notes does, so render_calendar
# now draws the open day again whenever what it shows has changed -- and
# only then, which paging past it proves.
_od_day = '2026-07-08'
_od_notes = [
    {'id': 140, 'title': 'OdDentist', 'body': 'x', 'category': 'General',
     'date': _od_day},
    {'id': 141, 'title': 'OdWalk', 'body': 'x', 'category': 'General',
     'date': '2026-07-01', 'recurrence': {'freq': 'daily'}},
]


def _od_reset():
    app.notes = [NO.normalize_note(dict(n)) for n in _od_notes]
    app.save_notes()
    app.refresh_note_list()
    app.notebook.select(app.TAB_CALENDAR); app.update()
    app.cal_year, app.cal_month = 2026, 7
    app.render_calendar(); app.update()


def _od_panel_texts():
    return find_all_labels(app.day_panel)


def _od_open_chip(day, index=0):
    app.notebook.select(app.TAB_CALENDAR); app.update()
    _at = _cd_point(day, chip=index)
    _qa_click(app.cal_canvas, x=_at[0], y=_at[1]); app.update()


def _od_open_day(day):
    app.notebook.select(app.TAB_CALENDAR); app.update()
    _at = _cd_point(day)
    _qa_click(app.cal_canvas, x=_at[0], y=_at[1]); app.update()


# Undo after a delete from the open note: the list shows the note again.
_od_reset()
_od_open_chip(_od_day, 0)
_od_ready = app._day_panel_mode == 'note' and 'OdDentist' in _od_panel_texts()
_od_del = find_widget(app.day_panel, tk.Button, 'Delete')
if _od_del is not None:
    _od_del.invoke(); app.update()
_od_gone = not any('OdDentist' in t for t in _od_panel_texts())
_qa_click(app.toast_action_lbl); app.update()
check(f"Undo after a delete from the day's panel shows the note in the open "
      f"list again, as on the grid ({_od_ready}, {_od_gone}, "
      f"{[t for t in _od_panel_texts() if 'Od' in t]}, "
      f"{_cd_view(_od_day)['chips']})",
      _od_ready and _od_del is not None and _od_gone
      and app._day_panel_mode == 'list' and app.selected_day == _od_day
      and any('OdDentist' in t for t in _od_panel_texts())
      and any('OdDentist' in t for t in _cd_view(_od_day)['chips']))

# ...and after "this occurrence only" and its Undo, the day's series.
_od_reset()
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
try:
    _od_open_chip('2026-07-15', 0)
    _od_ready = app._day_panel_mode == 'note' and 'OdWalk' in _od_panel_texts()
    _od_del = find_widget(app.day_panel, tk.Button, 'Delete')
    if _od_del is not None:
        _od_del.invoke(); app.update()
    _od_gone = any('No notes for this day yet.' in t for t in _od_panel_texts())
    _qa_click(app.toast_action_lbl); app.update()
finally:
    del app.ask_occurrence_scope
check(f"...and Undo after removing one day of a series shows that day's "
      f"list with the series again ({_od_ready}, {_od_gone}, "
      f"{[t for t in _od_panel_texts() if 'Od' in t or 'No notes' in t]})",
      _od_ready and _od_gone and app.selected_day == '2026-07-15'
      and any('OdWalk' in t for t in _od_panel_texts())
      and not any('No notes for this day yet.' in t for t in _od_panel_texts()))

# Paging past an open day draws nothing new in it: the same widgets stay.
_od_reset()
_od_open_day(_od_day)
_od_before = list(app.day_panel.winfo_children())
for _od_label in ('▶', '◀'):
    _od_btn = _cal_button(_od_label)
    if _od_btn is not None:
        _od_btn.invoke(); app.update()
check(f'paging the months with a day open leaves its panel as it was '
      f'({len(_od_before)} widgets, same: '
      f'{list(app.day_panel.winfo_children()) == _od_before})',
      _od_before and list(app.day_panel.winfo_children()) == _od_before
      and (app.cal_year, app.cal_month) == (2026, 7)
      and app.selected_day == _od_day and app._day_panel_mode == 'list')

# ---- A CATEGORY CHANGE REPAINTS THE CALENDAR ----
# A note with no colour of its own is drawn in its category's. Three routes
# change a category and never asked the calendar to redraw -- a title's own
# menu, the selection bar, and that change's Undo, beside which a comment
# said the calendar never reads a category -- so the dots and an open
# day's stripe stayed in the old colour until the month was paged.
# A category whose colour is not General's, so a stale dot can be told
# from a fresh one.
_od_cat = next(c for c, col in NO.CATEGORY_COLORS.items()
               if c != 'General' and col != NO.CATEGORY_COLORS['General'])
_od_gen, _od_new = NO.CATEGORY_COLORS['General'], NO.CATEGORY_COLORS[_od_cat]


def _od_stripes():
    """The open list's stripes, row by row: the 4-pixel frame in each row."""
    out, level = [], [app.day_panel]
    while level:
        nxt = []
        for w in level:
            for c in w.winfo_children():
                if isinstance(c, tk.Frame):
                    try:
                        if int(str(c.cget('width'))) == 4:
                            out.append(str(c.cget('bg')))
                    except (tk.TclError, ValueError):
                        pass
                nxt.append(c)
        level = nxt
    return out


_od_reset()
_od_open_day(_od_day)
_od_caught = []
_od_real_add, _od_real_pop = tk.Menu.add_command, tk.Menu.tk_popup
tk.Menu.add_command = lambda self, **kw: _od_caught.append(
    (str(kw.get('label', '')), kw.get('command')))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    _at = _cd_point(_od_day, chip=0)
    _qa_fire(app.cal_canvas, '<Button-3>', x=_at[0], y=_at[1],
             rootx=app.cal_canvas.winfo_rootx() + _at[0],
             rooty=app.cal_canvas.winfo_rooty() + _at[1])
    app.update()
finally:
    tk.Menu.add_command = _od_real_add
    tk.Menu.tk_popup = _od_real_pop
_od_move = next((c for l, c in _od_caught if l.strip() == _od_cat), None)
if _od_move is not None:
    _od_move(); app.update()
check(f"a category moved from a title's menu recolours its dot and the open "
      f"list's stripe ({_od_cat}: {_cd_view(_od_day)['dots']}, {_od_stripes()})",
      _od_move is not None and app.find_note(140)['category'] == _od_cat
      and _cd_view(_od_day)['dots'] == [_od_new, _od_gen]
      and _od_stripes() == [_od_new, _od_gen])

# From the selection bar, with the day open; then that change's Undo.
_od_reset()
_od_open_day(_od_day)
app.notebook.select(app.TAB_NOTES); app.update()
app._toggle_selection_mode()
app._toggle_note_selected(140, True)
app.update()
app._bulk_change_category()
app.update()
_od_lbl = find_widget(app._mini_popup, tk.Label, _od_cat)
for _ in range(60):
    if app.find_note(140)['category'] == _od_cat:
        break
    try:
        if _od_lbl is not None and _od_lbl.winfo_exists():
            _qa_click(_od_lbl)
    except tk.TclError:
        pass
    app.update()
    _t7.sleep(0.02)
_od_undo = app._toast_action
app.notebook.select(app.TAB_CALENDAR); app.update()
check(f"a category moved from the selection bar shows on the calendar and in "
      f"the open list ({_cd_view(_od_day)['dots']}, {_od_stripes()})",
      app.find_note(140)['category'] == _od_cat
      and _cd_view(_od_day)['dots'] == [_od_new, _od_gen]
      and _od_stripes() == [_od_new, _od_gen])
if _od_undo is not None:
    _od_undo(); app.update()
check(f"...and its Undo puts the old colour back on both "
      f"({_cd_view(_od_day)['dots']}, {_od_stripes()})",
      _od_undo is not None and app.find_note(140)['category'] == 'General'
      and _cd_view(_od_day)['dots'] == [_od_gen]
      and _od_stripes() == [_od_gen, _od_gen])
if app.selection_mode:
    app._toggle_selection_mode()

# ---- A THEME SWITCH LEAVES EACH NOTE ITS OWN COLOUR ----
# The straggler pass swaps any colour equal to another theme's palette
# entry, and cannot tell a note's own colour from one: the open day's
# stripes in the colours the theme being left also uses -- its accent
# (General's), its danger (Urgent's), its success -- came back as the new
# theme's. The list is drawn again from the notes after that pass, as the
# note list's cards are. The notes' colours are set outright: the default
# categories' colours no longer match any theme's, so a fixture leaning on
# that coincidence would test nothing.
_od_theme_was = app.theme_name
app.set_theme('dark'); app.update()
_od_dark, _od_ocean = NO.THEMES['dark'], NO.THEMES['dark_ocean']
_od_keys = ('accent', 'danger_text', 'success')
app.notes = [NO.normalize_note(n) for n in (
    {'id': 142, 'title': 'OdAccent', 'body': 'x', 'category': 'General',
     'date': '2026-07-09', 'color': _od_dark['accent']},
    {'id': 143, 'title': 'OdDanger', 'body': 'x', 'category': 'Urgent',
     'date': '2026-07-09', 'color': _od_dark['danger_text']},
    {'id': 144, 'title': 'OdOwn', 'body': 'x', 'category': 'General',
     'date': '2026-07-09', 'color': _od_dark['success']},
)]
app.save_notes()
app.refresh_note_list()
_od_open_day('2026-07-09')
_od_want = [app.get_note_color(n) for n in app.notes]
check(f'fixture: the stripes wear colours the dark theme also uses, which '
      f'Ocean Blue does not ({_od_stripes()})',
      _od_stripes() == _od_want
      and _od_want == [_od_dark[k] for k in _od_keys]
      and all(_od_dark[k] != _od_ocean[k] for k in _od_keys))
app.show_settings_page(); app.update()
app.set_theme('dark_ocean'); app.update()
app.hide_settings_page(); app.update()
check(f"a theme switched in Settings leaves the open day's stripes in the "
      f"notes' own colours ({_od_stripes()})",
      app.theme_name == 'dark_ocean' and _od_stripes() == _od_want)
app.set_theme('dark'); app.update()
app.notebook.select(app.TAB_NOTES); app.update()
app.editor_theme_btn.invoke(); app.update()
app.notebook.select(app.TAB_CALENDAR); app.update()
check(f"...and so does the sun/moon above a note ({app.theme_name}, "
      f"{_od_stripes()})",
      app.theme_name != 'dark' and _od_stripes() == _od_want)
app.set_theme(_od_theme_was); app.update()
app.close_day_panel()
app.notebook.select(app.TAB_NOTES); app.update()


class _CalKey:
    """What a page key reaches through bind_all: the bound handler, with the
    widget that holds the keyboard as the event's widget. A generated key
    goes to the focus, which a test process does not own (qa/README)."""
    widget = None


_CalKey.widget = app.cal_canvas

# ---- A MONTH CHANGED UNDER THE POINTER TAKES ITS PREVIEW WITH IT ----
# Resting on a title shows its preview; PgDn changed the month under the
# still pointer and the preview of July's note stayed over August's 12th,
# and over the gaps and the weekday names too -- the redraw forgot the
# hover without taking its preview down.
app.notes = [NO.normalize_note({
    'id': 150, 'title': 'TipDentist', 'body': 'Bring the card',
    'category': 'General', 'date': '2026-07-08'})]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
_tp_at = _cd_point('2026-07-08', chip=0)
_qa_fire(app.cal_canvas, '<Motion>', x=_tp_at[0], y=_tp_at[1]); app.update()
_tp_tip = getattr(app, '_day_tooltip', None)
_tp_up = _tp_tip is not None and bool(_tp_tip.winfo_exists())
app._calendar_key(_CalKey(), months=1); app.update()
check(f"PgDn under a note's preview takes the preview down with its month "
      f"(up before: {_tp_up}, month {app.cal_year}-{app.cal_month:02d}, "
      f"after: {getattr(app, '_day_tooltip', None)})",
      _tp_up and (app.cal_year, app.cal_month) == (2026, 8)
      and getattr(app, '_day_tooltip', None) is None
      and not (_tp_tip.winfo_exists() if _tp_tip is not None else False))
app.hide_day_tooltip()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()

# ---- ...AND SO DOES THE WHEEL ----
# The wheel scrolls the calendar's area under the same still pointer, with
# no redraw -- and only a redraw took the preview down: the preview of the
# 8th stayed up over the 22nd. The area's own movement takes it down now.
_wp_geom = app.winfo_geometry()
try:
    app.geometry('1150x600'); app.update()
    app.open_day_popup('2026-07-29'); app.update()
    app.cal_scroll_canvas.yview_moveto(0); app.update()
    _wp_at = _cd_point('2026-07-08', chip=0)
    _qa_fire(app.cal_canvas, '<Motion>', x=_wp_at[0], y=_wp_at[1]); app.update()
    _wp_tip = getattr(app, '_day_tooltip', None)
    _wp_up = _wp_tip is not None and bool(_wp_tip.winfo_exists())
    _wp_before = app.cal_scroll_canvas.yview()[0]
    _qa_fire(app.cal_canvas, '<MouseWheel>', x=_wp_at[0], y=_wp_at[1],
             delta=-360)
    app.update()
    _wp_after = app.cal_scroll_canvas.yview()[0]
    check(f"the wheel under a note's preview takes the preview down with the "
          f"days it moved (up before: {_wp_up}, view {_wp_before:.2f} -> "
          f"{_wp_after:.2f}, after: {getattr(app, '_day_tooltip', None)})",
          _wp_up and _wp_after > _wp_before
          and getattr(app, '_day_tooltip', None) is None)
finally:
    app.hide_day_tooltip()
    app.close_day_panel()
    app.geometry(_wp_geom); app.update()

# ---- WHILE HISTORY COVERS THE MONTH, THE PAGE KEYS PAGE HISTORY ----
# PgUp/PgDn/Home asked only whether the Calendar tab was showing, so under
# the register they moved the hidden month -- three PgDn from July came
# back to October -- and the register itself did not move.
app.notes = [NO.normalize_note({
    'id': 160 + i, 'title': f'PageKey{i}', 'body': 'x', 'category': 'General',
    'date': '2026-03-%02d' % (i % 28 + 1)}) for i in range(45)]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
app._history_toggle_btn.invoke(); app.update()
app.cal_scroll_canvas.yview_moveto(0); app.update()
_hk_top = app.cal_scroll_canvas.yview()
check(f'fixture: the register is longer than its view ({_hk_top})',
      app._history_visible and _hk_top[0] == 0.0 and _hk_top[1] < 1.0)
for _ in range(3):
    app._calendar_key(_CalKey(), months=1); app.update()
_hk_paged = app.cal_scroll_canvas.yview()
check(f'PgDn under History pages the register and leaves the hidden month '
      f'alone ({_hk_top} -> {_hk_paged}, {app.cal_year}-{app.cal_month:02d})',
      (app.cal_year, app.cal_month) == (2026, 7) and _hk_paged[0] > _hk_top[0])
app._calendar_key(_CalKey(), today=True); app.update()
_hk_home = app.cal_scroll_canvas.yview()
check(f'...Home goes to its top, not to today ({_hk_home}, '
      f'{app.cal_year}-{app.cal_month:02d})',
      _hk_home[0] == 0.0 and (app.cal_year, app.cal_month) == (2026, 7))
app._history_toggle_btn.invoke(); app.update()
check(f'...and the grid comes back on the month it left '
      f'({app.cal_month_lbl.cget("text")!r})',
      not app._history_visible and app.cal_month_lbl.cget('text') == 'July 2026  ⌄')

# ---- THE REMINDER BAR LANDS ON TODAY, ON SCREEN ----
# The "notes for today" bar sits above every page. Its click selected the
# Calendar tab and opened today's list under whichever month was showing,
# with no day outlined; from Settings, it opened the day behind Settings,
# where nothing showed; and under History, below the register.
import datetime as _rm_dt
_rm_d = _rm_dt.date.today()
_rm_today = _rm_d.strftime('%Y-%m-%d')
_rm_away = (_rm_d.year - 1, _rm_d.month)          # a month that is not today's
app.notes = [NO.normalize_note(n) for n in (
    {'id': 170, 'title': 'RemindToday', 'body': 'x', 'category': 'General',
     'date': _rm_today},
    {'id': 171, 'title': 'RemindAway', 'body': 'x', 'category': 'General',
     'date': '%04d-%02d-03' % _rm_away})]
app.save_notes()
app._render_reminder_bar(1, _rm_today); app.update()
_rm_lbl = find_widget(app.reminder_bar, tk.Label, 'You have')


def _rm_landed():
    return (app.notebook.winfo_ismapped()
            and app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
            and not app._history_visible
            and (app.cal_year, app.cal_month) == (_rm_d.year, _rm_d.month)
            and app.selected_day == _rm_today and app._day_panel_mode == 'list'
            and _cd_view(_rm_today)['selected_width'] == 2)


def _rm_elsewhere():
    app.close_day_panel()
    app.notebook.select(app.TAB_CALENDAR); app.update()
    app.cal_year, app.cal_month = _rm_away
    app.render_calendar(); app.update()


check('fixture: the reminder bar shows its line', _rm_lbl is not None)
_rm_elsewhere()
if _rm_lbl is not None:
    _qa_click(_rm_lbl); app.update()
check(f"the reminder's click shows today on its own month, outlined "
      f"({app.cal_year}-{app.cal_month:02d}, {app.selected_day})", _rm_landed())
_rm_elsewhere()
app.show_settings_page(); app.update()
if _rm_lbl is not None:
    _qa_click(_rm_lbl); app.update()
check(f"...clicked over Settings, it leaves Settings to show it "
      f"(Settings open: {app._settings_open})",
      not app._settings_open and _rm_landed())
_rm_elsewhere()
app._history_toggle_btn.invoke(); app.update()
if _rm_lbl is not None:
    _qa_click(_rm_lbl); app.update()
check(f"...and clicked over History, it brings the month back to show it "
      f"(History open: {app._history_visible})", _rm_landed())
app.dismiss_reminder()
app.close_day_panel(); app.update()

# ---- SAVING THE MARKER POPUP EMPTY OFFERS THE WAY BACK ----
# The menu's "Clear day markers" offers Undo on its toast, and so does the
# palette's "No color" for a day's colour. The marker popup's Clear, then
# Save, discards the same markers by a fourth door, and it said nothing and
# kept nothing. Picking chips and ✕ still write nothing (held above).
_mk_day = '2026-07-14'
_mk_three = [e for e, _c in app.DAY_MARKER_EMOJIS[:3]]
app.day_emoji = {_mk_day: list(_mk_three)}
app._persist_day_emoji()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
app._hide_toast()


def _mk_popup_save(clear_first):
    app._mark_day_emoji(_mk_day, _types_q7.SimpleNamespace(x_root=200, y_root=200))
    app.update()
    _mk_pop = app._mini_popup
    if clear_first:
        _mk_clear = find_widget(_mk_pop, tk.Button, 'Clear')
        if _mk_clear is not None:
            _mk_clear.invoke(); app.update()
    _mk_save = find_widget(_mk_pop, tk.Button, 'Save')
    if _mk_save is not None:
        _mk_save.invoke(); app.update()


_mk_popup_save(clear_first=True)
_mk_offer = app._toast_action
check(f"the marker popup saved empty clears the day and offers Undo on "
      f"its toast ({app.day_emoji.get(_mk_day)}, "
      f"{str(app.toast_lbl.cget('text'))!r})",
      _mk_day not in app.day_emoji
      and NO.load_settings().get('day_emoji', {}).get(_mk_day) is None
      and _mk_offer is not None
      and 'Day markers cleared' in str(app.toast_lbl.cget('text')))
if _mk_offer is not None:
    _mk_offer(); app.update()
check(f"...and its Undo puts the three back, on disk and in the day's corner "
      f"({_cd_view(_mk_day)['badge']!r})",
      app.day_emoji.get(_mk_day) == _mk_three
      and NO.load_settings().get('day_emoji', {}).get(_mk_day) == _mk_three
      and _cd_badge_ok(_cd_view(_mk_day)['badge'], _mk_three))
# The control: saved unchanged, nothing was lost and nothing is offered.
app._hide_toast()
_mk_popup_save(clear_first=False)
check(f"...while saving it unchanged offers nothing ({app._toast_action})",
      app._toast_action is None and app.day_emoji.get(_mk_day) == _mk_three)
app.day_emoji = {}
app._persist_day_emoji()
app._hide_toast()
app.notebook.select(app.TAB_NOTES); app.update()

# ---- A DAY DRAWS INSIDE ITSELF, ITS NUMBER UNCOVERED, READABLE ON ITS PAINT ----
# Three things the drawing got wrong where the widget grid had hidden them.
# A day of many colours drew its dots across the gap into the next days (a
# Frame had clipped them). Three markers printed over the day's number at
# the default window's width (an opaque Label had covered it). And a day
# painted yellow or light teal drew its number, titles and markers in white
# (1.3:1). Read from the canvas at the smallest window, either side of the
# 1,150-pixel text step, and wide: every item's box against its cell.
from noteorganizer.core.themes import contrasting_fg as _dr_contrasting_fg
_dr_colours = list(dict.fromkeys(NO.PRESET_NOTE_COLORS))[:12]
_dr_marks = [e for e, _c in app.DAY_MARKER_EMOJIS[:4]]
app.notes = [NO.normalize_note({
    'id': 180 + i, 'title': f'Colour{i}', 'body': 'x', 'category': 'General',
    'date': '2026-08-12', 'color': col}) for i, col in enumerate(_dr_colours)]
app.notes += [NO.normalize_note({
    'id': 195 + i, 'title': f'Painted{i}', 'body': 'x', 'category': 'General',
    'date': d}) for i, d in enumerate(('2026-08-14', '2026-08-18', '2026-08-19'))]
app.save_notes()
app.day_emoji = {'2026-08-14': list(_dr_marks), '2026-08-15': list(_dr_marks[:3]),
                 '2026-08-18': list(_dr_marks[:3])}
app._persist_day_emoji()
app.day_colors = {'2026-08-14': '#e76f51', '2026-08-18': '#fee440',
                  '2026-08-19': '#00f5d4'}
app._persist_day_colors()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 8
app.render_calendar(); app.update()


_dr_w0, _dr_h0 = app.winfo_width(), app.winfo_height()
try:
    for _dr_geom in ('640x700', '1149x850', '1150x850', '1400x850'):
        app.geometry(_dr_geom)
        for _ in range(6):
            app.update(); _t7.sleep(0.02)
        _dr_cv = app.cal_canvas
        _dr_out, _dr_cover = [], []
        for _dr_d, _dr_rec in app._cal_cells.items():
            for _dr_item in _dr_cv.find_withtag(_dr_rec['tag']):
                _dr_b = _dr_cv.bbox(_dr_item)
                if _dr_b and not (_dr_rec['x0'] - 1 <= _dr_b[0] and _dr_b[2] <= _dr_rec['x1'] + 1
                                  and _dr_rec['y0'] - 1 <= _dr_b[1]
                                  and _dr_b[3] <= _dr_rec['y1'] + 1):
                    _dr_out.append(_dr_d)
            _dr_it = _dr_rec['items']
            if 'badge' in _dr_it:
                _b1, _b2 = _dr_cv.bbox(_dr_it['badge']), _dr_cv.bbox(_dr_it['day'])
                if _b1[0] < _b2[2] and _b2[0] < _b1[2] and _b1[1] < _b2[3] and _b2[1] < _b1[3]:
                    _dr_cover.append(_dr_d)
        _dr_busy = _cd_view('2026-08-12')
        _dr_cell = _dr_busy['box'][2] - _dr_busy['box'][0]
        check(f'{_dr_geom} (cell {_dr_cell}px): everything a day draws sits inside '
              f'its own cell ({sorted(set(_dr_out))})', not _dr_out)
        check(f'{_dr_geom}: no marker covers its day\'s number ({_dr_cover}; '
              f'{_cd_view("2026-08-15")["badge"]!r}, {_cd_view("2026-08-14")["badge"]!r})',
              not _dr_cover
              and _cd_badge_ok(_cd_view('2026-08-15')['badge'], _dr_marks[:3])
              and _cd_badge_ok(_cd_view('2026-08-14')['badge'], _dr_marks))
        check(f'{_dr_geom}: a day of twelve colours shows the dots that fit, in '
              f'order, and "+" for the rest ({len(_dr_busy["dots"])} dots, '
              f'{_dr_busy["more_dots"]!r})',
              _dr_busy['dots'] == _dr_colours[:len(_dr_busy['dots'])]
              and (_dr_busy['more_dots'] == '+') == (len(_dr_busy['dots']) < 12))
    # Wide, where the room is not what limits: still three at most.
    check(f'with room to spare, four markers show as three and "+1" '
          f'({_cd_view("2026-08-14")["badge"]!r})',
          _cd_view('2026-08-14')['badge'] == ''.join(_dr_marks[:3]) + '+1')
finally:
    app.geometry('%dx%d' % (_dr_w0, _dr_h0))
    for _ in range(6):
        app.update(); _t7.sleep(0.02)


def _dr_contrast(a, b):
    def lum(h):
        h = h.lstrip('#')
        chans = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# The two paints the audit measured at 1.28:1 and 1.40:1 must read now, and
# so must the darker one, which kept white at 3.3:1 while the letters for a
# picked colour had a formula of their own instead of letters_on's.
for _dr_d, _dr_paint, _dr_least in (('2026-08-18', '#fee440', 4.5),
                                    ('2026-08-19', '#00f5d4', 4.5),
                                    ('2026-08-14', '#e76f51', 4.5)):
    _dr_v = _cd_view(_dr_d)
    _dr_want = _dr_contrasting_fg(_dr_paint)
    _dr_fills = {_dr_v['day_fill']} | set(_dr_v['chip_fill']) | (
        {_dr_v['badge_fill']} if _dr_v['badge'] else set())
    check(f"a day painted {_dr_paint} draws its number, titles and markers in the "
          f"colour that reads on it ({_dr_fills}, "
          f"{_dr_contrast(_dr_paint, _dr_v['day_fill']):.2f}:1)",
          _dr_v['bg'] == _dr_paint and _dr_fills == {_dr_want}
          and _dr_contrast(_dr_paint, _dr_v['day_fill']) >= _dr_least)
# A colour the drawing cannot work out -- #abc, which the colour gate now
# gives back long, planted here past the gate -- draws its text white, as
# every painted day did before it learned contrast. Raising in the middle
# of the month's drawing left the month half drawn and unclickable.
app.day_colors = dict(app.day_colors, **{'2026-08-20': '#abc'})
_dr_err = None
try:
    app.render_calendar(); app.update()
except Exception as _dr_exc:   # noqa: BLE001 -- the check reports it
    _dr_err = repr(_dr_exc)
check(f'a day colour the drawing cannot work out leaves the month drawn '
      f'({len(app._cal_cells)} days, {_dr_err})',
      _dr_err is None and len(app._cal_cells) == 31
      and _cd_view('2026-08-20')['day_fill'] == '#ffffff')
app.day_emoji, app.day_colors = {}, {}
app._persist_day_emoji()
app._persist_day_colors()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
app.notebook.select(app.TAB_NOTES); app.update()

# ---- A LONG TITLE GIVES WAY; THE MARKS AFTER IT STAY ----
# A day's list row and a History row put their marks AFTER the title -- ✎
# 💬 📎 on the day, "· 20 occurrences · 1 edited (✎)" in History -- in one
# label, and a long title (the app allows TITLE_MAX_LEN characters) pushed
# them past the label's edge, which is where the cut fell. Only the title
# gives way now, with an ellipsis, at the label's own width.
_lt_title = ('Quarterly planning with the whole regional team about the budget '
             * 4)[:app.TITLE_MAX_LEN].strip()
app.notes = [NO.normalize_note({
    'id': 210, 'title': _lt_title, 'body': 'x', 'category': 'General',
    'date': '2026-07-01', 'comments': 'c',
    'recurrence': {'freq': 'daily', 'count': 20},
    'attachments': [{'filename': 'plan.pdf', 'stored_as': 'x_plan.pdf'}],
    'overrides': {'2026-07-10': {'title': _lt_title, 'body': 'edited',
                                 'comments': 'note to self',
                                 'category': 'General', 'color': ''}}}),
    NO.normalize_note({'id': 211, 'title': 'Short one', 'body': 'x',
                       'category': 'General', 'date': '2026-07-10'})]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
_od_open_day('2026-07-10')
for _ in range(3):
    app.update_idletasks(); app.update()


def _lt_label(root, needle):
    _stack = [root]
    while _stack:
        _w = _stack.pop(0)
        if isinstance(_w, tk.Label) and needle in str(_w.cget('text')):
            return _w
        _stack.extend(_w.winfo_children())
    return None


_lt_row = _lt_label(app.day_panel, _lt_title[:20])
_lt_short = _lt_label(app.day_panel, 'Short one')
_lt_text = str(_lt_row.cget('text')) if _lt_row is not None else ''
check(f"a long title in a day's list gives way and its marks stay in view "
      f"(...{_lt_text[-28:]!r}, needs {_lt_row.winfo_reqwidth() if _lt_row else 0} "
      f"of {_lt_row.winfo_width() if _lt_row else 0}px)",
      _lt_row is not None and _lt_text.endswith('…  ✎  💬  📎×1')
      and _lt_text.startswith('🔁 Quarterly')
      and _lt_row.winfo_reqwidth() <= _lt_row.winfo_width())
check(f"...while a short one is shown whole ({_lt_short.cget('text') if _lt_short else None!r})",
      _lt_short is not None and str(_lt_short.cget('text')) == 'Short one')
app._history_toggle_btn.invoke(); app.update()
for _ in range(3):
    app.update_idletasks(); app.update()
_lt_hist = _lt_label(app._history_rows, _lt_title[:20])
_lt_htext = str(_lt_hist.cget('text')) if _lt_hist is not None else ''
check(f"...and in History, the group's counts stay in view "
      f"(...{_lt_htext[-45:]!r}, needs {_lt_hist.winfo_reqwidth() if _lt_hist else 0} "
      f"of {_lt_hist.winfo_width() if _lt_hist else 0}px)",
      _lt_hist is not None and '…' in _lt_htext
      and _lt_htext.endswith(' · 20 occurrences · 1 edited (✎)')
      and _lt_hist.winfo_reqwidth() <= _lt_hist.winfo_width())
app._history_toggle_btn.invoke(); app.update()
app.close_day_panel()
app.notebook.select(app.TAB_NOTES); app.update()

# ---- WITH A DAY OPEN, A HELD DRAG OF THE EDGE WAITS FOR THE HAND ----
# The month alone is one drawing and follows a held drag of the window's
# edge (qa9 holds that). An open day's panel below it is widgets -- a row
# per note, or a note's whole text -- and was laid out at every step with
# the month: 60 ms a step for an ordinary month, 150 and more for a busy
# one, back near the cost the drawing set out to remove. So with a day
# open the calendar waits for the hand, as History and the other pages do.
# The button is answered for the app and the pause is put out of reach, as
# qa9 does; what is asked is the width the content was given.
def _dg_width():
    return int(float(app.main_canvas.itemcget(app._main_window_item, 'width')))


def _dg_window():
    return max(app.main_canvas.winfo_width(), app._main_min_width)


app.notes = [NO.normalize_note({'id': 220, 'title': 'DragDay', 'body': 'x',
                                'category': 'General', 'date': '2026-07-08'})]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
_dg_held = {'now': True}
_dg_w0, _dg_h0 = app.winfo_width(), app.winfo_height()
app._pointer_button_held = lambda: _dg_held['now']
app.RESIZE_PAUSE_MS = 60000
try:
    app.geometry('%dx%d' % (_dg_w0 - 40, _dg_h0))
    for _ in range(5):
        app.update_idletasks(); app.update()
    check(f'fixture: with no day open, the month follows a held drag '
          f'({_dg_width()} for {_dg_window()})', _dg_width() == _dg_window())
    for _dg_open in (lambda: _od_open_day('2026-07-08'),
                     lambda: _od_open_chip('2026-07-08', 0)):
        _dg_open()
        for _ in range(3):
            app.update_idletasks(); app.update()
        _dg_mode = app._day_panel_mode
        _dg_before = _dg_width()
        app.geometry('%dx%d' % (_dg_before + (30 if _dg_before < _dg_w0 else -30),
                                _dg_h0))
        for _ in range(5):
            app.update_idletasks(); app.update()
        check(f'with a day open ({_dg_mode}), a held drag waits for the hand '
              f'(content {_dg_before} -> {_dg_width()}, the window is {_dg_window()})',
              _dg_mode in ('list', 'note') and _dg_width() == _dg_before != _dg_window()
              and app._resize_watch_job is not None)
        _dg_held['now'] = False
        _dg_end = time.time() + 5
        while time.time() < _dg_end and _dg_width() != _dg_window():
            app.update(); time.sleep(0.02)
        check(f'...and letting go lays it out, the open day with it '
              f'({_dg_width()} for {_dg_window()}, {app._day_panel_mode})',
              _dg_width() == _dg_window() and app._day_panel_mode == _dg_mode)
        _dg_held['now'] = True
finally:
    for _dg_attr in ('_pointer_button_held', 'RESIZE_PAUSE_MS'):
        app.__dict__.pop(_dg_attr, None)
    app.geometry('%dx%d' % (_dg_w0, _dg_h0))
    app._lay_out_at_window_size()
    for _ in range(5):
        app.update_idletasks(); app.update()
app.close_day_panel()
app.notebook.select(app.TAB_NOTES); app.update()

# ---- HISTORY KEEPS WHAT A SERIES COSTS; IT NEVER KEEPS A STALE ANSWER ----
# History worked every bounded series out again at each search pause (300-
# 400 ms at 1,000-5,000 notes). It now keeps what does not depend on the
# query -- a series' days, its label, its next day -- under exactly what
# they are worked out from, while the register is open. The promise that
# must not move: the rows, their order, their counts and "Show more" are
# what a register opened afresh would show, also after a series changes
# under the kept answers.
app.notes = [NO.normalize_note(n) for n in (
    [{'id': 230, 'title': 'KeptSeries', 'body': 'x', 'category': 'General',
      'date': '2026-06-01', 'recurrence': {'freq': 'daily', 'count': 10}},
     {'id': 231, 'title': 'KeptLong', 'body': 'x', 'category': 'General',
      'date': '2026-01-05', 'recurrence': {'freq': 'weekly', 'end': '2029-01-01'}}]
    + [{'id': 240 + i, 'title': f'KeptDated{i}', 'body': 'x',
        'category': 'General', 'date': '2026-03-%02d' % (i % 28 + 1)}
       for i in range(55)])]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app._history_toggle_btn.invoke(); app.update()
# A page of fifty, as a search or a year chip leaves it (the Show-more
# check above left it at a hundred).
app._history_shown = 50
app._render_calendar_history(); app.update()


def _hm_rows():
    return find_all_labels(app._history_rows) + [
        str(b.cget('text')) for b in app._history_rows.winfo_children()
        if isinstance(b, tk.Button)]


def _hm_fresh():
    """The same view, from a memo nobody has used."""
    app._history_memo = {}
    app._render_calendar_history(); app.update()
    return _hm_rows()


_hm_kept = _hm_rows()
check(f'fixture: History shows the ten-day series, 50 rows and Show more '
      f'({[t for t in _hm_kept if "KeptSeries" in t]}, {_hm_kept[-1]!r})',
      any('KeptSeries' in t and '10 occurrences' in t for t in _hm_kept)
      and _hm_kept[-1].startswith('Show more (7 left)'))
for _hm_q in ('Kept', 'KeptD', ''):
    app._history_search_var.set(_hm_q)
    app._render_calendar_history(); app.update()
_hm_kept = _hm_rows()
check('with its kept answers, History lists what a fresh register lists',
      _hm_kept == _hm_fresh())
# A series changes under the kept answers: one of its days deleted through
# a day row's own menu ("this occurrence only"), with the search running.
app._history_search_var.set('KeptSeries')
app._render_calendar_history(); app.update()
app._history_toggle_group(230); app.update()
_hm_caught = []
_hm_real_add, _hm_real_pop = tk.Menu.add_command, tk.Menu.tk_popup
tk.Menu.add_command = lambda self, **kw: _hm_caught.append(
    (str(kw.get('label', '')), kw.get('command')))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    _hm_row = _lt_label(app._history_rows, '05.06.2026')
    if _hm_row is not None:
        _qa_fire(_hm_row, '<Button-3>', x=5, y=5, rootx=200, rooty=200)
        app.update()
finally:
    tk.Menu.add_command = _hm_real_add
    tk.Menu.tk_popup = _hm_real_pop
_hm_delete = next((c for l, c in _hm_caught if 'Delete' in l), None)
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
try:
    if _hm_delete is not None:
        _hm_delete(); app.update()
finally:
    del app.ask_occurrence_scope
_hm_after = _hm_rows()
check(f'...and after one of a series\' days is deleted under them, the count '
      f'follows ({[t for t in _hm_after if "KeptSeries" in t]})',
      _hm_delete is not None
      and '2026-06-05' in (app.find_note(230).get('exceptions') or [])
      and any('KeptSeries' in t and '9 occurrences' in t for t in _hm_after)
      and not any('05.06.2026' in t for t in _hm_after)
      and _hm_after == _hm_fresh())
app._history_search_var.set('')
app._render_calendar_history(); app.update()
_hm_show = find_widget(app._history_rows, tk.Button, 'Show more')
if _hm_show is not None:
    _hm_show.invoke(); app.update()
_hm_more = _hm_rows()
check(f'...and Show more still brings the same rows as a fresh register '
      f'({len(_hm_more)} rows)',
      _hm_show is not None and any('KeptLong' in t for t in _hm_more)
      and _hm_more == _hm_fresh())

# ---- A DAY'S NOTES COME FROM THE MONTH ALREADY WORKED OUT ----
# The month's drawing already knows which notes land on each day; hovering
# a day and opening it asked every note again (14 ms at 5,000 notes, at
# every hover). The drawn month's answer is used while it is current.
app._history_toggle_btn.invoke(); app.update()
app.cal_year, app.cal_month = 2026, 3
app.render_calendar(); app.update()
_nd_day = '2026-03-02'
_nd_calls = []
_nd_real = app.notes_on_date
app.notes_on_date = lambda d: (_nd_calls.append(d), _nd_real(d))[1]
_nd_tips = []
try:
    _at = _cd_point(_nd_day)
    _qa_fire(app.cal_canvas, '<Motion>', x=_at[0], y=_at[1]); app.update()
    _nd_tips = find_all_labels(app._day_tooltip) if getattr(app, '_day_tooltip', None) else []
    app.hide_day_tooltip()
    _od_open_day(_nd_day)
finally:
    del app.notes_on_date
_nd_want = [n['title'] for n in app.notes_on_date(_nd_day)]
check(f"hovering and opening a day of the drawn month ask no note again "
      f"({_nd_calls}), and show the day's notes ({_nd_want})",
      not _nd_calls and _nd_want
      and all(any(t in s for s in _nd_tips) for t in _nd_want)
      and all(any(t in s for s in _od_panel_texts()) for t in _nd_want))

# ---- RE-DRAWING HISTORY OR A DAY LEAVES NOTHING BEHIND ----
# Both bound their long-lived frame again at every redraw -- History its
# wheel, the day panel its right-click -- and Tkinter never deletes the
# command a binding replaces: one more Tcl command per render, for as long
# as the app ran. The day panel's binding also outlived its note: back on
# the day's list, a right-click on the panel's bare edge offered the last
# note's menu.
app._history_toggle_btn.invoke(); app.update()
_lb_history = _qa_leaves_nothing_behind(
    app, lambda: (app._render_calendar_history(), app.update()), 20)
app._history_toggle_btn.invoke(); app.update()
_od_open_day(_nd_day)
_lb_note = app.notes_on_date(_nd_day)[0]
_lb_day = _qa_leaves_nothing_behind(
    app, lambda: (app.show_day_note(_lb_note, _nd_day), app.show_day_list(),
                  app.update()), 20)
check(f'History renders and day views, again and again, leave no Tcl command '
      f'behind ({_lb_history[1]} | {_lb_day[1]})',
      _lb_history[0] and _lb_day[0])
_lb_menus = []
app.show_note_context_menu = lambda e, n, **k: _lb_menus.append((n['id'], k))
try:
    app.show_day_note(_lb_note, _nd_day); app.update()
    _qa_fire(app.day_panel, '<Button-3>', x=3, y=3, rootx=200, rooty=200)
    app.update()
    _lb_in_note = list(_lb_menus)
    app.show_day_list(); app.update()
    _qa_fire(app.day_panel, '<Button-3>', x=3, y=3, rootx=200, rooty=200)
    app.update()
finally:
    del app.show_note_context_menu
check(f"the panel's edge offers the open note's menu, and none once back on "
      f"the day's list ({_lb_in_note}, {_lb_menus[len(_lb_in_note):]})",
      _lb_in_note == [(_lb_note['id'], {'occurrence_date': _nd_day})]
      and _lb_menus == _lb_in_note)
app.close_day_panel()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar(); app.update()
app.notebook.select(app.TAB_NOTES); app.update()

# ============================================================
# 7. ATTACHMENT-ONLY NOTE AUTOSAVE
# ============================================================
tmp_file = os.path.join(tempfile.gettempdir(), 'qa7_attach_only.txt')
with open(tmp_file, 'w') as f: f.write('x')

app.open_blank_tab()
app.update()
fd.askopenfilenames = lambda **k: (tmp_file,)
# Counted rather than caught pending: a queued job is a fact about a
# moment, and adding an attachment does real work (a file copy) before the
# update() below -- so on a loaded machine the 500ms debounce can fire and
# clear the job before it is read. A sibling of this shape went red on CI
# while passing here three times running.
_at7_fired = {'n': 0}
_at7_real_now = app._autosave_now


def _at7_counting_now(*a, **k):
    _at7_fired['n'] += 1
    return _at7_real_now(*a, **k)


app._autosave_now = _at7_counting_now
try:
    app.add_attachment()
    app.update()
finally:
    app._autosave_now = _at7_real_now
check(f'adding an attachment schedules an autosave '
      f'(pending={getattr(app, "_autosave_job", None) is not None}, '
      f'fired={_at7_fired["n"]})',
      getattr(app, '_autosave_job', None) is not None
      or _at7_fired['n'] >= 1)

if getattr(app, '_autosave_job', None) is not None:
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
    app.notes.append({'id': 700 + i, 'title': f'Tab{i}', 'body': f'body {i}',
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
    app.notes.append({'id': 800 + i, 'title': 'Twin', 'body': 'idem',
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
      sum(1 for n in app.notes if n.get('title') == 'Twin') == 1
      and sum(1 for e in app.trash if e.get('title') == 'Twin') == 2)
_dpf.destroy(); app.update()

# ---- Duplicates hover PREVIEW (coverage-lift #2) ----
_pv_note = {'id': 900, 'title': 'PreviewNote', 'body': 'preview body',
            'category': 'General', 'updated': '2026-01-01 00:00',
            'created': '2026-01-01 09:30', 'date': '2026-03-05',
            'checklist': [], 'attachments': []}
_pv_lbl = tk.Label(app, text='hover me')
_pv_lbl.pack()
app._attach_dup_preview(_pv_lbl, _pv_note)
app.update()
# Which toplevels existed BEFORE the hover, so the one that appears can be
# named without assuming where it is parented.
_pv_before = set()


def _all_tops7(root, acc):
    for c in root.winfo_children():
        if isinstance(c, tk.Toplevel):
            acc.add(c)
        _all_tops7(c, acc)


_all_tops7(app, _pv_before)
_qa_fire(_pv_lbl, '<Enter>')
app.update()
# Found by being NEW, not by being a child of the row. The preview is
# parented to the window rather than to the widget it describes: a
# Toplevel whose master is a widget joins that widget's winfo_children(),
# so a preview parented to a row lands inside its panel's tree, where a
# theme sweep, the wheel binding and any check counting what is on screen
# all meet it. That cost two red CI runs -- qa3 counted one open preview
# as an extra trash row, deterministically on a headless display where
# the pointer sits still, and never here where it does not.
_pv_after = set()
_all_tops7(app, _pv_after)
_tips = [w for w in (_pv_after - _pv_before)]
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
      _tips and any('PreviewNote' in t for t in _tip_txts7(_tips)))
# ...its date and its creation shown as every date in the app is, day first.
_pv_said = _tip_txts7(_tips) if _tips else []
check(f'...naming the note\'s date and when it was made, day first '
      f'({[t for t in _pv_said if "2026" in t]})',
      '05.03.2026' in _pv_said and '01.01.2026 09:30' in _pv_said)
_qa_fire(_pv_lbl, '<Leave>')
app.update()
check('leaving the row hides the preview',
      not any(w.winfo_exists() for w in _tips))
_pv_lbl.destroy(); app.update()

# A note with a table: the preview gives its words and says a table is
# there, as the calendar's does. Field-reported from Recently deleted and
# Duplicates: "only parallel vertical lines". A row typed past its last
# cell counts as part of the table, and a body that is not text (a trash
# entry is not normalised) shows no words rather than failing.
_pv_lbl = tk.Label(app, text='hover me')
_pv_lbl.pack()
app._attach_dup_preview(_pv_lbl, dict(
    _pv_note, body='Shopping list\n| Milk | 2 |\n| --- | --- |\n| Eggs | 6 |and more\nEnd'))
app.update()
_pv_before = set()
_all_tops7(app, _pv_before)
_qa_fire(_pv_lbl, '<Enter>')
app.update()
_pv_after = set()
_all_tops7(app, _pv_after)
_pv_said = _tip_txts7(list(_pv_after - _pv_before))
check(f'a table in a hover preview is named, not drawn as bars ({_pv_said})',
      not any('|' in t for t in _pv_said)
      and any('▦ 1 table' in t for t in _pv_said)
      and any('Shopping list' in t for t in _pv_said))
_qa_fire(_pv_lbl, '<Leave>')
app.update()
_pv_lbl.destroy(); app.update()
_pv_lbl = tk.Label(app, text='hover me')
_pv_lbl.pack()
app._attach_dup_preview(_pv_lbl, dict(_pv_note, body=['not', 'text']))
_pv_before = set()
_all_tops7(app, _pv_before)
_qa_fire(_pv_lbl, '<Enter>')
app.update()
_pv_after = set()
_all_tops7(app, _pv_after)
_pv_said = _tip_txts7(list(_pv_after - _pv_before))
check(f'a preview of a body that is not text still opens ({_pv_said})',
      any('PreviewNote' in t for t in _pv_said))
_qa_fire(_pv_lbl, '<Leave>')
app.update()
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
app.title_entry.insert(0, 'ToEmpty')
app.body_text.insert('1.0', 'old content')
app.save_current_note(auto=False); app.update()
_gid = app.selected_note_id
app.title_entry.delete(0, 'end')
app.body_text.delete('1.0', 'end')
app._flush_autosave(); app.update()
_gn = app.find_note(_gid)
check('switch-away flush records the emptying of a saved note',
      _gn is not None and _gn['title'] == '' and _gn['body'] == '')

app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'ToEmpty2')
app.body_text.insert('1.0', 'other content')
app.save_current_note(auto=False); app.update()
_gid2 = app.selected_note_id
app.title_entry.delete(0, 'end')
app.body_text.delete('1.0', 'end')
app._autosave_now(); app.update()
_gn2 = app.find_note(_gid2)
check('the autosave timer route records the emptying too',
      _gn2 is not None and _gn2['title'] == '' and _gn2['body'] == '')

app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'ToEmpty3')
app.body_text.insert('1.0', 'content again')
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
app.comments_text.insert('1.0', 'just one comment')
app._autosave_now(); app.update()
check('a comments-only note is real content to the autosave',
      len(app.notes) == _before + 1
      and app.notes[-1]['comments'] == 'just one comment')

# ---- Whitespace edits reach the disk (T0-4, the half in FRONT of the
# writer) ----
# The save learned to keep leading/trailing whitespace, but the dirty
# comparator stripped both sides, so a whitespace-only edit read as "no
# change" and the automatic routes never wrote it: the fix's own promise,
# defeated one frame upstream.
app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'Spaces')
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
app._working_checklist = [{'text': 'just the list', 'done': False}]
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
      and app._get_checklist() == [{'text': 'just the list', 'done': False}])

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
                     'the long original version, about to be cut down sharply')
app.save_current_note(auto=False); app.update()
_pid = app.selected_note_id
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'short')
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
      _pn is not None and 'original version' in _pn.get('body', ''))
# What the restore replaced is kept as the copy in its turn (2026-10-22,
# the owner's call): spent, it took the words written since the deletion
# with no way back. So the button stays, and brings "short" back.
check(f"...and what it replaced is kept, the button there to bring it back "
      f"({(_pn.get('_prev') or {}).get('body')!r})",
      (_pn.get('_prev') or {}).get('body') == 'short'
      and app.restore_prev_btn.winfo_ismapped())
# A big deletion taken back by Undo: the save after it holds what the copy
# kept, so the copy is spent and the button goes. It stayed, and pressed
# later it put the old version over everything written since. (The date
# half-typed above is cleared first: leaving it asks a question.)
app.date_entry.delete(0, 'end')
app.save_current_note(auto=False); app.update()
app.open_blank_tab(); app.update()
app.title_entry.insert(0, 'Undone')
app.body_text.insert('1.0', 'a long text that a slip of the hand is about to delete whole')
app.save_current_note(auto=False); app.update()
_ud_id = app.selected_note_id
app.body_text.edit_separator()
app.body_text.delete('1.0', 'end')
app.save_current_note(auto=False); app.update()
_ud_kept = isinstance((app.find_note(_ud_id) or {}).get('_prev'), dict)
app._body_undo_redo('undo'); app.update()
app.save_current_note(auto=False); app.update()
_ud = app.find_note(_ud_id) or {}
check(f"a big deletion's copy is spent once Undo has brought the words back, "
      f"and the button goes (kept after the delete: {_ud_kept}; body {_ud.get('body')!r})",
      _ud_kept and _ud.get('_prev') is None
      and _ud.get('body', '').rstrip('\n') == 'a long text that a slip of the hand is about to delete whole'
      and not app.restore_prev_btn.winfo_ismapped())
# ...and the same note wiped again, a new line typed before the autosave
# (the owner's test case 692, 2026-10-24). A short note's text, replaced,
# shrank by under 40 characters, and the copy was decided by how much
# shorter the text got: no copy, no button, the words gone. It is decided
# by what of the old text is gone now (rescue_copy_due).
app.title_entry.delete(0, 'end')
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'Buy milk\nCall mom\nPay the rent')
app.save_current_note(auto=False); app.update()
app.body_text.edit_separator()
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'A new line')
app._flush_autosave(); app.update()
_rp = app.find_note(_ud_id) or {}
check(f"a short note replaced by a new line before the autosave keeps its words "
      f"for Restore previous, the button there ({(_rp.get('_prev') or {}).get('body')!r})",
      (_rp.get('_prev') or {}).get('body') == 'Buy milk\nCall mom\nPay the rent'
      and app.restore_prev_btn.winfo_ismapped())

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

# ============================================================
# CANCEL MEANS STAY -- ON EVERY ROUTE THAT WOULD REPLACE THE EDITOR
# ============================================================
# Leaving a note whose date its save could not store asks about it, and
# going back must mean staying. It was found with a day of a repeating note,
# whose way out once asked what Save applied to: Cancel was a silent
# "discard" -- save_current_note returned without saving, the flush never
# said so, and the caller loaded what came next anyway. A day now saves to
# itself, asking nothing; the question that remains on the way out is the
# date's ("Part of this note isn't saved"), and "Go back and fix it" means
# "take me back", as in every other dialog.
_cs_notes = [
    {'id': 90, 'title': 'Weekly sync', 'body': 'agenda', 'category': 'General',
     'date': '2026-09-07', 'recurrence': {'freq': 'weekly', 'weekdays': [0]},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': []},
    {'id': 91, 'title': 'Something else', 'body': 'x', 'category': 'General',
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': []},
]


def _cs_reset():
    app.notes = [NO.normalize_note(dict(n)) for n in _cs_notes]
    app.save_notes()
    app.refresh_note_list(); app.update()


def _cs_on_the_edited_day():
    """The series on screen, typed into, with a date its save cannot
    store."""
    app.open_note_in_tab(app.find_note(90), flush=False)
    app.update()
    app.body_text.insert('end-1c', ' EDITED')
    app.date_entry.delete(0, 'end')
    app.date_entry.insert(0, '31/09/2026')
    app.update()


def _cs_still_there():
    return (app.selected_note_id == 90
            and app.current_occurrence_date is None
            and 'EDITED' in app.body_text.get('1.0', 'end-1c')
            and app._typed_date() == '31/09/2026')


def _cs_other():
    """Note 91 -- put back if a broken fix let a delete through, so that a
    red here stays a red and never becomes a crash before the footer."""
    note = app.find_note(91)
    if note is None:
        app.notes.append(NO.normalize_note(dict(_cs_notes[1])))
        app.save_notes()
        note = app.find_note(91)
    return note


def _cs_back_on_the_day():
    """Put the edited day back on screen if a broken fix navigated away."""
    if not _cs_still_there():
        _cs_on_the_edited_day()


_cs_reset()
_cs_on_the_edited_day()
_cs_asked = []
_cs_real_dialog = app._themed_dialog
app._themed_dialog = lambda title, *a, **k: (_cs_asked.append(title), False)[1]
app.open_note_in_tab(_cs_other()); app.update()
check(f'going back on the way-out question keeps the note when opening another '
      f'note ({_cs_asked[:1]})',
      _cs_still_there() and _cs_asked[:1] == ["Part of this note isn't saved"])
_cs_back_on_the_day()
app._shortcut_new_note(); app.update()
check('...and when pressing Ctrl+N', _cs_still_there())
_cs_back_on_the_day()
app.open_blank_tab(); app.update()
check('...and on the + New Note button', _cs_still_there())
# (Another note's Delete keeps the editor where it is, and so asks no
# way-out question at all: qa5, "A ROUTE THAT KEEPS THE EDITOR DOES NOT ASK
# THE LEAVING QUESTION".)
_cs_back_on_the_day()
_cs_way_back = {"year": 2026, "month": 9, "date_str": "2026-09-21",
                "origin": "edit"}
app._pending_calendar_return = dict(_cs_way_back)
app._ctx_open(_cs_other(), None, return_day='2026-09-30'); app.update()
check('...and the way back to the calendar is still the day it was, '
      'not re-pointed at the note that did not open',
      _cs_still_there() and app._pending_calendar_return == _cs_way_back)
app._pending_calendar_return = None
app._update_calendar_return_button()
_cs_back_on_the_day()
# Closing: the window must stay. destroy is stood in for, so that a broken
# fix fails this check instead of taking the rest of the file with it.
_cs_closed = []
app.destroy = lambda: _cs_closed.append(1)
try:
    app.on_app_close(); app.update()
finally:
    del app.destroy
check('...and closing the window, which stays open on the edited note',
      not _cs_closed and _cs_still_there())
# THE CONTROL: the other answer saves what it can and moves on.
_cs_back_on_the_day()
app._themed_dialog = lambda title, *a, **k: True        # "Continue without it"
app.open_note_in_tab(_cs_other()); app.update()
check('answering "Continue without it" saves the rest and moves on',
      app.selected_note_id == 91
      and 'EDITED' in (app.find_note(90).get('body') or '')
      and app.find_note(90).get('date') == '2026-09-07')
app._themed_dialog = _cs_real_dialog

# ============================================================
# A QUESTION ON SCREEN HOLDS THE GLOBAL SHORTCUTS
# ============================================================
# The dialog's grab confines the POINTER; keys bound with bind_all still
# ran underneath it. Ctrl+S pressed twice stacked the same question on
# itself, and Ctrl+N under it cleared the editor -- found under a day's own
# question, whose answer then wrote the edit under a day of None. The
# question here is the one Ctrl+S raises over a date it could not store. The
# shortcuts are asked from inside the question's own wait -- where a
# person's keypress would land.
def _cs_press(label):
    app.update()
    for frame in app.place_slaves():
        stack = [frame]
        while stack:
            w = stack.pop()
            if isinstance(w, tk.Button) and str(w.cget('text')) == label:
                w.invoke()
                return True
            stack.extend(w.winfo_children())
    return False


_cs_reset()
_cs_on_the_edited_day()
_cs_questions = []


def _cs_answer(_var):
    _cs_questions.append(1)
    if len(_cs_questions) == 1:
        app._shortcut_save_now()
        app._shortcut_new_note()
        app.update()
    # A question stacked on this one (only possible if the shortcuts ran
    # underneath) is answered the way a person clicking through would,
    # which is what lets Ctrl+N go on to clear the editor -- the damage
    # the checks below are about.
    _cs_press('OK')


# This file answers every warning for itself (its top); this one must ask.
_cs_warn_stub = app.__dict__.pop('show_warning', None)
app.wait_variable = _cs_answer
try:
    app._shortcut_save_now(); app.update()
finally:
    del app.wait_variable
    if _cs_warn_stub is not None:
        app.show_warning = _cs_warn_stub
check(f'a shortcut pressed under the question does not stack a second one '
      f'({len(_cs_questions)} asked)',
      len(_cs_questions) == 1)
check('...nor clear the editor underneath it',
      app.selected_note_id == 90 and _cs_still_there())
check('...and the save the question followed is the note\'s own',
      'EDITED' in (app.find_note(90).get('body') or '')
      and app.find_note(90).get('date') == '2026-09-07')
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()

# ============================================================
# THE KEYBOARD GOES BACK WHERE IT WAS AFTER A QUESTION
# ============================================================
# The dialog takes the focus onto its own button and is then destroyed;
# Tk handed the keyboard to the bare window, and typing went nowhere until
# the person clicked back in. What is asserted is the dialog's decision --
# it hands the keyboard back to the body -- recorded where it is made.
app.open_note_in_tab(_cs_other()); app.update()
_cs_body_ready = _c9_take(app.body_text)
_cs_given_back = []
app.body_text.focus_set = lambda *a, **k: _cs_given_back.append('body')
app.wait_variable = lambda _var: _cs_press('No')
del app.ask_yes_no
try:
    app.ask_yes_no('Delete note', 'Move it to the Trash?', icon='warning',
                   default='no')
finally:
    del app.wait_variable
    del app.body_text.focus_set
    app.ask_yes_no = lambda *a, **k: True
check('after a question is answered, the keyboard is handed back to the note',
      _cs_body_ready and _cs_given_back == ['body'])

# ============================================================
# A CELL EDITOR DOES NOT OUTLIVE ITS TABLE
# ============================================================
# Opening another note tore the table down and the open cell's editor with
# it, and nothing cleared the record: Bold, Italic and the colours then
# aimed at a dead widget on the next note, did nothing, and raised.
app.notes = [NO.normalize_note(n) for n in (
    {'id': 95, 'title': 'Table note',
     'body': '| a | b |\n| --- | --- |\n| 1 | 2 |\n', 'category': 'General'},
    {'id': 96, 'title': 'Plain', 'body': 'hello world', 'category': 'General'})]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.find_note(95)); app.update()
_cs_grids = list(getattr(app, '_table_grids', []) or [])
check('fixture: the table is drawn as a grid', bool(_cs_grids))
if _cs_grids:
    app._open_cell_editor(_cs_grids[0], 1, 0)
    app.update()
    _cs_entry = (app._cell_editor or {}).get('entry')
    if _cs_entry is not None:
        _cs_entry.insert('end', 'pear')
check('fixture: a cell editor is open', app._cell_editor is not None)
app.open_note_in_tab(app.find_note(96)); app.update()
check('the cell editor is gone with the table it was drawn in',
      app._cell_editor is None)
check('...and the typing in it was kept',
      'pear' in (app.find_note(95).get('body') or ''))
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', '1.0', '1.5')
_cs_raised = None
try:
    app._toggle_body_style('bold')
    app.update()
except Exception as _e:
    _cs_raised = _e
check('...so Bold works on the next note instead of raising',
      _cs_raised is None and 'bold' in app.body_text.tag_names('1.2'))

# ---- A day left open on the Calendar is not rebuilt behind the Notes tab ----
# Every autosave rebuilt it, walking every note, on a tab nobody was looking
# at. It is brought up to date when the Calendar is shown again, as the
# month itself is (render_calendar).
app.notes = [NO.normalize_note({'id': 501, 'title': 'DayPanelNote', 'body': 'x',
                                'date': '2026-07-15'})]
app.save_notes(); app.refresh_note_list()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar()
app.open_day_popup('2026-07-15'); app.update()
check('fixture: the day is open on the Calendar',
      app._day_panel_mode == 'list'
      and any('DayPanelNote' in t for t in find_all_labels(app.day_panel)))
app.notebook.select(app.TAB_NOTES); app.update()
app.open_note_in_tab(app.find_note(501)); app.update()
_dp_rebuilt = []
_dp_real = app.show_day_list
app.show_day_list = lambda *a, **k: (_dp_rebuilt.append(1), _dp_real(*a, **k))[1]
try:
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'DayPanelRenamed')
    app.save_current_note(auto=True); app.update()
    _dp_behind = len(_dp_rebuilt)
    app.notebook.select(app.TAB_CALENDAR); app.update()
finally:
    app.show_day_list = _dp_real
check(f'a save made on the Notes tab does not rebuild the day left open on the '
      f'Calendar ({_dp_behind} rebuilds)', _dp_behind == 0
      and app.find_note(501)['title'] == 'DayPanelRenamed')
check('...and the day shows the change when the Calendar is shown again',
      len(_dp_rebuilt) >= 1
      and any('DayPanelRenamed' in t for t in find_all_labels(app.day_panel)))

# ---- KEYBOARD: a day's list, the History register and the reminder ----
# Their rows and words were bound to the mouse alone: an open day's notes
# could not be opened from the keyboard, nor a History row, nor today's
# reminder answered.
import time as _kc_time


def _kc_settle(n=6):
    for _ in range(n):
        app.update()
        _kc_time.sleep(0.02)


from _qa_support import take_focus as _qa_take_focus  # noqa: E402


def _kc_take(w, cap_s=2.0):
    return _qa_take_focus(app, w, cap_s)


def _kc_rows(top):
    found = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Frame) and getattr(c, '_key_press', None):
                found.append(c)
            walk(c)
    walk(top)
    return found


app.new_note()
app.notes = [{'id': 901, 'title': 'KeyDay', 'body': 'x', 'category': 'General',
              'date': '2026-10-02', 'created': '2026-01-01 00:00',
              'updated': '2026-01-01 00:00', 'checklist': [], 'attachments': []}]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR)
app.cal_year, app.cal_month = 2026, 10
app.render_calendar()
_kc_settle()
app.open_day_popup('2026-10-02')
_kc_settle()
_kc_list = _kc_rows(app.day_panel)
_kc_menus = []
app.show_note_context_menu = lambda e, n, occurrence_date=None: _kc_menus.append(
    (n.get('title'), occurrence_date))
try:
    if _kc_list and _kc_take(_kc_list[0]):
        _kc_list[0].event_generate('<Shift-F10>')
        _kc_settle()
finally:
    del app.show_note_context_menu
check(f'Shift+F10 on a day\'s note row opens that note\'s menu, as a right-click '
      f'does ({_kc_menus})', _kc_menus == [('KeyDay', '2026-10-02')])
_kc_list = _kc_rows(app.day_panel)
if _kc_list and _kc_take(_kc_list[0]):
    _kc_list[0].event_generate('<Return>')
    _kc_settle()
check(f'Return on a day\'s note row opens the note in the day\'s panel '
      f'({app._day_panel_mode})', bool(_kc_list) and app._day_panel_mode == 'note')
app._toggle_calendar_history()
_kc_settle(10)
_kc_hist = _kc_rows(app._history_rows)
if _kc_hist and _kc_take(_kc_hist[0]):
    _kc_hist[0].event_generate('<Return>')
    _kc_settle()
check(f'Return on a History row opens its day on the month '
      f'({app._history_visible}, {app.selected_day})',
      bool(_kc_hist) and not app._history_visible
      and app.selected_day == '2026-10-02')
app._render_reminder_bar(1, '2026-10-02')
_kc_settle()
_kc_close = [w for w in app.reminder_bar.winfo_children()
             if isinstance(w, tk.Label) and str(w.cget('text')) == '✕']
if _kc_close and _kc_take(_kc_close[0]):
    _kc_close[0].event_generate('<space>')
    _kc_settle()
check('the reminder\'s ✕ is a Tab stop, and Space closes the reminder',
      bool(_kc_close) and str(_kc_close[0].cget('takefocus')) == '1'
      and not app._is_placed(app.reminder_bar))

# The month itself: one canvas bound to the mouse alone, so the keyboard
# could only change month, never reach a day.
app.notebook.select(app.TAB_CALENDAR)
app.close_day_panel()
app.cal_year, app.cal_month = 2030, 6
app._cal_key_day = None
app.render_calendar()
_kc_settle()
_kc_cv = app.cal_canvas


def _kc_ring_on():
    """The day the keyboard's ring is drawn round, read from the drawing."""
    items = _kc_cv.find_withtag('cal_key')
    if len(items) != 1 or str(_kc_cv.itemcget(items[0], 'outline')).lower() \
            != app._focus_ring().lower():
        return None
    box = tuple(int(round(v)) for v in _kc_cv.coords(items[0]))
    for date_str, rec in app._cal_cells.items():
        if box == (rec['x0'] - 2, rec['y0'] - 2, rec['x1'] + 2, rec['y1'] + 2):
            return date_str
    return None


def _kc_key(key):
    if _kc_take(_kc_cv):
        _kc_cv.event_generate(key)
        _kc_settle()


_kc_chain, _kc_at = [], str(app._history_toggle_btn)
for _ in range(20):
    _kc_at = str(app.tk.call('tk_focusNext', _kc_at))
    _kc_chain.append(_kc_at)
check('the month is a Tab stop, reached from the calendar\'s header',
      str(_kc_cv) in _kc_chain)
_kc_take(_kc_cv)
_kc_settle()
_kc_first = _kc_ring_on()
_kc_steps = []
for _kc_k in ('<Right>', '<Down>', '<Left>', '<Up>'):
    _kc_key(_kc_k)
    _kc_steps.append(_kc_ring_on())
check(f'with the keyboard on the month a ring is drawn round its first day, and '
      f'the arrows walk it a day and a week ({_kc_first}, {_kc_steps})',
      _kc_first == '2030-06-01'
      and _kc_steps == ['2030-06-02', '2030-06-09', '2030-06-08', '2030-06-01'])
_kc_key('<Left>')
check(f'an arrow off the month\'s edge turns to the next one '
      f'({app.cal_year}-{app.cal_month}, {_kc_ring_on()})',
      (app.cal_year, app.cal_month) == (2030, 5) and _kc_ring_on() == '2030-05-31')
_kc_key('<Next>')
check(f'Page Down keeps the ring on the same day of the month, as far as the '
      f'month goes ({_kc_ring_on()})', _kc_ring_on() == '2030-06-30')
_kc_key('<Return>')
check(f'Return opens the day, as a click does ({app.selected_day}, '
      f'{app._day_panel_mode})',
      app.selected_day == '2030-06-30' and app._day_panel_mode == 'list')
_kc_menus = []
app.show_day_context_menu = lambda e, d: _kc_menus.append((d, e.widget))
try:
    _kc_key('<Shift-F10>')
finally:
    del app.show_day_context_menu
check(f'Shift+F10 opens the day\'s right-click menu, at the day ({_kc_menus})',
      _kc_menus == [('2030-06-30', _kc_cv)])
# The menu's colour palette, asked for from the keyboard, takes it.
_kc_asked = []
_kc_real_focus_set = tk.Misc.focus_set
tk.Misc.focus_set = lambda self: (_kc_asked.append(self), _kc_real_focus_set(self))[1]
try:
    if _kc_take(_kc_cv):
        # The event the day's menu hands its "Color this day..." entry.
        app._color_day('2030-06-30', type('E', (), {
            'widget': _kc_cv, 'x_root': _kc_cv.winfo_rootx() + 10,
            'y_root': _kc_cv.winfo_rooty() + 10})())
        _kc_settle()
finally:
    tk.Misc.focus_set = _kc_real_focus_set
_kc_pop = app._mini_popup
check(f'"Color this day..." from the keyboard opens the palette with the keyboard '
      f'in it ({_kc_asked[-1:]})',
      _kc_pop is not None and any(str(w).startswith(str(_kc_pop) + '.')
                                  for w in _kc_asked))
app._dismiss_mini_popup()
app.close_day_panel()
_kc_settle()
app.notebook.select(app.TAB_NOTES)
app.notes = []
app.save_notes()
_kc_settle()

print(f"=== QA7 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
