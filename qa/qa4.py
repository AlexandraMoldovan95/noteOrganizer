# HERMETIC SEED -- BEFORE the note_organizer import below: the module
# resolves its data directory and runs the data MIGRATIONS at import
# time, so this script's data directory must be its own before that
# happens. hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to
# run at all outside a scratch run, or beside a notebook it cannot
# prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import note_organizer as NO, tkinter as tk, time
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         pin_popup_visibility as _qa_pin)
_qa_pin(NO)
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

def safe(name, fn):
    try:
        fn()
        check(name, True)
    except Exception as e:
        check(f'{name} ({type(e).__name__}: {e})', False)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.geometry('1100x850'); app.update()

# ---- THEME SWITCHING ----
def theme_stress():
    for _ in range(15):
        app.toggle_theme()
        app.update()
safe('theme toggle stress (15x, no freeze)', theme_stress)

# theme correctness: note card picks up new colors
app.set_theme('dark'); app.update()  # known starting point after the toggle stress above
app.notes.append({'id':1,'title':'ThemeNote','body':'x','category':'General',
                  'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
                  'checklist':[],'attachments':[]})
app.refresh_note_list(); app.update()
def find_card_bg():
    # The list is a drawing: the first drawn card's own fill.
    order = app._card_order()
    return str(app._card_view(order[0])['bg']) if order else None
before = find_card_bg()
app.set_theme('light'); app.update()
after = find_card_bg()
check('note card color updates on theme switch', before != after and after==app.colors['card'])

app.set_theme('dark'); app.update()

# ---- POPUP STRESS: rapid open/dismiss ----
NO.CATEGORY_COLORS.setdefault('PopupTestCat', '#7c5cff')
def popup_stress():
    app.show_settings_page(); app.update()
    app.toggle_settings_panel('categories'); app.update()
    for _ in range(5):
        app._show_color_palette(app, '#111111', lambda c: None)
        app.update()
        app._dismiss_mini_popup()
        app.update()
safe('rapid popup open/dismiss (5x, no freeze)', popup_stress)

# ---- SETTINGS PANEL STRESS: rapid toggling ----
def panel_stress():
    app.show_settings_page(); app.update()
    for _ in range(3):
        for p in ['categories','trash','duplicates','templates']:
            app.toggle_settings_panel(p)
            app.update()
safe('rapid settings panel toggling (no freeze)', panel_stress)

# ---- MEMORY LEAK CHECK: themed_widgets should stay flat ----
app.notes = [{'id':i,'title':f'N{i}','body':'x','category':'General',
             'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
             'checklist':[],'attachments':[]} for i in range(100)]
app.refresh_note_list(); app.render_calendar(); app.update()
before_widgets = len(app.themed_widgets)
for _ in range(10):
    app.refresh_note_list()
    app.render_calendar()
    app.update()
after_widgets = len(app.themed_widgets)
check(f'themed_widgets stays flat over 10 refreshes ({before_widgets} -> {after_widgets})',
      after_widgets==before_widgets)

# attachments list leak check
app.load_note(app.notes[0])
before_att = len(app.themed_widgets)
for _ in range(10):
    app.current_attachments = [{'filename':f'f{i}.txt','stored_as':'x'} for i in range(3)]
    app.refresh_attachments_list()
    app.update()
after_att = len(app.themed_widgets)
check(f'attachments list themed_widgets stays flat ({before_att} -> {after_att})',
      after_att==before_att)

# share panel leak check
before_share = len(app.themed_widgets)
for _ in range(10):
    app.toggle_share_panel()
    app.toggle_share_panel()
after_share = len(app.themed_widgets)
check(f'share panel themed_widgets stays flat ({before_share} -> {after_share})',
      after_share==before_share)

# ---- PIN + DUPLICATE UNDER STRESS ----
def pin_dup():
    n = app.notes[0]
    app.toggle_pin(n)
    app.duplicate_note(n)
    app.toggle_pin(n)
safe('pin + duplicate note', pin_dup)

# ---- ATTACHMENTS: copies of a note get their OWN files (audit Z01-F04) ----
# duplicate_note AND the Settings "clean up duplicates" merge both used to
# point the copy/survivor at the SAME file on disk as the source. Deleting
# one note then deleted the file out from under the other — for cleanup,
# the auto-purge of the trashed twin is guaranteed to destroy the very file
# the merge exists to preserve. Each copy must own its files.
import os as _os4
from noteorganizer.core import paths as _paths4
from noteorganizer.core import storage as _storage4
from noteorganizer.core import model as _model4
_os4.makedirs(_paths4.ATTACHMENTS_DIR, exist_ok=True)

