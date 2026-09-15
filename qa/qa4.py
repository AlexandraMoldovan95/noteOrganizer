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
def find_card_bg(w):
    for c in w.winfo_children():
        try:
            if c.cget('cursor')=='hand2' and isinstance(c, tk.Frame): return c.cget('bg')
        except: pass
        r=find_card_bg(c)
        if r: return r
before = find_card_bg(app.list_frame)
app.set_theme('light'); app.update()
after = find_card_bg(app.list_frame)
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
check('recurrence radios still have their well tracked, so it cannot go stale',
      any(isinstance(w, tk.Radiobutton) and m.get('selectcolor') == 'check_well'
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
NOTE_LIST_BUDGET_MS = 8000
app.notes = [{'id':i,'title':f'Perf{i}','body':'x'*30,'category':'General',
             'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
             'checklist':[],'attachments':[]} for i in range(300)]
t0=time.perf_counter()
app.refresh_note_list()
app.update()
elapsed=(time.perf_counter()-t0)*1000
_cards_built = len(getattr(app, '_note_card_widgets', {}))
check(f'refresh_note_list really builds every card ({_cards_built} of 300)',
      _cards_built == 300)
check(f'...and stays inside its budget ({elapsed:.0f}ms of '
      f'{NOTE_LIST_BUDGET_MS}ms; measured 1.2-1.6s on Windows, 0.5s on Linux)',
      elapsed < NOTE_LIST_BUDGET_MS)

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
    borrowed, dark = [], []
    for widget in toggles:
        try:
            well = str(widget.cget('selectcolor')).lower()
            behind = str(widget.cget('bg')).lower()
        except tk.TclError:
            continue
        # The promise is not "it equals check_well" -- a literal written
        # somewhere else would pass that by luck. It is that the well is
        # not the surface it sits on, which is the mistake that was made
        # twelve times over.
        if well == behind:
            borrowed.append(str(widget))
        if (_luminance(well) or 1) <= 0.75:
            dark.append(str(widget))
    check('no tick box borrows the colour of the surface behind it (%s)'
          % route, not borrowed)
    check('every tick box on screen has a light well (%s)' % route, not dark)


# Both routes, because both build the boxes and the fix had to reach
# both: entering selection mode adds a box to each existing card in
# place, while a refresh builds every card from scratch with its box
# already on. A mutant put back in one of them survived a check that
# only ever saw the other.
_inspect_wells('added to the cards in place')
app.refresh_note_list()
app.update()
_inspect_wells('built with the cards')

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