def _mk_att4(name, text="payload"):
    p = _os4.path.join(_paths4.ATTACHMENTS_DIR, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p

# -- duplicate_note (the wiring seam no test covered) --
_dup_src = "20260101000000000001_dup.txt"
_dup_src_path = _mk_att4(_dup_src)
app.notes = [{'id': 1, 'title': 'Owns file', 'body': 'x', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': [{'filename': 'dup.txt', 'stored_as': _dup_src}]}]
app.save_notes()
_clone4 = app.duplicate_note(app.notes[0])
app.update()
_clone_name4 = (_clone4.get('attachments') or [{}])[0].get('stored_as')
check('duplicate_note: the copy gets a DIFFERENT attachment filename',
      bool(_clone_name4) and _clone_name4 != _dup_src)
check('duplicate_note: the copy has its own file on disk',
      bool(_clone_name4)
      and _os4.path.isfile(_os4.path.join(_paths4.ATTACHMENTS_DIR, _clone_name4)))
_storage4._delete_attachment_files([_clone4])
check('duplicate_note: deleting the copy leaves the original file intact',
      _os4.path.isfile(_dup_src_path))

# -- duplicate_note and the note's IDENTITY --
#
# Same seam, same shape of bug as the attachment above: a deep copy
# carries something that was never meant to be shared. Two notes with one
# uid is the exact collision uid exists to prevent, manufactured locally
# by a feature that has nothing to do with sharing -- and nothing would
# look wrong until a share code or an import tried to tell them apart.
_ident_src = _model4.normalize_note(
    {'id': 1, 'title': 'Are identitate', 'body': 'x'})
app.notes = [_ident_src]
app.save_notes()
_ident_clone = app.duplicate_note(app.notes[0])
app.update()
check('duplicate_note: the original still has its identity',
      bool(_ident_src.get('uid')))
check('duplicate_note: the copy is given its OWN identity',
      bool(_ident_clone.get('uid')))
check('duplicate_note: the two identities differ',
      _ident_clone.get('uid') != _ident_src.get('uid'))

# -- Settings "clean up duplicates" merge (GAP found by the Fix-1 reviewer) --
_merge_src = "20260101000000000002_merge.txt"
_merge_src_path = _mk_att4(_merge_src)
_kept4 = {'id': 10, 'title': 'Dup', 'body': 'same', 'category': 'General',
          'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
          'checklist': [], 'attachments': []}
_removed4 = {'id': 11, 'title': 'Dup', 'body': 'same', 'category': 'General',
             'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
             'checklist': [], 'attachments': [{'filename': 'merge.txt', 'stored_as': _merge_src}]}
app.notes = [_kept4, _removed4]
app.trash = []
_group4 = [_kept4, _removed4]
class _V4:
    def __init__(self, v): self._v = v
    def get(self): return self._v
_orig_ask4 = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
try:
    app._cleanup_selected_duplicates(
        [(_V4(False), _kept4, _group4), (_V4(True), _removed4, _group4)],
        None, refresh=lambda: None, announce=False)
finally:
    app.ask_yes_no = _orig_ask4
app.update()
_merged4 = [a.get('stored_as') for a in _kept4.get('attachments', [])]
check('cleanup-duplicates: survivor gets the merged file under its OWN name',
      len(_merged4) == 1 and _merged4[0] != _merge_src
      and _os4.path.isfile(_os4.path.join(_paths4.ATTACHMENTS_DIR, _merged4[0])))
# The trashed twin still points at the original file; its later purge must
# not delete the survivor's copy.
_storage4._delete_attachment_files([_removed4])
check('cleanup-duplicates: purging the trashed twin leaves the survivor file intact',
      len(_merged4) == 1
      and _os4.path.isfile(_os4.path.join(_paths4.ATTACHMENTS_DIR, _merged4[0])))

# ---- THEME: long-lived borders and hover follow a switch (Z07-F03/F04) ----
# The 0.66.97 lesson, reaching the instances it missed: a long-lived
# widget must track EVERY colour option it sets (the dropdown/category
# borders and the export progress frame stayed on the build-time
# palette), and hover colours must be computed at event time (a tracked
# settings button hovered in whatever theme it was built under).
app.set_theme('dark'); app.update()
_probe_btn = app._settings_big_button(app, 'ThemeProbe', lambda: None,
                                      kind='danger')
_probe_btn.pack(); app.update()
_probe_dd = app._build_themed_dropdown(app, tk.StringVar(value='x'),
                                       ['x', 'y'], lambda v: None)
_probe_dd.pack(); app.update()
# Assert under BOTH themes: the app itself was built under the default
# palette, so a widget frozen at build time still matches ONE theme by
# coincidence — it cannot match both.
def _borders_ok():
    return (str(app.category_menu.cget('highlightbackground')) == app.colors['card'],
            str(_probe_dd.cget('highlightbackground')) == app.colors['card'],
            str(app.export_progress_frame.cget('highlightbackground')) == app.colors['accent']
            and str(app.export_progress_frame.cget('bg')) == app.colors['card'])
_dark_ok = _borders_ok()
app.set_theme('light'); app.update()
_light_ok = _borders_ok()
check('the category button border follows the theme switch',
      _dark_ok[0] and _light_ok[0])
check('a themed dropdown border follows too',
      _dark_ok[1] and _light_ok[1])
# Behaviour AND mechanism: _recolor_stragglers (the safety net) remaps
# stray bg/fg on every switch, and the stock dark/light accents are the
# same hex — so on these two themes the net masks a missing tracking
# entry. The net is the fallback, not the mechanism; assert the frame is
# genuinely registered, the way the rest of the long-lived family is.
check('the export progress frame follows (it was never tracked at all)',
      _dark_ok[2] and _light_ok[2]
      and any(w is app.export_progress_frame for w, _m in app.themed_widgets))
_qa_fire(_probe_btn, '<Enter>'); app.update()
check('a settings button hovers in the CURRENT palette, not the build-time one',
      str(_probe_btn.cget('bg'))
      == app._blend(app.colors['card'], app.colors['danger'], 0.14))
_qa_fire(_probe_btn, '<Leave>'); app.update()
check('and rests back on the current card colour',
      str(_probe_btn.cget('bg')) == app.colors['card'])
# The other button factory has the same hover mechanism — build under
# light, switch to dark, hover must paint dark's palette.
_probe_txt = app._text_button(app, 'TxtProbe', lambda: None, kind='primary')
_probe_txt.pack(); app.update()
app.set_theme('dark'); app.update()
_qa_fire(_probe_txt, '<Enter>'); app.update()
check('a text button hovers in the current palette too',
      str(_probe_txt.cget('bg')) == app.colors['accent_hover'])
# Mechanism assert: the stock dark/light accents share a hex, so a
# frozen ring matches the palette by coincidence (the export-frame
# lesson, same file, a few checks up).
check('and its ring is tracked, not frozen at build',
      str(_probe_txt.cget('highlightbackground')) == app.colors['accent']
      and any(w is _probe_txt and m.get('highlightbackground') == 'accent'
              for w, m in app.themed_widgets))
_probe_btn.destroy(); _probe_dd.destroy(); _probe_txt.destroy(); app.update()

# ---- THEME sweep round 2: caret, checkbox wells, press colours ----
# The adversarial review widened the class: every long-lived text field's
# caret (insertbackground) was frozen at build — invisible after a
# dark<->light switch, the main editor included; the recurrence radios'
# selectcolor and the checklist rows' wells stayed on the old palette;
# Back to Notes pressed in the old theme's colours.
# Checklist rows are built while the section is OPEN (a closed section
# builds none since the checklist learned to touch one row at a time);
# open it, as a person must to reach the box that adds an item, and put it
# back after the check.
_cl_was_open = app._checklist_open
if not _cl_was_open:
    app.toggle_checklist_section()
app.checklist_add_var.set('bifa')
app._add_checklist_item()
app.update()
def _caret_ok():
    return (str(app.body_text.cget('insertbackground')) == app.colors['text']
            and str(app.title_entry.cget('insertbackground')) == app.colors['text']
            and str(app.comments_text.cget('insertbackground')) == app.colors['text'])
def _wells_ok():
    # Asked for the SIDEBAR colour by name until the wells moved to their
    # own palette entry. Naming a colour made the check agree with the
    # bug it sat next to: a well the same value as the surface behind it
    # passed happily, which is how a ticked box came to look like an
    # empty one on every dark theme. What matters is that the well is
    # still the palette's (so a theme switch cannot leave it stale) AND
    # that it is not the surface it sits on.
    hits = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Checkbutton):
                well = str(c.cget('selectcolor'))
                hits.append(well == app.colors['check_well']
                            and well != str(c.cget('bg')))
            walk(c)
    walk(app.checklist_items_frame)
    return bool(hits) and all(hits)
def _find_btn_text(root, txt):
    for c in root.winfo_children():
        if isinstance(c, tk.Button) and str(c.cget('text')) == txt:
            return c
        r = _find_btn_text(c, txt)
        if r:
            return r
    return None
_dark2 = (_caret_ok(), _wells_ok())
app.set_theme('light'); app.update()
_light2 = (_caret_ok(), _wells_ok())
check('the caret follows the theme in body, title and comments',
      _dark2[0] and _light2[0])
check('checklist checkbox wells stay readable across a theme switch',
      _dark2[1] and _light2[1])
if not _cl_was_open and app._checklist_open:
    app.toggle_checklist_section()
check('recurrence radios still have their well tracked, so it cannot go stale',
      any(isinstance(w, tk.Radiobutton) and m.get('selectcolor') == 'card'
          for w, m in app.themed_widgets))
_back2 = _find_btn_text(app.settings_page, 'Back to Notes') \
    if hasattr(app, 'settings_page') else None
check('Back to Notes presses in the live palette',
      _back2 is not None
      and str(_back2.cget('activebackground')) == app.colors['card']
      and str(_back2.cget('activeforeground')) == app.colors['text'])

# ---- THEME registry prunes its dead (the revisit leak) ----
# Rebuilt Settings panels re-track their widgets on every visit; the
# registry kept the destroyed entries forever, growing without bound.
_dead_probe = tk.Label(app, text='soon gone')
app.track_theme(_dead_probe, bg='card')
_dead_probe.destroy()
app.toggle_theme(); app.update()
check('a theme switch prunes destroyed widgets from the registry',
      not any(w is _dead_probe for w, _m in app.themed_widgets))
app.toggle_theme(); app.update()

# ---- PERFORMANCE: note list with larger count ----
# This check used to assert a literal True: it measured the time, printed
# it into its own label, and passed unconditionally. It was the only
# guard over the note list's rebuild cost -- the thing the product review
# calls "every pause in typing freezes the app" -- and it could not fail.
# Recorded as T1-4 in docs/PRODUCT_FINDINGS.md.
#
# It asserts two things now, and neither is a timing opinion.
#
# First, that the work actually happened. A rebuild that silently stopped
# building cards would be instant, and a pure stopwatch would applaud it.
#
# Second, a ceiling far above the real numbers rather than near them.
# Measured three runs per platform on an idle machine: Windows
# 1153/1625/1608 ms, Linux 508/446/462 ms. Windows is the slow side, so
# the budget is built from it -- 8 s is five times its worst run. That
# will not catch a 20% drift, and is not meant to: a check that fires on
# 20% is a check that fires on a busy CI runner, and this project has
# already thrown away a day to a flaky check. It catches the thing worth
# catching, which is an accidental order-of-magnitude.
#
# The first half changed shape when the list stopped being drawn whole: a
# rebuild draws LIST_FIRST_DRAW rows and the rest as the view comes near
# them. So "the work actually happened" is asked twice -- the first draw is
# exactly the first rows, and scrolling to the end draws every one of the
# 300 in the list's own order. A rebuild that silently stopped building
# cards fails both, and so does one that went back to drawing everything.
NOTE_LIST_BUDGET_MS = 8000
# A clean editor first. Whatever an earlier block left in it (the checklist
# item above, on a note from an older fixture) is otherwise saved by a late
# autosave INTO this fixture -- a 301st note, and the counts below read one
# card too many whenever the timer lost the race. Every real delete route
# saves the editor first; the checks here call _delete_note directly.
app.new_note(); app.update()
app.notes = [{'id':i,'title':f'Perf{i}','body':'x'*30,'category':'General',
             'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
             'checklist':[],'attachments':[]} for i in range(300)]
app.canvas.yview_moveto(0); app.update()
t0=time.perf_counter()
app.refresh_note_list()
app.update()
elapsed=(time.perf_counter()-t0)*1000
_cards_built = len(app._card_order())
_first_draw = app.LIST_FIRST_DRAW
# The numbers go at the END of the names: a mutant that changes the
# constant must not change the name a runner looks for.
check(f'a rebuild draws only the first screenful of cards straight away '
      f'({_cards_built} of 300; LIST_FIRST_DRAW is {_first_draw})',
      _cards_built == _first_draw < 300)
check(f'...and holds the rest ready below them '
      f'({len(app._list_pending)} waiting)',
      len(app._list_pending) == 300 - _first_draw)
check(f'...and stays inside its budget ({elapsed:.0f}ms of '
      f'{NOTE_LIST_BUDGET_MS}ms; measured 1.2-1.6s on Windows, 0.5s on Linux '
      f'when it still drew all 300)',
      elapsed < NOTE_LIST_BUDGET_MS)
_perf_steps = 0
while app._list_pending and _perf_steps < 100:
    app.canvas.yview_moveto(1.0)
    app.update()
    _perf_steps += 1
_perf_order = app._card_order()
_perf_rows = [r[1]['id'] for r in app._list_rows() if r[0] == 'note']
check(f'scrolling to the end draws every card, in the list\'s own order '
      f'({len(_perf_order)} of 300, in {_perf_steps} steps)',
      len(_perf_order) == 300 and _perf_order == _perf_rows)

# ---------------------------------------------------------------------
# THE LIST DRAWS WHAT YOU CAN SEE
#
# Three promises, each with the mechanism that used to break it:
#   1. two handlers that only care about the window -- the title bar's
#      paint on <Map> and the calendar's width step -- no longer run once
#      per widget. Bound with self.bind they ran 1,939 and 3,882 times for
#      one rebuild of 300 notes. The paint listens to the window alone; the
#      step listens to the calendar's own grid, which also hears the resize
#      made while the calendar was hidden (the storm used to cover that);
#   2. the list draws rows as the view comes near them: the scroll, the
#      keyboard's walk and a list shorter than its window all draw more,
#      and a deletion or a group's count reaches rows not drawn yet;
#   3. a save redraws the saved note's card alone, and the list it leaves
#      is the list a full rebuild would draw.
# The image preview's half of the same work is in qa7.
# ---------------------------------------------------------------------


def _ls_settle(n=3):
    for _ in range(n):
        app.update()
        app.update_idletasks()


def _ls_keys():
    return list(app._list_drawn_keys) + [
        (r[0], r[1] if r[0] == 'header' else r[1]['id'])
        for r in app._list_pending]


def _ls_snapshot():
    """What the drawn list shows, card by card and header by header, in
    the order it stands on screen -- read back from the drawing, with the
    place of each row, so a card left out of its slot shows too."""
    shown = []
    for key in app._list_drawn_keys:
        if key[0] == 'note':
            v = app._card_view(key[1])
            shown.append(('note', key[1], v['title'], v['preview'], v['tags'],
                          str(v['stripe']), str(v['ring']), v['y0'], v['y1']))
        else:
            v = app._header_view(key[1])
            shown.append(('header', key[1], v['label'], v['caret'], v['y0'], v['y1']))
    # Anything drawn that no row owns -- left behind by an update that
    # forgot to delete it. Recorded as a difference, never a crash.
    owned = {rec['tag'] for rec in app._list_drawn}
    loose = set()
    for item in app.canvas.find_withtag('row'):
        tags = [t for t in app.canvas.gettags(item) if t.startswith(('card', 'hdr'))]
        if tags and tags[0] not in owned:
            loose.add(tags[0])
    if loose:
        shown.append(('drawn but nobody owns it', tuple(sorted(loose))))
    return shown


def _ls_same_as_rebuild():
    """The list as it stands, against the list a full rebuild draws. A
    rebuild may draw a different depth, so the drawn part is compared as
    far as both reach, and the order of every row -- drawn or waiting --
    in full."""
    before, before_keys = _ls_snapshot(), _ls_keys()
    app.refresh_note_list(); _ls_settle()
    after, after_keys = _ls_snapshot(), _ls_keys()
    common = min(len(before), len(after))
    return common > 0 and before[:common] == after[:common] \
        and before_keys == after_keys


def _ls_search(text):
    """Search for `text` now, not after the typing pause."""
    app.search_var.set(text)
    job = getattr(app, '_search_debounce_job', None)
    if job is not None:
        app.after_cancel(job)
        app._search_debounce_job = None
    app.refresh_note_list(); _ls_settle()


def _ls_scroll_to_end():
    steps = 0
    while app._list_pending and steps < 100:
        app.canvas.yview_moveto(1.0)
        app.update()
        steps += 1


def _ls_card_ids():
    return app._card_order()


def _ls_let_restores_finish():
    """Let a rebuild's scroll restore run its course. It is queued for
    when the app is next idle, then stays in force for 400ms and re-applies
    itself on timers (qa/README) -- read before that, a position is the
    restore's, not the thing under test's; left running, it lands on the
    next check and moves ITS view."""
    end = time.time() + 1.0
    while time.time() < end:
        app.update()
        time.sleep(0.02)


# 1. The window's own handlers. Counted on the instance, which is where
# both bindings look them up each time they run.
_ls_calls = {'paint': 0, 'calendar': 0}
_ls_real_paint = app._paint_title_bar
_ls_real_cal = app._is_calendar_visible


def _ls_paint():
    _ls_calls['paint'] += 1
    return _ls_real_paint()


def _ls_cal():
    _ls_calls['calendar'] += 1
    return _ls_real_cal()


app._paint_title_bar = _ls_paint
app._is_calendar_visible = _ls_cal
try:
    app.canvas.yview_moveto(0); _ls_settle()
    _ls_calls['paint'] = _ls_calls['calendar'] = 0
    app.refresh_note_list(); _ls_settle()
    check(f'a list rebuild runs no window-level handler once per widget '
          f'(title bar {_ls_calls["paint"]}, calendar step '
          f'{_ls_calls["calendar"]}; 1,939 and 3,882 when bound with '
          f'self.bind)', _ls_calls['paint'] == 0 and _ls_calls['calendar'] == 0)
    # The other half: the window's OWN <Map> must still paint the title
    # bar, which is what the binding is for -- a fresh launch otherwise
    # keeps the system colours until a theme is switched.
    _ls_calls['paint'] = 0
    app.withdraw(); _ls_settle()
    app.deiconify()
    _ls_end = time.time() + 5
    while _ls_calls['paint'] == 0 and time.time() < _ls_end:
        app.update(); time.sleep(0.02)
    check(f'...while the window\'s own <Map> still paints its title bar '
          f'({_ls_calls["paint"]})', _ls_calls['paint'] >= 1)
    # And the calendar still takes its width step from the window's own
    # resize, both ways across the 1150-pixel line. On screen, which the
    # Settings page left open by the stress test above would prevent: the
    # step is taken only while the calendar can be seen.
    _ls_settings_was_open = getattr(app, '_settings_open', False)
    if _ls_settings_was_open:
        app.hide_settings_page()
    app.geometry('1100x850'); _ls_settle()
    app.notebook.select(app.TAB_CALENDAR); _ls_settle()
    app._cal_last_font_size = None
    app.geometry('1200x850')
    _ls_end = time.time() + 5
    while app._cal_last_font_size != 11 and time.time() < _ls_end:
        app.update(); time.sleep(0.02)
    _ls_wide = app._cal_last_font_size
    app.geometry('1100x850')
    _ls_end = time.time() + 5
    while app._cal_last_font_size != 9 and time.time() < _ls_end:
        app.update(); time.sleep(0.02)
    check(f'...and the calendar still takes its width step from the '
          f'window\'s resize (wide {_ls_wide}, narrow '
          f'{app._cal_last_font_size})',
          _ls_wide == 11 and app._cal_last_font_size == 9)
    # ...including a resize made while the calendar was NOT showing: the
    # step is taken when it comes back. The window's own <Configure> never
    # reports that -- bound there alone, the calendar kept its small text
    # on a wide window. The old per-widget storm happened to cover it.
    app.notebook.select(app.TAB_NOTES); _ls_settle()
    app.geometry('1200x850'); _ls_settle()
    app.notebook.select(app.TAB_CALENDAR)
    _ls_end = time.time() + 5
    while app._cal_last_font_size != 11 and time.time() < _ls_end:
        app.update(); time.sleep(0.02)
    check(f'...and takes it on coming back to a calendar the window was '
          f'resized away from ({app._cal_last_font_size})',
          app._cal_last_font_size == 11)
    app.notebook.select(app.TAB_NOTES); _ls_settle()
    app.geometry('1100x850'); _ls_settle()
    if _ls_settings_was_open:
        app.show_settings_page(); _ls_settle()
finally:
    app.__dict__.pop('_paint_title_bar', None)
    app.__dict__.pop('_is_calendar_visible', None)

# Activate/Deactivate reach every widget inside a window, so they are
# bound on the two window classes rather than with bind_all -- which ran
# the handler 2,132 times per Alt+Tab for a 300-note list, measured.
check('the activation handlers are not bound on every widget',
      not app.bind_all('<Activate>') and not app.bind_all('<Deactivate>'))
# Asked of the REQUEST the handler makes, recorded as it is made: the watch
# also runs on a 300ms heartbeat of its own, so a check that waited for the
# watch to run passed with the popup's binding gone (a mutant said so).
# Only the Deactivate handler asks for a look 150ms later.
_ls_asked_watch = []
_ls_real_after = app.after


def _ls_after(ms, func=None, *args):
    if getattr(func, '__name__', '') == '_popup_watch_step':
        _ls_asked_watch.append(ms)
    return _ls_real_after(ms, func, *args)


_ls_top = tk.Toplevel(app)
try:
    _ls_settle()
    _ls_top.winfo_id()
    app.after = _ls_after
    try:
        # Processed before event_generate returns: every handler for it
        # has run by the next line.
        _ls_top.event_generate('<Deactivate>')
    finally:
        app.__dict__.pop('after', None)
    check(f'...while a popup window losing the front still asks the '
          f'foreground watch to look ({_ls_asked_watch})',
          _ls_asked_watch == [150])
finally:
    _ls_top.destroy()
    _ls_settle()

# 2. Drawing as the view comes near. The 300 notes from above, from the top.
app.canvas.yview_moveto(0); _ls_settle()
app.refresh_note_list(); _ls_settle()
_ls_rows = [r[1]['id'] for r in app._list_rows() if r[0] == 'note']
_ls_last = [k for k in app._list_drawn_keys if k[0] == 'note'][-1][1]
# None when everything is drawn already -- the check below then fails on
# its own line instead of the script dying here without a verdict.
_ls_at = _ls_rows.index(_ls_last)
_ls_want = _ls_rows[_ls_at + 1] if _ls_at + 1 < len(_ls_rows) else None
# Which card the walk puts the ring on, recorded where the decision is
# made: focus_get() cannot be trusted while the test process does not own
# the desktop's foreground (qa/README).
_ls_asked = []
app._put_keyboard_on_card = lambda nid: _ls_asked.append(nid)
try:
    app._focus_card_by_offset(_ls_last, 1)
finally:
    app.__dict__.pop('_put_keyboard_on_card', None)
check(f'Down on the last drawn card draws on and moves to the next '
      f'(asked for {_ls_asked}, the next is {_ls_want})',
      _ls_want is not None and _ls_asked == [_ls_want])

# A note deleted before its card was ever drawn must never get one.
check(f'fixture: the list holds exactly the 300 notes it was given '
      f'({len(app.notes)})', len(app.notes) == 300)
_ls_victim = _ls_rows[200]
_ls_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
try:
    app._delete_note(app.find_note(_ls_victim), None); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
_ls_scroll_to_end()
_ls_ids = _ls_card_ids()
check(f'a note deleted before its card was drawn never gets one '
      f'({len(_ls_ids)} cards, victim drawn: {_ls_victim in _ls_ids})',
      _ls_victim not in _ls_ids and len(_ls_ids) == 299)

# A rebuild while scrolled keeps the depth, so the place restored in
# pixels has content to land on.
app.canvas.yview_moveto(0); _ls_settle()
app.refresh_note_list(); _ls_settle()
for _ in range(4):
    app.canvas.yview_moveto(1.0); app.update()
app.canvas.yview_moveto(0.6); _ls_settle()
_ls_depth = len(app._list_drawn_keys)
_ls_px = app.canvas.canvasy(0)
app.refresh_note_list()
# Read once the restore has run its course: straight after the call the
# view has not been clamped yet, so the place would match for nothing.
_ls_let_restores_finish()
check(f'a rebuild while scrolled keeps the drawn depth '
      f'({len(app._list_drawn_keys)} of {_ls_depth}) and the place '
      f'({app.canvas.canvasy(0):.0f} of {_ls_px:.0f})',
      _ls_px > 0 and len(app._list_drawn_keys) >= _ls_depth
      and abs(app.canvas.canvasy(0) - _ls_px) < 30)

# A first draw shorter than the window draws on by itself. From the top,
# once the rebuild above's restore has run out -- still in force, it
# carried the old depth into this rebuild and drew deep for a different
# reason (a mutant said so). And the fixture asserts its own start: one
# row, shorter in PIXELS than the view, which is what the promise is
# about. The list shows about 140px in this window, so three cards already
# overfilled it and a first version of this check, drawing three, asked
# nothing at all.
app.LIST_FIRST_DRAW = 1
try:
    _ls_let_restores_finish()
    app.canvas.yview_moveto(0)
    app._list_restore_px = None
    _ls_settle()
    app.refresh_note_list()
    _ls_first = len(app._list_drawn_keys)
    _ls_first_key = app._list_drawn_keys[0] if app._list_drawn_keys else None
    _ls_end = time.time() + 5
    _ls_seen = -1
    while time.time() < _ls_end and len(app._list_drawn_keys) != _ls_seen:
        _ls_seen = len(app._list_drawn_keys)
        _ls_settle()
        time.sleep(0.05)
    _ls_view = app.canvas.winfo_height()
    _ls_left = app._list_extent()[3] - app.canvas.canvasy(_ls_view)
    # The first card is the same drawing however many were drawn after it.
    _ls_first_card = (app._card_view(_ls_first_key[1])
                      if _ls_first_key and _ls_first_key[0] == 'note' else None)
    _ls_first_h = (_ls_first_card['y1'] - _ls_first_card['y0'] + 10
                   if _ls_first_card is not None else None)
    check(f'fixture: the first draw really is shorter than the view '
          f'({_ls_first} row, {_ls_first_h}px in a {_ls_view}px view)',
          _ls_first == 1 and _ls_first_h is not None and _ls_first_h < _ls_view)
    check(f'a list drawn shorter than its window draws on until a screen '
          f'is left below the view ({len(app._list_drawn_keys)} rows, '
          f'{_ls_left:.0f}px below a {_ls_view}px view)',
          len(app._list_drawn_keys) > 1 and _ls_left >= _ls_view > 1)
finally:
    del app.LIST_FIRST_DRAW

# The scroll region is the drawing as the app knows it, from 0 to below
# its last row -- not whatever Tk's bbox makes of it. How Tk pads a
# rectangle's bbox changed between 8.6.15 and 8.6.16, and a list that took
# its top from there read as scrolled on the Linux image while Windows was
# green. Asked of the canvas's own scrollregion, which is what the
# scrollbar and every yview use, against what Tk says the rows measure
# (a pixel either way for that same padding).
app.canvas.yview_moveto(0); _ls_settle()
_ls_region = [int(float(v)) for v in str(app.canvas.cget('scrollregion')).split()]
_ls_rows_box = app.canvas.bbox('row')
check(f'the scroll region is the drawing, from 0 to below its last row '
      f'({_ls_region} for rows measuring {_ls_rows_box})',
      len(_ls_region) == 4 and _ls_region[:2] == [0, 0]
      and _ls_rows_box is not None
      and _ls_rows_box[3] - 1 <= _ls_region[3]
      <= _ls_rows_box[3] + app.CARD_MARGIN[1] + 1)
check('...and at the top of the list, the top of the view is 0',
      app.canvas.canvasy(0) == 0)

# Select all covers the notes not drawn yet, and their cards arrive ticked.
app.canvas.yview_moveto(0); _ls_settle()
app.refresh_note_list(); _ls_settle()
app._toggle_selection_mode(); _ls_settle()
app._bulk_select_all(); _ls_settle()
_ls_scroll_to_end()
_ls_boxes = [app._card_view(n)['checked'] for n in app._card_order()]
_ls_ticked = sum(1 for b in _ls_boxes if b)
check(f'cards drawn after Select all arrive ticked ({_ls_ticked} of '
      f'{len(app._visible_note_ids())})',
      _ls_ticked == len(_ls_boxes) == len(app._visible_note_ids()))
app._toggle_selection_mode(); _ls_settle()

# Grouped: a header not drawn yet still counts only what is left. Work is
# a default category; made certain BEFORE normalize_note, which files a
# note under an unknown category as General.
_ls_added_work = 'Work' not in NO.CATEGORY_COLORS
NO.CATEGORY_COLORS.setdefault('Work', '#4cc9f0')
app.notes = ([NO.normalize_note({'id': 1000 + i, 'title': 'Gen %03d' % i,
                                 'body': 'b', 'category': 'General',
                                 'updated': '2026-01-01 00:00'})
              for i in range(60)]
             + [NO.normalize_note({'id': 2000 + i, 'title': 'Wk %03d' % i,
                                   'body': 'b', 'category': 'Work',
                                   'updated': '2026-01-01 00:00'})
                for i in range(60)])
app.group_by_category.set(True)
# From the top, once the scroll restores of the Select all block above have
# run out -- still in force, the rebuild below would keep their depth and
# draw the Work header straight away, and the check would ask nothing.
_ls_let_restores_finish()
app.canvas.yview_moveto(0)
app._list_restore_px = None
_ls_settle()
app.refresh_note_list(); _ls_settle()
_ls_work_waiting = ('header', 'Work') not in app._list_drawn_keys
app.ask_yes_no = lambda *a, **k: True
try:
    app._delete_note(app.find_note(2030), None); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
_ls_scroll_to_end()
_ls_work_txt = (app._header_view('Work') or {}).get('label')
check(f'a group\'s header drawn after a deletion counts what is left '
      f'({_ls_work_txt!r}; it was waiting: {_ls_work_waiting})',
      _ls_work_waiting and _ls_work_txt == 'Work (59)')

# The drawing answers the mouse the way the widgets did -- found by where
# the pointer is, since a drawn card has no bindings of its own. Every
# event below is a real one, generated on the list's canvas.
_ls_let_restores_finish()
app.canvas.yview_moveto(0)
app._list_restore_px = None
_ls_settle()
app.refresh_note_list(); _ls_settle()


def _ls_at(y0, y1):
    """The canvas widget's own y for the middle of a drawn span."""
    return int((y0 + y1) / 2 - app.canvas.canvasy(0))


# A header folds its group when clicked anywhere on its line -- at x=200,
# well clear of its words, as the header frame used to take such a click.
_ls_hd = app._header_view('General')
_qa_click(app.canvas, x=200, y=_ls_at(_ls_hd['y0'], _ls_hd['y1']))
_ls_settle()
check("a click anywhere on a header's line folds its group "
      "(caret %r)" % (app._header_view('General') or {}).get('caret'),
      'General' in app.collapsed_groups
      and (app._header_view('General') or {}).get('caret') == '▶')
_ls_hd = app._header_view('General')
_qa_click(app.canvas, x=200, y=_ls_at(_ls_hd['y0'], _ls_hd['y1']))
_ls_settle()
check('...and a second click unfolds it',
      'General' not in app.collapsed_groups)

# The hand over a card, the plain pointer over the gap between two.
_ls_o = app._card_order()
_ls_v0 = app._card_view(_ls_o[0])
_qa_fire(app.canvas, '<Motion>', x=120, y=_ls_at(_ls_v0['y0'], _ls_v0['y1']))
_ls_settle()
_ls_hand = str(app.canvas.cget('cursor'))
_qa_fire(app.canvas, '<Motion>', x=120,
         y=int(_ls_v0['y1'] + app.CARD_MARGIN[1] - app.canvas.canvasy(0)))
_ls_settle()
_ls_gap = str(app.canvas.cget('cursor'))
check(f'the pointer is a hand over a card and plain over the gap '
      f'({_ls_hand!r}, {_ls_gap!r})', _ls_hand == 'hand2' and _ls_gap == '')

# In selection mode a click ticks the card -- drawn AND recorded -- rather
# than opening the note.
app._toggle_selection_mode(); _ls_settle()
_ls_pick = app._card_order()[1]
_ls_was = app._card_view(_ls_pick)['checked']
_ls_open_before = app.selected_note_id
_ls_pt = app._card_point(_ls_pick)
_qa_click(app.canvas, x=_ls_pt[0], y=_ls_pt[1])
_ls_settle()
check(f'in selection mode a click ticks the card, on screen and in the '
      f'selection (was {_ls_was}, now {app._card_view(_ls_pick)["checked"]})',
      _ls_was is False and app._card_view(_ls_pick)['checked'] is True
      and _ls_pick in app.selected_note_ids
      and app.selected_note_id == _ls_open_before)
app._toggle_selection_mode(); _ls_settle()

# 3. A save redraws one card. Grouped first: an edit that stays in its
# group, then one that changes group -- which must rebuild, because two
# headers' counts change.
app.canvas.yview_moveto(0); _ls_settle()
app.refresh_note_list(); _ls_settle()
app.open_note_in_tab(app.find_note(1005)); _ls_settle()
_ls_others = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()
              if nid != 1005}
app.body_text.insert('end', ' grouped edit')
app.save_current_note(auto=True); _ls_settle()
_ls_after = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()
             if nid != 1005}
check('a grouped save that stays in its group leaves every other card alone',
      _ls_others == _ls_after)
check('...and the list it leaves is the one a full rebuild draws',
      _ls_same_as_rebuild())
app.category_var.set('Work')
app.save_current_note(auto=True); _ls_settle()
check('a grouped save that changes group leaves the list a full rebuild '
      'draws (both counts moved)', _ls_same_as_rebuild())
app.group_by_category.set(False)
if _ls_added_work:
    NO.CATEGORY_COLORS.pop('Work', None)

# Ungrouped, sorted by Recently updated: the saved card goes to the top.
app.notes = [{'id': i, 'title': f'Save{i}', 'body': 'x' * 30,
              'category': 'General', 'updated': '2026-01-01 00:%02d' % (i % 60),
              'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}
             for i in range(120)]
app.canvas.yview_moveto(0); _ls_settle()
app.refresh_note_list(); _ls_settle()
_ls_target = _ls_card_ids()[12]
app.open_note_in_tab(app.find_note(_ls_target)); _ls_settle()
_ls_others = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()
              if nid != _ls_target}
_ls_stats = {'n': 0}
_ls_real_stats = app._render_statistics


def _ls_count_stats():
    _ls_stats['n'] += 1
    return _ls_real_stats()


app._render_statistics = _ls_count_stats
try:
    app.body_text.insert('end', ' and one more line')
    app.save_current_note(auto=True); _ls_settle()
finally:
    app.__dict__.pop('_render_statistics', None)
_ls_after = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()
             if nid != _ls_target}
check('an autosave redraws the saved card and leaves every other card alone',
      _ls_others == _ls_after)
check(f'...puts it where the sort does -- the top '
      f'({_ls_card_ids()[:1]}, saved {_ls_target})',
      _ls_card_ids()[:1] == [_ls_target])
check(f'...keeps Settings\' statistics live, as the rebuild did '
      f'({_ls_stats["n"]})', _ls_stats['n'] >= 1)
# The moved card was drawn last and put first. The keyboard walks the
# order on screen, so Down from it goes to the card under it -- not off
# the end of the order the cards were drawn in.
_ls_screen = _ls_card_ids()
_ls_asked = []
app._put_keyboard_on_card = lambda nid: _ls_asked.append(nid)
try:
    app._focus_card_by_offset(_ls_target, 1)
finally:
    app.__dict__.pop('_put_keyboard_on_card', None)
check(f'Down from a card a save moved walks the order on screen '
      f'(asked for {_ls_asked}, under it is {_ls_screen[1:2]})',
      _ls_asked == _ls_screen[1:2])
check('...and leaves the list a full rebuild would draw',
      _ls_same_as_rebuild())

# A save that takes the note out of the search takes its card with it.
_ls_search('Save7')
_ls_leaving = 7 if 7 in app._note_cards else None
if _ls_leaving is not None:
    app.open_note_in_tab(app.find_note(_ls_leaving)); _ls_settle()
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'Renamed away')
    app.save_current_note(auto=True); _ls_settle()
check(f'a save that takes a note out of the search takes its card off '
      f'(was on the list: {_ls_leaving is not None})',
      _ls_leaving is not None and _ls_leaving not in app._note_cards
      and _ls_same_as_rebuild())
_ls_search('')

# A brand-new note joins the list without the rest being rebuilt.
app.canvas.yview_moveto(0); _ls_settle()
app.refresh_note_list(); _ls_settle()
app.open_blank_tab(); _ls_settle()
_ls_others = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()}
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'Freshly made')
app.save_current_note(auto=True); _ls_settle()
_ls_new_id = app.selected_note_id
_ls_after = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()
             if nid != _ls_new_id}
# Where the list's own rows put it, not "the top": two saves in the same
# second tie on their timestamp, and a tie keeps the notebook's order.
_ls_new_rows = [r[1]['id'] for r in app._list_rows() if r[0] == 'note']
check('a new note\'s first save adds its card and leaves the others alone',
      _ls_new_id in app._note_cards and _ls_others == _ls_after
      and _ls_new_id in _ls_card_ids()
      and _ls_card_ids().index(_ls_new_id) == _ls_new_rows.index(_ls_new_id))
check('...and leaves the list a full rebuild would draw',
      _ls_same_as_rebuild())

# A drawn card deleted: the rows below close up over its place -- the list
# a full rebuild draws, compared place for place, so a gap left behind
# shows as a difference.
_ls_gone = _ls_card_ids()[3]
app.ask_yes_no = lambda *a, **k: True
try:
    app._delete_note(app.find_note(_ls_gone), None); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
check('deleting a drawn card closes the gap -- the list a full rebuild draws',
      _ls_gone not in app._note_cards and _ls_same_as_rebuild())

# ---------------------------------------------------------------------
# 4. Custom order: the list arranged by hand.
#
# A card dragged to another place stays there -- in the notebook file,
# not only on screen -- and so does one moved with Alt+Up or Alt+Down.
# Every drag below is real events on the list's canvas: a press on the
# card, the pointer moving with the button down, the release. Alt+arrows
# and Escape are keys, which Tk delivers to whichever window has the
# focus, and a test process does not own the desktop's focus (qa/README):
# their handlers are called as the bindings call them, and qa6 checks
# the bindings themselves exist.
# ---------------------------------------------------------------------
import json as _co_json
import io as _co_io


def _co_file_order():
    """The notes' ids in the order their stored places put them."""
    with _co_io.open(NO.DATA_FILE, encoding='utf-8') as fh:
        stored = _co_json.load(fh)
    placed = [n for n in stored if 'order' in n]
    return [n['id'] for n in sorted(placed, key=lambda n: n['order'])]


def _co_press(nid):
    """A press on a card's middle, where a hand would take it -- once the
    card is on screen, as a hand would need it to be (and so the press's
    own scroll-into-view moves nothing under the pointer)."""
    app._scroll_row_into_view(app._note_cards[nid])
    _ls_settle()
    v = app._card_view(nid)
    y = int((v['y0'] + v['y1']) / 2 - app.canvas.canvasy(0))
    _qa_click(app.canvas, x=120, y=y)
    _ls_settle()
    return y


def _co_move_to(from_y, canvas_y):
    """The pointer carried, button down, from `from_y` to canvas y
    `canvas_y`, in steps as a hand moves."""
    to = int(canvas_y - app.canvas.canvasy(0))
    step = 6 if to > from_y else -6
    for y in range(from_y, to, step):
        _qa_fire(app.canvas, '<B1-Motion>', x=120, y=y)
        app.update()
    _qa_fire(app.canvas, '<B1-Motion>', x=120, y=to)
    app.update()
    return to


def _co_drag(nid, canvas_y):
    y = _co_move_to(_co_press(nid), canvas_y)
    _qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=y)
    _ls_settle()


def _co_fresh(notes, sort='Recently updated'):
    app.group_by_category.set(False)
    if app.selection_mode:
        app._toggle_selection_mode()
    app.sort_var.set(sort)
    app.notes = [NO.normalize_note(n) for n in notes]
    app.save_notes()
    app.new_note()
    _ls_let_restores_finish()
    app.canvas.yview_moveto(0)
    app._list_restore_px = None
    app.refresh_note_list(); _ls_settle()


_ls_search('')
# The list shows about 140px in this window, so a pointer carried to a card
# a few places away passes the list's edge, where a drag scrolls the list
# under it. That has its own checks at the end of this block; here it would
# move the target while the pointer travels.
app.DRAG_EDGE = -10000
_co_notes = [{'id': 1500 + i, 'title': 'Arrange %02d' % i, 'body': 'b',
              'category': 'General', 'created': '2026-01-01 00:%02d' % i,
              'updated': '2026-02-01 00:%02d' % (59 - i)} for i in range(8)]
_co_fresh(_co_notes)
_co_ids = [1500 + i for i in range(8)]
check(f'fixture: eight cards, in the order Recently updated puts them '
      f'({app._card_order()})', app._card_order() == _co_ids
      and not any('order' in n for n in app.notes))

# Dragged up: the card lands before the one the line was above.
_co_updated = {n['id']: n['updated'] for n in app.notes}
_co_drag(1505, app._card_view(1501)['y0'] + 2)
_co_want = [1500, 1505, 1501, 1502, 1503, 1504, 1506, 1507]
check(f'a card dragged up lands where the line was ({app._card_order()})',
      app._card_order() == _co_want)
check('...and the list is in Custom order now, started from the order it '
      'showed', app.sort_var.get() == 'Custom order')
check(f'...and the notebook file holds that order ({_co_file_order()})',
      _co_file_order() == _co_want)
check('...and a move is not an edit: no note\'s "updated" changed',
      all(n['updated'] == _co_updated[n['id']] for n in app.notes))
check('...and nothing of the drag is left on the drawing',
      not app.canvas.find_withtag('drag_line') and _ls_same_as_rebuild())

# Dragged down, to just below a card: after it.
_co_drag(1500, app._card_view(1503)['y1'] + 2)
_co_want = [1505, 1501, 1502, 1503, 1500, 1504, 1506, 1507]
check(f'a card dragged down lands after the card it was let go under '
      f'({app._card_order()})', app._card_order() == _co_want)

# A hand that shakes a little while clicking has not started a drag.
_co_y = _co_press(1502)
_qa_fire(app.canvas, '<B1-Motion>', x=120, y=_co_y + 2); app.update()
_co_shaky = getattr(app, '_drag', None)
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_y + 2); _ls_settle()
check('a press that moves a pixel or two is a click, not a drag',
      _co_shaky is not None and not _co_shaky['started']
      and app._card_order() == _co_want)

# Escape puts the card back and moves nothing. The pointer is carried far
# above the list's top on the way (the list shows a card and a half), and
# the card it carries must still be in sight -- first photographed with the
# line at the top of the list and its card nowhere.
_co_y = _co_move_to(_co_press(1507), app._card_view(1505)['y0'] + 2)
_co_lifted = bool(getattr(app, '_drag', None) and app._drag['started']
                  and app.canvas.find_withtag('drag_line'))
_co_box = app.canvas.coords(app._note_cards[1507]['items']['bg'])
_co_view = (app.canvas.canvasy(0), app.canvas.canvasy(app.canvas.winfo_height()))
check(f'a card carried past the list\'s edge stays in sight (card '
      f'{_co_box[1]:.0f}-{_co_box[3]:.0f}, view {_co_view[0]:.0f}-{_co_view[1]:.0f})',
      _co_lifted and _co_box[1] >= _co_view[0] - 1 and _co_box[3] <= _co_view[1] + 1)
app._list_drag_escape(); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_y); _ls_settle()
check(f'Escape during a drag puts the card back and moves nothing '
      f'(lifted first: {_co_lifted})',
      _co_lifted and app._card_order() == _co_want
      and not app.canvas.find_withtag('drag_line') and _ls_same_as_rebuild())

# The list changing under a drag -- a rebuild -- ends it cleanly.
_co_y = _co_move_to(_co_press(1504), app._card_view(1501)['y0'] + 2)
_co_lifted = bool(getattr(app, '_drag', None) and app._drag['started'])
app.refresh_note_list(); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_y); _ls_settle()
check(f'a rebuild under a drag ends it, with the card back in its place '
      f'(lifted first: {_co_lifted})',
      _co_lifted and getattr(app, '_drag', None) is None
      and app._card_order() == _co_want
      and not app.canvas.find_withtag('drag_line') and _ls_same_as_rebuild())

# Alt+Up and Alt+Down: the card with the ring moves, the ring with it.
app._put_keyboard_on_card(1503); _ls_settle()
app._list_move_by_keyboard(-1); _ls_settle()
_co_want = [1505, 1501, 1503, 1502, 1500, 1504, 1506, 1507]
check(f'Alt+Up moves the card with the ring one place up ({app._card_order()})',
      app._card_order() == _co_want)
check('...and the ring stays on it', app._focused_note_id == 1503)
app._list_move_by_keyboard(1); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
_co_want = [1505, 1501, 1502, 1500, 1503, 1504, 1506, 1507]
check(f'...and Alt+Down twice takes it two places down ({app._card_order()})',
      app._card_order() == _co_want and app._focused_note_id == 1503)

# A save does not move a card in Custom order; a new note starts at the top.
app.open_note_in_tab(app.find_note(1502)); _ls_settle()
app.body_text.insert('end', ' edited'); app.save_current_note(auto=True); _ls_settle()
check(f'saving a note leaves its card where it was put ({app._card_order()})',
      app._card_order() == _co_want)
app.new_note(); _ls_settle()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Brand new')
app.save_current_note(auto=True); _ls_settle()
_co_new = app.selected_note_id
check(f'a new note starts at the top of a Custom order ({app._card_order()[:2]})',
      app._card_order()[0] == _co_new and app._card_order()[1:] == _co_want)
app.notes = [n for n in app.notes if n['id'] != _co_new]
app.save_notes(); app.new_note(); app.refresh_note_list(); _ls_settle()

# Pinned notes stand above the rest, and a drag cannot cross that line --
# the next rebuild would only undo it.
app.find_note(1507)['pinned'] = True
app.save_notes(); app.refresh_note_list(); _ls_settle()
_co_order = app._card_order()
# Where the LINE says the card will land, not only where it lands: the
# pinned card floats above whatever the numbers say, so a drop that
# crossed it would look right afterwards -- while the line had promised a
# place above the pinned card that the card could never take (a mutant
# that let it cross passed on the landing alone).
_co_y = _co_move_to(_co_press(1506), app._card_view(1507)['y0'] + 2)
_co_slot = app._drag['slot'] if getattr(app, '_drag', None) else 'none'
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_y); _ls_settle()
check(f'a card dragged above the pinned ones is shown, and lands, first '
      f'below them (line {_co_slot}; {app._card_order()[:3]})',
      _co_slot == ('before', _co_order[1])
      and app._card_order()[:2] == [1507, 1506]
      and app._card_order()[2:] == [i for i in _co_order[1:] if i != 1506])
_co_order = app._card_order()
_co_y = _co_move_to(_co_press(1507), app._card_view(_co_order[-1])['y1'] - 2)
_co_slot = app._drag['slot'] if getattr(app, '_drag', None) else 'none'
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_y); _ls_settle()
check(f'a pinned card cannot be dragged down among the rest (slot {_co_slot})',
      _co_slot is None and app._card_order() == _co_order)
app.find_note(1507)['pinned'] = False
app.save_notes()

# Grouped: a card stays in its category's group.
_co_fresh([{'id': 1600 + i, 'title': 'Grp %d' % i, 'body': 'b',
            'category': 'General' if i < 3 else 'Work',
            'created': '2026-01-01 00:%02d' % i,
            'updated': '2026-02-01 00:%02d' % (59 - i)} for i in range(6)])
app.group_by_category.set(True)
app.refresh_note_list(); _ls_settle()
_co_general = [r[1]['id'] for r in app._list_rows()
               if r[0] == 'note' and r[1]['category'] == 'General']
_co_work = [r[1]['id'] for r in app._list_rows()
            if r[0] == 'note' and r[1]['category'] == 'Work']
# The line again, for the same reason as the pinned card's: grouping
# sorts a card back into its category whatever the numbers say.
_co_y = _co_move_to(_co_press(1605), app._card_view(1600)['y0'] + 2)
_co_slot = app._drag['slot'] if getattr(app, '_drag', None) else 'none'
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_y); _ls_settle()
_co_rows = [(r[1]['category'], r[1]['id']) for r in app._list_rows() if r[0] == 'note']
check(f'in a grouped list a card dragged into another group is shown, and '
      f'lands, at its own group\'s edge (line {_co_slot}; {_co_rows})',
      _co_slot == ('before', _co_work[0])
      and [i for c, i in _co_rows if c == 'General'] == _co_general
      and [i for c, i in _co_rows if c == 'Work'][0] == 1605
      and app.find_note(1605)['category'] == 'Work')
app.group_by_category.set(False)

# Choosing Custom order for the first time starts from the order shown.
_co_fresh(_co_notes, sort='Title Z–A')
_co_order = app._card_order()
app.sort_var.set('Custom order')
app._on_sort_chosen('Custom order'); _ls_settle()
check(f'Custom order chosen for the first time keeps the order that was '
      f'showing ({app._card_order()})',
      app._card_order() == _co_order and _co_file_order() == _co_order)

# In selection mode a press ticks the card; the pointer moving after it
# carries nothing.
app._toggle_selection_mode(); _ls_settle()
_co_order = app._card_order()
_co_move_to(_co_press(_co_order[4]), app._card_view(_co_order[0])['y0'] + 2)
check('in selection mode a card cannot be dragged',
      getattr(app, '_drag', None) is None
      and not app.canvas.find_withtag('drag_line'))
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=10); _ls_settle()
app._toggle_selection_mode(); _ls_settle()
check('...and nothing moved', app._card_order() == _co_order)

# A place is this notebook's own: a share code does not carry it, and a
# number that is not a number never reaches the sort.
_co_decoded = NO.decode_share_code(NO.encode_share_code(app.notes[0]))
check('a share code does not carry a note\'s place in Custom order',
      'order' in app.notes[0] and all('order' not in n for n in _co_decoded))
_co_norm = [NO.normalize_note({'id': 1, 'order': v}).get('order', 'absent')
            for v in (3, 2.5, True, '4', float('nan'), None)]
check(f'only a real number is kept as a place ({_co_norm})',
      _co_norm == [3, 2.5, 'absent', 'absent', 'absent', 'absent'])

# The list's edge: a drag held there scrolls the list, a step at a time,
# so a card can be taken further than the list shows -- and going down,
# the rows drawn on demand arrive under the drag (the drawing and the drag
# meeting, which neither knew about when it was written).
app.__dict__.pop('DRAG_EDGE', None)
_co_fresh([{'id': 1700 + i, 'title': 'Long %02d' % i, 'body': 'b',
            'category': 'General', 'created': '2026-01-01 00:%02d' % i,
            'updated': '2026-02-01 00:%02d' % (59 - i)} for i in range(45)])
check(f'fixture: a list longer than its first drawing ({len(app._list_drawn)} '
      f'of 45 drawn)', len(app._list_drawn) < 45)
# Taken from well down the drawn part, so the drawn rows run out soon.
_co_y = _co_press(1725)
_co_top = app.canvas.canvasy(0)
_co_drawn = len(app._list_drawn)
_co_h = app.canvas.winfo_height()
_co_move_to(_co_y, app.canvas.canvasy(_co_h - 3))
_co_end = time.time() + 6
while time.time() < _co_end and len(app._list_drawn) <= _co_drawn:
    app.update(); time.sleep(0.02)
_co_scrolled = app.canvas.canvasy(0) - _co_top
_co_slot = app._drag['slot'] if getattr(app, '_drag', None) else None
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_h - 3); _ls_settle()
_co_rows = [r[1]['id'] for r in app._list_rows() if r[0] == 'note']
check(f'a drag held at the list\'s bottom edge scrolls it and the rows '
      f'waiting are drawn under it ({_co_drawn} -> {len(app._list_drawn)} '
      f'drawn, {_co_scrolled:.0f}px scrolled)',
      len(app._list_drawn) > _co_drawn and _co_scrolled > 100)
check(f'...and the card lands where the line was when it was let go '
      f'({_co_slot})',
      _co_slot is not None and _co_slot[0] in ('before', 'after')
      and _co_rows.index(1725) == _co_rows.index(_co_slot[1])
      + (-1 if _co_slot[0] == 'before' else 1)
      and _ls_same_as_rebuild())
app.canvas.yview_moveto(1.0); _ls_settle()
_co_y = _co_press(_co_rows[-1])
_co_let = app.canvas.canvasy(0)
_co_move_to(_co_y, app.canvas.canvasy(3))
_co_end = time.time() + 6
while time.time() < _co_end and app.canvas.canvasy(0) > _co_let - 100:
    app.update(); time.sleep(0.02)
_co_up = _co_let - app.canvas.canvasy(0)
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=3); _ls_settle()
check(f'...and one held at the top edge scrolls it up ({_co_up:.0f}px)',
      _co_up >= 100 and _ls_same_as_rebuild())
app.sort_var.set('Recently updated')

# ---------------------------------------------------------------------
# 5. The list under a hurried hand (the break-it audit, 2026-09-30).
#
# Each part below is a way a person's ordinary handling of the list went
# wrong while every single gesture, taken slowly and alone, worked: a
# release lost to another window, a click that saved the note left behind
# and so moved the rows under the pointer, a Select all over folded
# groups, a tick left on a note that was deleted, an arrangement replaced
# without a word, two cards both claiming to be open, a header too long
# for its line, the ring out of sight, groups the keyboard could not
# fold, and a list that stayed drawn to its end once it had been.
# ---------------------------------------------------------------------


def _bl_drawing_ok():
    """Every drawn card is drawn where its record says: a card left
    lifted, or moved without its record, shows here."""
    bad = []
    for rec in app._list_drawn:
        if rec['kind'] != 'note':
            continue
        box = app.canvas.coords(rec['items']['bg'])
        if not box or abs(box[1] - rec['y0']) > 0.5 or abs(box[3] - rec['y1']) > 0.5:
            bad.append(rec['note']['id'])
    return not bad


def _bl_lift(nid, by=54):
    """Press a card and carry it `by` pixels down with the button held --
    far enough to lift it -- and return where the pointer is."""
    y = _co_press(nid)
    for dy in range(6, by + 1, 6):
        _qa_fire(app.canvas, '<B1-Motion>', x=120, y=y + dy)
        app.update()
    return y + by


def _bl_lifted():
    drag = getattr(app, '_drag', None)
    return bool(drag and drag['started'] and drag['offset']
                and app.canvas.find_withtag('drag_line'))


# 5a. A drag whose release never reaches the list. The release is lost
# (another window took the pointer, say); whatever the list hears next
# must put the lifted card back before it does anything else.
app.DRAG_EDGE = -10000
_co_fresh(_co_notes)
_bl_o = app._card_order()
_bl_lift(_bl_o[1])
_bl_was = _bl_lifted()
_bl_pt = app._card_point(_bl_o[0])
_qa_click(app.canvas, x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
check(f'a press while a card is still lifted puts it back first: no line, '
      f'every card where its record is, no four-way pointer (lifted first: '
      f'{_bl_was}, pointer {str(app.canvas.cget("cursor"))!r})',
      _bl_was and not app.canvas.find_withtag('drag_line') and _bl_drawing_ok()
      and str(app.canvas.cget('cursor')) != 'fleur')
_qa_fire(app.canvas, '<ButtonRelease-1>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()

_bl_lift(_bl_o[2])
check(f'...while a card is lifted, the pointer shape the list remembers is '
      f'the one it shows ({app._list_cursor!r}, '
      f'{str(app.canvas.cget("cursor"))!r})',
      app._list_cursor == str(app.canvas.cget('cursor')) == 'fleur')
# Motion with the button UP: <B1-Motion> takes every move while it is down,
# so this one says the release went missing.
_bl_pt = app._card_point(_bl_o[0])
_qa_fire(app.canvas, '<Motion>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
check(f'...and the pointer moving with the button up puts it back too, '
      f'with the hand over a card again ({str(app.canvas.cget("cursor"))!r})',
      not _bl_lifted() and not app.canvas.find_withtag('drag_line')
      and _bl_drawing_ok() and str(app.canvas.cget('cursor')) == 'hand2')

# A right-click during a drag: the drawing under the pointer is the lifted
# card, the record there its neighbour's, so a menu would be for a note
# nobody pointed at. First the control -- with no drag, a right-click does
# open the menu of the card under it -- so the silence below is a decision.
_bl_menus = []
app.show_note_context_menu = lambda ev, note, **k: _bl_menus.append(note['id'])
try:
    _bl_pt = app._card_point(_bl_o[3])
    _qa_fire(app.canvas, '<Button-3>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
    _bl_control = list(_bl_menus)
    del _bl_menus[:]
    _bl_y = _bl_lift(_bl_o[1])
    _bl_was = _bl_lifted()
    # On the neighbour's record, where the lifted card is drawn: without
    # the cancel this is the menu that opened -- for the neighbour.
    _bl_pt = app._card_point(_bl_o[2])
    _qa_fire(app.canvas, '<Button-3>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
finally:
    app.__dict__.pop('show_note_context_menu', None)
check(f'a right-click during a drag cancels it and opens no menu (menus '
      f'{_bl_menus}; with no drag it opened {_bl_control}, lifted first: '
      f'{_bl_was})',
      _bl_control == [_bl_o[3]] and _bl_was and _bl_menus == []
      and not _bl_lifted() and _bl_drawing_ok())
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y); _ls_settle()

# The window losing the keyboard mid-drag is how a release goes missing.
_bl_lift(_bl_o[1])
_bl_was = _bl_lifted()
app.canvas.winfo_id()
app.canvas.event_generate('<FocusOut>'); _ls_settle()
check(f'the list losing the keyboard mid-drag puts the lifted card back '
      f'(lifted first: {_bl_was})',
      _bl_was and not _bl_lifted() and not app.canvas.find_withtag('drag_line')
      and _bl_drawing_ok() and app._card_order() == _bl_o)
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=10); _ls_settle()
app.__dict__.pop('DRAG_EDGE', None)

# ---------------------------------------------------------------------
# A tick box's well must be light, because the mark in it is dark.
#
# Tk draws a Checkbutton's mark dark on Windows whatever the palette
# says. Every well in the app used to be set to `card` or `sidebar` --
# the very surface the box sits on -- so on a dark theme a ticked box
# and an empty one looked the same. Field-reported with a screenshot:
# "you can barely see that it is ticked".
#
# Light themes never showed it, because their card already is white.
# That is the trap: the well has to be light because the MARK is dark,
# not because the theme is one thing or the other. So the check is about
# luminance, not about which theme is loaded -- a future palette that
# picks a dark well fails here rather than in somebody's screenshot.
#
# A RADIO is the exception, and the same trap the other way round. Tk on
# Windows paints a selected radio's dot in the button's own foreground
# colour -- measured: a red foreground gave a red dot and nothing else
# did -- so on a dark theme the light text colour went onto the light
# well and the dot vanished. Field-reported: "the bullets stay white,
# the user cannot see which one is chosen". A radio's well has to stand
# apart from its OWN foreground, which card does on every theme.
# ---------------------------------------------------------------------


def _luminance(hex_colour):
    """0 (black) to 1 (white), weighted the way an eye weights it."""
    raw = str(hex_colour).lstrip('#')
    if len(raw) != 6:
        return None
    r, g, b = (int(raw[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


for _tname, _palette in NO.THEMES.items():
    _well = _palette.get('check_well')
    check('%s names a well for its tick boxes' % _tname, bool(_well))
    _lum = _luminance(_well) if _well else None
    check('...and it is light enough for a dark mark to read (%s)' % _well,
          _lum is not None and _lum > 0.75)


def _every_toggle(widget, out=None):
    out = [] if out is None else out
    for child in widget.winfo_children():
        if isinstance(child, (tk.Checkbutton, tk.Radiobutton)):
            out.append(child)
        _every_toggle(child, out)
    return out


# Built on screen, not just in the palette: selection mode puts a box on
# every card, and Settings carries several more.
app.notes = [NO.normalize_note({'id': 960 + i, 'title': 'Toggle%d' % i,
                                'body': 'b', 'category': 'General'})
             for i in range(3)]
app.save_notes()
app.new_note()
app.refresh_note_list()
app.update()
if not app.selection_mode:
    app._toggle_selection_mode()
app.update()
app.show_settings_page()
app.update()

def _inspect_wells(route):
    """Every tick box on screen, judged on the two things that matter."""
    toggles = _every_toggle(app)
    check('there are tick boxes on screen to inspect (%s)' % route,
          len(toggles) >= 3)
    borrowed, dark, dot_lost, radios = [], [], [], 0
    for widget in toggles:
        try:
            well = str(widget.cget('selectcolor')).lower()
            behind = str(widget.cget('bg')).lower()
            ink = str(widget.cget('fg')).lower()
        except tk.TclError:
            continue
        # The promise is not "it equals check_well" -- a literal written
        # somewhere else would pass that by luck. It is that the well is
        # not the surface it sits on, which is the mistake that was made
        # twelve times over.
        if well == behind:
            borrowed.append(str(widget))
        if isinstance(widget, tk.Radiobutton):
            # A radio is the other way round, measured on Windows: its dot
            # is painted in the button's OWN foreground colour, so what
            # matters is that the well stands apart from that. This check
            # used to hold radios to the light well too -- the rule that
            # made the dot vanish on every dark theme.
            radios += 1
            if abs((_luminance(well) or 0) - (_luminance(ink) or 0)) < 0.5:
                dot_lost.append(str(widget))
        elif (_luminance(well) or 1) <= 0.75:
            dark.append(str(widget))
    check('no tick box borrows the colour of the surface behind it (%s)'
          % route, not borrowed)
    check('every tick box on screen has a light well (%s)' % route, not dark)
    check('every radio\'s well stands apart from the colour its dot is '
          'painted in (%s; %d radios)' % (route, radios),
          radios >= 3 and not dot_lost)


# Both routes, because both build the boxes and the fix had to reach
# both: entering selection mode adds a box to each existing card in
# place, while a refresh builds every card from scratch with its box
# already on. A mutant put back in one of them survived a check that
# only ever saw the other.
_inspect_wells('added to the cards in place')
app.refresh_note_list()
app.update()
_inspect_wells('built with the cards')

# ...and a radio on EVERY theme: its dot vanished only where the text
# colour is light, which is every dark theme and none of the light ones,
# so a check run on whichever theme happened to be loaded could pass.
_rw_lost = []
_rw_before = app.theme_name
for _rw_theme in NO.THEMES:
    app.set_theme(_rw_theme)
    app.update()
    for _rw in _every_toggle(app):
        if not isinstance(_rw, tk.Radiobutton):
            continue
        _rw_well = str(_rw.cget('selectcolor'))
        _rw_ink = str(_rw.cget('fg'))
        if abs((_luminance(_rw_well) or 0) - (_luminance(_rw_ink) or 0)) < 0.5:
            _rw_lost.append('%s/%s' % (_rw_theme, _rw.cget('text')))
app.set_theme(_rw_before)
app.update()
check('on every theme, a chosen radio\'s dot stands out from its well '
      '(%s)' % (', '.join(_rw_lost) or 'every theme'), not _rw_lost)

app.hide_settings_page()
app.update()
if app.selection_mode:
    app._toggle_selection_mode()
app.notes = []
app.save_notes()
app.new_note()
app.update()


print()
print(f"=== QA4 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
