# HERMETIC SEED -- BEFORE the note_organizer import below. Building the
# app calls initialise(), which resolves the data directory and runs the
# data MIGRATIONS, so this script's data directory must be its own by
# then; seeding it before the import leaves no step in between.
# hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to run at all
# outside a scratch run, or beside a notebook it cannot prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import types
import note_organizer as NO, tkinter as tk, time
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         pin_popup_visibility as _qa_pin,
                         waiting_timers as _qa_waiting)
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
    {'id': 1, 'title': 'Has identity', 'body': 'x'})
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

# The same seam once more: the rescue copy of a big deletion ("↩ Restore
# previous") was copied too, so the duplicate offered to put the
# original's older words over a note made now. It stays with the original.
_prev_src = _model4.normalize_note(
    {'id': 1, 'title': 'Cut down', 'body': 'short now',
     '_prev': {'title': 'Cut down', 'body': 'the long text it had before'}})
app.notes = [_prev_src]
app.save_notes()
_prev_clone = app.duplicate_note(app.notes[0])
app.update()
check(f'duplicate_note: the copy carries no rescue copy of the original '
      f'({sorted(_prev_clone)!r})', '_prev' not in _prev_clone)
check('duplicate_note: the original keeps its own',
      (app.find_note(1).get('_prev') or {}).get('body') == 'the long text it had before')
# ...and a backup's "Add a copy anyway" or "Add them as new notes", the
# other roads that copy a note here: the copies came with the original's
# rescue copy, the seam duplicate_note had.
_prev_copies = app._without_identity([(app.notes[0], dict(app.notes[0]))])
check(f'an import\'s copies carry no rescue copy, nor the uid '
      f'({[sorted(c) for c in _prev_copies]!r})',
      len(_prev_copies) == 1 and '_prev' not in _prev_copies[0] and 'uid' not in _prev_copies[0]
      and _prev_copies[0].get('body') == 'short now')

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
        refresh=lambda: None, announce=False)
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
# The merge stops where a note's files do, as the backup import's: past
# NO.MAX_ATTACHMENTS the next load cut the list, and the purge took the files
# no note named any more.
_cap_kept = dict(_kept4, id=12, attachments=[
    {'filename': f'k{i}.txt', 'stored_as': f'2026010100000000{i:04d}_k.txt'}
    for i in range(NO.MAX_ATTACHMENTS - 1)])
_cap_extra = [f"2026010100000001{i:04d}_x.txt" for i in range(3)]
for _name in _cap_extra:
    _mk_att4(_name)
_cap_removed = dict(_removed4, id=13, attachments=[
    {'filename': f'x{i}.txt', 'stored_as': n} for i, n in enumerate(_cap_extra)])
app.notes = [_cap_kept, _cap_removed]
app.trash = []
app.ask_yes_no = lambda *a, **k: True
try:
    app._cleanup_selected_duplicates(
        [(_V4(False), _cap_kept, [_cap_kept, _cap_removed]),
         (_V4(True), _cap_removed, [_cap_kept, _cap_removed])],
        refresh=lambda: None, announce=False)
finally:
    app.ask_yes_no = _orig_ask4
app.update()
check(f"cleanup-duplicates: the kept copy takes files up to the {NO.MAX_ATTACHMENTS} "
      f"a note holds, the rest left with the copy in the Trash "
      f"({len(_cap_kept['attachments'])}, {[len(e.get('attachments') or []) for e in app.trash]})",
      len(_cap_kept['attachments']) == NO.MAX_ATTACHMENTS
      and [len(e.get('attachments') or []) for e in app.trash] == [3])
# Duplicate gives the copy each file again under a new name: cleaning the
# copy up gave the kept note every file twice.
_mk_att4("2026010100000002_a_photo.jpg", "PHOTO")
_mk_att4("2026010100000002_b_photo.jpg", "PHOTO")
_mk_att4("2026010100000002_c_other.txt", "OTHER")
_mk_att4("2026010100000002_d_photo.jpg", "PHOTX")      # as long, other bytes
_tw_kept = dict(_kept4, id=14, attachments=[
    {'filename': 'photo.jpg', 'stored_as': '2026010100000002_a_photo.jpg'}])
_tw_copy = dict(_removed4, id=15, title='Dup (copy)', attachments=[
    {'filename': 'photo.jpg', 'stored_as': '2026010100000002_b_photo.jpg'},
    {'filename': 'photo.jpg', 'stored_as': '2026010100000002_d_photo.jpg'},
    {'filename': 'other.txt', 'stored_as': '2026010100000002_c_other.txt'}])
app.notes = [_tw_kept, _tw_copy]
app.trash = []
app.ask_yes_no = lambda *a, **k: True
try:
    app._cleanup_selected_duplicates(
        [(_V4(False), _tw_kept, [_tw_kept, _tw_copy]),
         (_V4(True), _tw_copy, [_tw_kept, _tw_copy])],
        refresh=lambda: None, announce=False)
finally:
    app.ask_yes_no = _orig_ask4
app.update()
check(f"cleanup-duplicates: a file the kept note already holds is not merged "
      f"again, a different one is "
      f"({[a.get('filename') for a in _tw_kept['attachments']]})",
      [a.get('filename') for a in _tw_kept['attachments']]
      == ['photo.jpg', 'photo.jpg', 'other.txt'])

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
    # The keyboard's ring too: it is the border's other colour (focus_ring).
    return (str(app.category_menu.cget('highlightbackground')) == app.colors['card']
            and str(app.category_menu.cget('highlightcolor')) == app._focus_ring(),
            str(_probe_dd.cget('highlightbackground')) == app.colors['card']
            and str(_probe_dd.cget('highlightcolor')) == app._focus_ring(),
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

# ---- THEME: the keyboard's ring keeps its colours across a switch ----
# The reminder bar's message and ✕ are Tab stops
# ringed in the bar's own words' colour, remembered when the bar is drawn. A
# switch kept the old accent round them, and dark_slate's near-black ring on
# light's violet read at 3:1 where light's own white reads at 5.7:1.
import datetime as _rb_dt
_rb_theme = app.theme_name
# The bar stands above the notebook, which Settings takes off the window.
_rb_settings = getattr(app, '_settings_open', False)
if _rb_settings:
    app.hide_settings_page()
app.set_theme('dark_slate'); app.update()
app._render_reminder_bar(2, _rb_dt.date.today().strftime('%Y-%m-%d'))
app.update()
_rb_stops = [w for w in app.reminder_bar.winfo_children()
             if getattr(w, '_key_press', None) is not None]
app.set_theme('light'); app.update()


def _rb_resting(w):
    return (str(w.cget('highlightbackground')).lower(), str(w._ring_on).lower())


check(f'after a switch the reminder bar\'s two Tab stops rest in the new accent '
      f'and are ringed in its words ({[_rb_resting(w) for w in _rb_stops]})',
      len(_rb_stops) == 2 and all(
          _rb_resting(w) == (app.colors['accent'].lower(),
                             app._on_fill('accent').lower()) for w in _rb_stops))
_rb_seen = None
if _rb_stops:
    _rb_stops[-1].focus_force()
    for _ in range(40):
        app.update()
        try:
            if app.focus_get() is _rb_stops[-1]:
                break
        except KeyError:
            pass
        time.sleep(0.02)
    app.update()
    _rb_seen = (str(_rb_stops[-1].cget('highlightbackground')).lower(),
                str(_rb_stops[-1].cget('highlightcolor')).lower())
check(f'...and with the keyboard on its ✕ the ring is the new theme\'s words '
      f'({_rb_seen})', _rb_seen == (app._on_fill('accent').lower(),) * 2)
app.dismiss_reminder()
app.set_theme(_rb_theme); app.update()
if _rb_settings:
    app.show_settings_page(); app.update()

# ---- THEME sweep, widened: caret, checkbox wells, press colours ----
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
app.checklist_add_var.set('tick')
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
    walk(app._checklist_rows)
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

# ---- The light/dark switch remembers each kind from one start to the next ----
# Forgotten at each start, it promised the last theme used and gave the
# default after a restart.
from noteorganizer.core.themes import last_of_each as _lt_last
_lt_was = app.theme_name
app.set_theme('dark_ocean'); app.update()
app.set_theme('light_sky'); app.update()
_lt_kept = (NO.load_settings().get('last_dark_theme'), NO.load_settings().get('last_light_theme'))
check(f"the switch's last dark and light themes are written for the next start ({_lt_kept})",
      _lt_kept == ('dark_ocean', 'light_sky'))
check("...and read back at a start, the theme worn first, a name no theme has passed over",
      _lt_last('light_sky', *_lt_kept) == ('dark_ocean', 'light_sky')
      and _lt_last('dark', 'no_such', 'light_mint') == ('dark', 'light_mint')
      and _lt_last('light_warm', ['x'], None) == ('dark', 'light_warm'))
# ...the start's own reading, from the file (no window opened twice):
app._last_dark_theme = app._last_light_theme = None
app._load_last_themes()
check(f"...and a start reads them from settings.json ({app._last_dark_theme}, {app._last_light_theme})",
      (app._last_dark_theme, app._last_light_theme) == ('dark_ocean', 'light_sky'))
# A dark theme a newer version named, which this one passes over, is kept
# while a light one is chosen: the switch wrote "dark" over it.
NO.save_setting('last_dark_theme', 'dark_rose')
app._load_last_themes()
app.set_theme('light_mint'); app.update()
check(f"...and a newer version's dark theme stays while a light one is chosen "
      f"({NO.load_settings().get('last_dark_theme')!r})",
      NO.load_settings().get('last_dark_theme') == 'dark_rose')
app.set_theme(_lt_was); app.update()
# A list or an object in "theme" is read as no theme: `in THEMES` raised on
# it, and every start stopped.
NO.save_setting('theme', ['dark'])
try:
    _lt_loaded = app.load_theme_setting()
except TypeError as _lt_e:   # this check's FAIL, not the suite's end
    _lt_loaded = 'raised %s' % _lt_e
app.save_theme_setting()
check(f"a list in the theme setting is read as the default, not a start that stops ({_lt_loaded!r})",
      _lt_loaded == 'dark')

# ---- PERFORMANCE: note list with larger count ----
# This check used to assert a literal True: it measured the time, printed
# it into its own label, and passed unconditionally. It was the only
# guard over the note list's rebuild cost -- the thing the product review
# calls "every pause in typing freezes the app" -- and it could not fail.
# Recorded as T1-4 in docs/archive/PRODUCT_FINDINGS.md.
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
    _ls_wide, _ls_wide_px = app._cal_last_font_size, app.winfo_width()
    app.geometry('1100x850')
    _ls_end = time.time() + 5
    while app._cal_last_font_size != 9 and time.time() < _ls_end:
        app.update(); time.sleep(0.02)
    # The window's own width is in the message: when the screen cuts a
    # requested size, the reading says so instead of blaming the calendar.
    check(f'...and the calendar still takes its width step from the '
          f'window\'s resize (wide {_ls_wide} at {_ls_wide_px}px, narrow '
          f'{app._cal_last_font_size} at {app.winfo_width()}px)',
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
          f'resized away from ({app._cal_last_font_size} at '
          f'{app.winfo_width()}px)',
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

# A rebuild while scrolled draws as deep as the view needs -- down to a
# screen below it -- so the place restored in pixels has content to land
# on. It used to draw again every row drawn before, which is the next check.
app.canvas.yview_moveto(0); _ls_settle()
app.refresh_note_list(); _ls_settle()
for _ in range(4):
    app.canvas.yview_moveto(1.0); app.update()
app.canvas.yview_moveto(0.6); _ls_settle()
_ls_px = app.canvas.canvasy(0)
app.refresh_note_list()
# Read once the restore has run its course: straight after the call the
# view has not been clamped yet, so the place would match for nothing.
_ls_let_restores_finish()
_ls_view_h = app.canvas.winfo_height()
check(f'a rebuild while scrolled keeps the place '
      f'({app.canvas.canvasy(0):.0f} of {_ls_px:.0f}) with rows drawn below '
      f'it ({app._list_end_y():.0f}px drawn, the view ends at '
      f'{app.canvas.canvasy(0) + _ls_view_h:.0f})',
      _ls_px > 0 and abs(app.canvas.canvasy(0) - _ls_px) < 30
      and (app._list_end_y() >= app.canvas.canvasy(0) + _ls_view_h
           or not app._list_pending))
# ...and no deeper than that. One trip to the end of the list draws every
# row; back near the top, a rebuild drew all of them again from then on --
# every pin, Select mode, grouping or search paying for 1,000 rows where
# the top of the list costs 30.
_ls_scroll_to_end()
_ls_all = len(app._list_drawn_keys)
app._list_restore_px = None
app._apply_list_scroll_px(109); _ls_settle()
app.refresh_note_list()
_ls_let_restores_finish()
check(f'after one trip to the end of the list, a rebuild near the top draws '
      f'a screenful again, not the {_ls_all} rows the trip drew '
      f'({len(app._list_drawn_keys)} drawn; view at {app.canvas.canvasy(0):.0f})',
      _ls_all >= 290
      and len(app._list_drawn_keys) <= app.LIST_FIRST_DRAW + app.LIST_DRAW_STEP
      and abs(app.canvas.canvasy(0) - 109) < 2)

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

# One note pinned, given another category, or moved in Custom order, from
# far down the list: its card alone is redrawn, as a save's is. A full
# rebuild drew every row above the view -- 1.3 s for one pin at 10,000
# notes (tools/bench.py --deep). The keyboard's ring is off the list here:
# with it on, the rebuild stays, since following the ring is the rebuild's
# (the pinned-card check in section 5).
_ls_rebuilds = []
_ls_real_refresh = NO.NoteOrganizer.refresh_note_list


def _ls_one_note_change(action):
    """Do *action* with the list scrolled to its end; return how many full
    rebuilds it made and whether the list is then what a rebuild draws."""
    # The keyboard elsewhere, as <FocusOut> records it: a test process
    # does not own the desktop's focus to make that happen (qa/README).
    app.title_entry.focus_set(); app._keyboard_on_card = False
    _ls_scroll_to_end(); _ls_settle()
    del _ls_rebuilds[:]
    app.refresh_note_list = lambda: (_ls_rebuilds.append(1), _ls_real_refresh(app))[1]
    try:
        action(); _ls_settle()
    finally:
        app.__dict__.pop('refresh_note_list', None)
    return len(_ls_rebuilds), _ls_same_as_rebuild()


_ls_scroll_to_end(); _ls_settle()
_ls_deep = _ls_card_ids()[-1]
_ls_n, _ls_same = _ls_one_note_change(lambda: app.toggle_pin(app.find_note(_ls_deep)))
check(f'pinning a note from the end of the list redraws its card alone '
      f'({_ls_n} rebuilds; first now {_ls_card_ids()[:1]}, pinned {_ls_deep})',
      _ls_n == 0 and _ls_card_ids()[:1] == [_ls_deep] and _ls_same)
app.toggle_pin(app.find_note(_ls_deep)); _ls_settle()
NO.CATEGORY_COLORS.setdefault('Moved', '#7a7a7a')
_ls_scroll_to_end(); _ls_settle()
_ls_recat = _ls_card_ids()[-1]
_ls_n, _ls_same = _ls_one_note_change(
    lambda: app._ctx_move_to_category(app.find_note(_ls_recat), 'Moved'))
check(f'...and so does giving it another category ({_ls_n} rebuilds)',
      _ls_n == 0 and app.find_note(_ls_recat)['category'] == 'Moved' and _ls_same)
app._ctx_move_to_category(app.find_note(_ls_recat), 'General'); _ls_settle()
NO.CATEGORY_COLORS.pop('Moved', None)
app.sort_var.set(app.SORT_CUSTOM)
app.refresh_note_list(); _ls_settle()
_ls_scroll_to_end(); _ls_settle()
_ls_a, _ls_b = _ls_card_ids()[-2:]
_ls_n, _ls_same = _ls_one_note_change(lambda: app._move_note(_ls_b, before_id=_ls_a))
_ls_order = [r[1]['id'] for r in app._list_rows() if r[0] == 'note']
check(f'...and moving it a place in Custom order ({_ls_n} rebuilds; {_ls_b} put '
      f'before {_ls_a}: {_ls_order[-3:]}; as a rebuild draws: {_ls_same})',
      _ls_n == 0 and _ls_order.index(_ls_b) + 1 == _ls_order.index(_ls_a) and _ls_same)
app.sort_var.set('Recently updated')
app.refresh_note_list(); _ls_settle()

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
# Held until the state promised: the list scrolled well down AND the rows
# that were waiting drawn. Waiting for the rows alone measured how fast the
# scroll STARTS, which it now does slowly on purpose (see the edge-slip
# checks below): the first rows arrived after 84px.
_co_end = time.time() + 6
while time.time() < _co_end and (len(app._list_drawn) <= _co_drawn
                                 or app.canvas.canvasy(0) - _co_top <= 100):
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
# To the end the way the scrollbar goes there: a deliberate move that beats
# the restore the rebuild above left in force (qa/README). A bare
# yview_moveto did not, so the restore could pull the view back up in the
# middle of this measurement -- counted as the edge scrolling when it
# landed after the press, and costing the drag its card when it landed
# before the click (0px, seen once under a mutant elsewhere).
app._list_scrollbar_moved('moveto', '1.0'); _ls_settle()
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


# A press AT an edge is not a drag carried there. The card the list's edge
# cuts is the one a hand most often clicks, and a click whose hand slips
# five pixels starts a drag: it scrolled the list under the held card from
# the very first beat, and the release dropped the card a place or three
# away -- the list in Custom order, or a hand-made one changed silently. A
# drag that begins at an edge scrolls only once it has been out in the open
# list, or has stayed at the edge a while; and any arrival at an edge starts
# slowly. The beats are driven here by hand, the timers cancelled, so no
# stopwatch decides what a beat did.
def _co_cancel_beat():
    drag = app._drag
    if drag['scroll_job'] is not None:
        app.after_cancel(drag['scroll_job'])
        drag['scroll_job'] = None


def _co_beat():
    """One beat of the edge scroll, as its timer would run it; returns how
    far it moved the view. The drag's own timer is cancelled before and
    after, so only these beats move anything."""
    _co_cancel_beat()
    top = app.canvas.canvasy(0)
    app._list_drag_scroll_step()
    _co_cancel_beat()
    app.update_idletasks()
    return app.canvas.canvasy(0) - top


def _co_press_at(y):
    """A press on the card at (or a few pixels from) widget y; returns
    where. Measured AFTER it: a press brings a card the edge cuts into view
    itself, which is not the edge scrolling."""
    for yy in [y] + [y + d for d in range(-6, 7) if d]:
        rec = app._list_record_at(120, yy)
        if rec is not None and rec['kind'] == 'note':
            y = yy
            break
    _qa_click(app.canvas, x=120, y=y); _ls_settle()
    return y


def _co_edge_slip(y, dy):
    """A press on the card at widget y and a slip of dy pixels with the
    button held, then a beat; returns (drag started, view moved, slot)."""
    y = _co_press_at(y)
    top = app.canvas.canvasy(0)
    _qa_fire(app.canvas, '<B1-Motion>', x=120, y=y + dy // 2); app.update()
    _qa_fire(app.canvas, '<B1-Motion>', x=120, y=y + dy); app.update()
    drag = getattr(app, '_drag', None)
    started = bool(drag and drag['started'])
    if started:
        _co_beat()
    slot = drag['slot'] if drag else None
    moved = app.canvas.canvasy(0) - top
    _qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=y + dy); _ls_settle()
    return started, moved, slot


_co_edge_notes = [{'id': 1750 + i, 'title': 'Edge %02d' % i, 'body': 'b',
                   'category': 'General', 'created': '2026-01-01 00:%02d' % i,
                   'updated': '2026-02-01 00:%02d' % (59 - i)}
                  for i in range(14)]
_co_fresh(_co_edge_notes)
app._list_scrollbar_moved('moveto', '0.3'); _ls_settle()
_co_order = app._card_order()
# However long the hold: what is asked is whether a beat may scroll yet.
app.DRAG_EDGE_DWELL_MS = 10 ** 9
try:
    _co_bottom = _co_edge_slip(app.canvas.winfo_height() - 10, 6)
    _co_top = _co_edge_slip(10, -6)
finally:
    app.__dict__.pop('DRAG_EDGE_DWELL_MS', None)
check(f'a click whose hand slips 6px on a card at the list\'s bottom or top '
      f'edge scrolls nothing and drops nothing (bottom: started, moved, slot '
      f'{_co_bottom}; top {_co_top}; sort {app.sort_var.get()!r}, notes with '
      f'a place: {sum(1 for n in app.notes if "order" in n)})',
      _co_bottom == (True, 0, None) and _co_top == (True, 0, None)
      and app.sort_var.get() == 'Recently updated'
      and not any('order' in n for n in app.notes)
      and app._card_order() == _co_order)
# A press a pixel or three OUTSIDE the edge counted as one in the open
# list: the same slip into the edge then scrolled the list at once, and a
# slow click dropped the card a place away. A slip away from the edge
# waits as one at it does.
_co_out = None
for _co_d in (1, 2, 3):
    _co_yy = app.canvas.winfo_height() - app.DRAG_EDGE - _co_d
    _co_rec = app._list_record_at(120, _co_yy)
    if _co_rec is not None and _co_rec['kind'] == 'note':
        _co_out = _co_yy
        break
check(f'fixture: a card lies a few pixels outside the list\'s bottom edge '
      f'(at y {_co_out})', _co_out is not None)
app.DRAG_EDGE_DWELL_MS = 10 ** 9
try:
    _co_outside = _co_edge_slip(_co_out, 7) if _co_out is not None else None
    # A slip that passes first through the strip just outside the edge is
    # not the pointer having been out in the open list either.
    _co_far = (_co_edge_slip(_co_out - 6, 12) if _co_out is not None
               and app._list_record_at(120, _co_out - 6) is not None else None)
finally:
    app.__dict__.pop('DRAG_EDGE_DWELL_MS', None)
check(f'...and a click there whose hand slips 7px into the edge scrolls '
      f'nothing and drops nothing, nor one pressed 6px further in that slips '
      f'12px (started, moved, slot {_co_outside}; {_co_far}; sort '
      f'{app.sort_var.get()!r})',
      _co_outside == (True, 0, None) and _co_far == (True, 0, None)
      and app.sort_var.get() == 'Recently updated'
      and not any('order' in n for n in app.notes))
# ...while one held there scrolls the list after all: a card at the edge
# can still be taken further than the list shows. Waited for, not timed.
_co_y = _co_press_at(app.canvas.winfo_height() - 10)
_co_top0 = app.canvas.canvasy(0)
_qa_fire(app.canvas, '<B1-Motion>', x=120, y=_co_y + 6); app.update()
_co_end = time.time() + 6
while time.time() < _co_end and app.canvas.canvasy(0) == _co_top0:
    app.update(); time.sleep(0.02)
_co_held = app.canvas.canvasy(0) - _co_top0
app._list_drag_escape()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_y + 6); _ls_settle()
check(f'...while a drag held at the edge it began on scrolls the list after a '
      f'moment ({_co_held:.0f}px)', _co_held > 0
      and app._card_order() == _co_order)
# Arriving at the edge from the open list, the first beat is a part of the
# full step, and the steps grow to it.
_co_fresh([dict(n, id=2300 + i, title='Ramp %02d' % i)
           for i, n in enumerate(_co_edge_notes * 3)])
_co_h = app.canvas.winfo_height()
_co_y = _co_press(2301)
for _co_to in range(_co_y, _co_h - 30, 6):
    _qa_fire(app.canvas, '<B1-Motion>', x=120, y=_co_to); app.update()
_qa_fire(app.canvas, '<B1-Motion>', x=120, y=_co_h - 3)
_co_steps = [_co_beat() for _ in range(12)]
_co_full = min(10, 1 + (_co_h - 3 - (_co_h - app.DRAG_EDGE)) // 8) * _co_h / 10.0
app._list_drag_escape()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_co_h - 3); _ls_settle()
check(f'...and arriving at an edge from the open list, the scroll starts with '
      f'a part of its step and grows to all of it ({[round(s) for s in _co_steps]}'
      f'; the full step {_co_full:.0f}px)',
      0 < _co_steps[0] <= _co_full / 5
      and all(b >= a for a, b in zip(_co_steps, _co_steps[1:]))
      and abs(_co_steps[-1] - _co_full) <= 1.5)
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

# 5b. A click whose own open moves the rows under the pointer. Opening a
# note first saves the one left behind, and under a sort by date that save
# moves the saved card: the cards between slide, the clicked one included.
# What the pointer is over must stay what it was over -- for the second
# press of a double-click, and for a drag the press may start. One check
# per mechanism, because two of them hold the double-click together.
_bl_notes = [{'id': 1800 + i, 'title': 'Hurry %02d' % i, 'body': 'b',
              'category': 'General', 'created': '2026-01-01 00:%02d' % i,
              'updated': '2026-02-01 00:%02d' % (59 - i)} for i in range(12)]


def _bl_type_in(nid):
    """Open a note and type in it, leaving the save pending -- what the
    next click's open will flush."""
    app.open_note_in_tab(app.find_note(nid)); _ls_settle()
    app.body_text.insert('end', ' typed')
    app._schedule_autosave()


def _bl_y_at(nid, frac):
    v = app._card_view(nid)
    return int(v['y0'] + (v['y1'] - v['y0']) * frac - app.canvas.canvasy(0))


# The list keeps the clicked card under the pointer when it can scroll far
# enough: Recently updated moves the saved card to the top, above it.
_co_fresh(_bl_notes)
_bl_o = app._card_order()
_bl_h = app.canvas.winfo_height()
_bl_type_in(_bl_o[2])
_bl_y = _bl_y_at(_bl_o[1], 0.25)
check(f'fixture: a list long enough to scroll, the card to click in view '
      f'({app._list_extent()[3]:.0f}px of list, a {_bl_h}px view, the click '
      f'at y={_bl_y})', app._list_extent()[3] > _bl_h + 200 and 0 <= _bl_y < _bl_h)
_qa_click(app.canvas, x=120, y=_bl_y); _ls_settle()
_bl_under = app._list_record_at(120, _bl_y)
_bl_under = _bl_under['note']['id'] if _bl_under else None
check(f'a click whose open saves the note left behind keeps the clicked card '
      f'under the pointer (open {app.selected_note_id}, under the pointer '
      f'{_bl_under}, clicked {_bl_o[1]}; the saved card went to the top: '
      f'{app._card_order()[:1]})',
      app.selected_note_id == _bl_o[1] and _bl_under == _bl_o[1]
      and app._card_order()[0] == _bl_o[2])
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y); _ls_settle()
# A second press at the same spot is the second half of a double-click (Tk
# calls it one), and it goes to the card now under the pointer: the same.
_qa_click(app.canvas, x=120, y=_bl_y); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y); _ls_settle()
check(f'...so a double-click on it opens it ({app.selected_note_id})',
      app.selected_note_id == _bl_o[1])

# When the list cannot scroll far enough, the second press follows the first
# one's aim. Oldest updated at the top of the list: the saved card goes to
# the BOTTOM, the clicked card slides up, and a view at the top cannot
# scroll up after it -- whatever the window's or the fonts' size.
_co_fresh(_bl_notes, sort='Oldest updated')
_bl_o = app._card_order()
_bl_type_in(_bl_o[0])
_bl_y = _bl_y_at(_bl_o[1], 0.25)
_qa_click(app.canvas, x=120, y=_bl_y); _ls_settle()
_bl_under = app._list_record_at(120, _bl_y)
_bl_under = _bl_under['note']['id'] if _bl_under else None
check(f'fixture: the clicked card slid out from under the pointer and the '
      f'list could not follow it (open {app.selected_note_id}, under the '
      f'pointer {_bl_under}, clicked {_bl_o[1]}, view at '
      f'{app.canvas.canvasy(0):.0f})',
      app.selected_note_id == _bl_o[1] and _bl_under not in (None, _bl_o[1]))
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y); _ls_settle()
_qa_click(app.canvas, x=120, y=_bl_y); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y); _ls_settle()
check(f'...and a double-click still opens the card it was aimed at, not the '
      f'one that slid under the pointer ({app.selected_note_id}; under the '
      f'pointer {_bl_under})', app.selected_note_id == _bl_o[1])
# The aim lasts as long as a double-click can: a press made later goes where
# it points. Tk reads a made-up event's timestamp as 0, so it calls this
# press the second half of a double-click too -- only the aim's own clock
# can tell the two apart (a stale aim once opened the wrong note here).
_bl_under_now = app._list_record_at(120, _bl_y)
_bl_under_now = _bl_under_now['note']['id'] if _bl_under_now else None
_ls_let_restores_finish()
_qa_click(app.canvas, x=120, y=_bl_y); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y); _ls_settle()
check(f'...while a press a second later opens the card under the pointer '
      f'({app.selected_note_id}; under the pointer {_bl_under_now})',
      _bl_under_now not in (None, _bl_o[1])
      and app.selected_note_id == _bl_under_now)

# ...and a hand that slips a few pixels while that press is held drops
# nothing. A drag armed on a card that slid away measured its grab against
# a place the hand was not on, so the slip "dropped" the clicked card
# before its neighbour and switched the whole list to Custom order.
_co_fresh(_bl_notes, sort='Oldest updated')
_bl_o = app._card_order()
_bl_type_in(_bl_o[0])
# The LOWER part of the card: once it has slid up, the pointer is over the
# lower half of the card that took its place, where a drag armed anyway
# reads "before the next one" -- a real drop, not the card's own place.
_bl_y = _bl_y_at(_bl_o[1], 0.75)
check(f'fixture: the lower part of the card to press is on screen (y={_bl_y} '
      f'of {app.canvas.winfo_height()})', 0 <= _bl_y < app.canvas.winfo_height())
_qa_click(app.canvas, x=120, y=_bl_y); _ls_settle()
for _bl_dy in (3, 6):
    _qa_fire(app.canvas, '<B1-Motion>', x=120, y=_bl_y + _bl_dy); app.update()
_bl_started = bool(getattr(app, '_drag', None) and app._drag['started'])
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y + 6); _ls_settle()
check(f'a 6px slip while pressing a card that slid away drops nothing '
      f'(drag started: {_bl_started}; sort {app.sort_var.get()!r}; notes '
      f'with a place: {sum(1 for n in app.notes if "order" in n)})',
      not _bl_started and app.sort_var.get() == 'Oldest updated'
      and not any('order' in n for n in app.notes))

# A header's own press can move it too: folding the last group of a list
# scrolled to its end shortens the list, the view clamps, and the header
# slides down from under the pointer -- where the second press of a
# double-click then opened the card that slid in, instead of unfolding.
_bl_work_added = 'Work' not in NO.CATEGORY_COLORS
NO.CATEGORY_COLORS.setdefault('Work', '#4cc9f0')
_co_fresh([dict(n, category='General') for n in _bl_notes[:10]]
          + [dict(n, category='Work') for n in _bl_notes[10:]])
app.group_by_category.set(True)
app.collapsed_groups.discard('Work')
app.refresh_note_list(); _ls_settle()
app._list_scrollbar_moved('moveto', '1.0'); _ls_settle()
_ls_let_restores_finish()
_bl_hd = app._header_view('Work')
_bl_y = int((_bl_hd['y0'] + _bl_hd['y1']) / 2 - app.canvas.canvasy(0))
_bl_open = app.selected_note_id
_qa_click(app.canvas, x=200, y=_bl_y); _ls_settle()
_bl_under = app._list_record_at(200, _bl_y)
_bl_under = _bl_under and _bl_under['key']
_qa_fire(app.canvas, '<ButtonRelease-1>', x=200, y=_bl_y); _ls_settle()
check(f'fixture: folding the last group of a list scrolled to its end moves '
      f'its header from under the pointer (folded: '
      f'{"Work" in app.collapsed_groups}; under the pointer now {_bl_under})',
      'Work' in app.collapsed_groups and _bl_under != ('header', 'Work'))
_qa_click(app.canvas, x=200, y=_bl_y); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=200, y=_bl_y); _ls_settle()
check(f'...and a double-click on that header unfolds the same group again, '
      f'opening nothing (folded: {sorted(app.collapsed_groups)}; open '
      f'{app.selected_note_id}, was {_bl_open})',
      'Work' not in app.collapsed_groups and app.selected_note_id == _bl_open)
app.group_by_category.set(False)
app.collapsed_groups.discard('Work')
if _bl_work_added:
    NO.CATEGORY_COLORS.pop('Work', None)

# How far the HAND moved decides a drag, not how far the view did: the view
# can move under a held button (a rebuild's restore landing late), and read
# in canvas pixels a 1px jitter then passed for a drag.
_co_fresh(_bl_notes)
_bl_o = app._card_order()
_bl_y = _co_press(_bl_o[1])
_bl_top = app.canvas.canvasy(0)
app._list_restore_px = None
app._apply_list_scroll_px(_bl_top + 12); _ls_settle()
_bl_moved = app.canvas.canvasy(0) - _bl_top
_qa_fire(app.canvas, '<B1-Motion>', x=120, y=_bl_y + 1); app.update()
_bl_started = bool(getattr(app, '_drag', None) and app._drag['started'])
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y + 1); _ls_settle()
check(f'the view moving under a held button is not the hand moving: a 1px '
      f'jitter starts no drag (the view moved {_bl_moved:.0f}px; drag '
      f'started: {_bl_started})', _bl_moved >= 10 and not _bl_started
      and app.sort_var.get() == 'Recently updated')

# A deliberate scroll beats a rebuild's restore even before that restore
# has started: it was queued for the next idle moment as a callback nothing
# could cancel, and it scrolled the view back after the scroll-into-view.
_co_fresh(_bl_notes)
_bl_o = app._card_order()
app._apply_list_scroll_px(40); _ls_settle()
_bl_was = app.canvas.canvasy(0)
app.refresh_note_list()
app._scroll_row_into_view(app._note_cards[_bl_o[-1]])
_bl_want = app.canvas.canvasy(0)
_ls_let_restores_finish()
check(f'a deliberate scroll made before a rebuild\'s restore has run beats '
      f'it (view {app.canvas.canvasy(0):.0f}, scrolled to {_bl_want:.0f}, '
      f'the rebuild was at {_bl_was:.0f})',
      _bl_was > 0 and _bl_want > _bl_was + 50
      and abs(app.canvas.canvasy(0) - _bl_want) < 2)

# The reported route end to end: the emoji picker open while typing, so the
# autosave leaves the list as it was; the list scrolled; a click on a card
# above the edited one, whose open catches the list up with a full rebuild;
# a 1px jitter. Nothing may move.
_co_fresh(_bl_notes)
app._apply_list_scroll_px(40); _ls_settle()
app._list_restore_px = None
_bl_top = app.canvas.canvasy(0)
_bl_o = app._card_order()
_bl_vis = [n for n in _bl_o if app._card_view(n)['y0'] >= _bl_top
           and app._card_view(n)['y1'] <= _bl_top + app.canvas.winfo_height()]
_bl_click = _bl_vis[-1] if _bl_vis else _bl_o[1]
_bl_edit = _bl_o[_bl_o.index(_bl_click) + 2]
app.open_note_in_tab(app.find_note(_bl_edit)); _ls_settle()
app._show_emoji_picker(app.body_text); _ls_settle()
app.body_text.insert('end', ' x')
app._schedule_autosave()
_bl_end = time.time() + 5
while not getattr(app, '_note_list_needs_refresh', False) and time.time() < _bl_end:
    app.update(); time.sleep(0.02)
_bl_deferred = bool(getattr(app, '_note_list_needs_refresh', False))
_bl_y = _bl_y_at(_bl_click, 0.2)
_qa_click(app.canvas, x=120, y=_bl_y); _ls_settle()
_qa_fire(app.canvas, '<B1-Motion>', x=120, y=_bl_y + 1); app.update()
_bl_started = bool(getattr(app, '_drag', None) and app._drag['started'])
_qa_fire(app.canvas, '<ButtonRelease-1>', x=120, y=_bl_y + 1); _ls_settle()
_ls_let_restores_finish()
check(f'a click that catches up a deferred rebuild, with the list scrolled, '
      f'then a 1px jitter: nothing moves (autosave deferred the list: '
      f'{_bl_deferred}; drag started: {_bl_started}; open '
      f'{app.selected_note_id} of {_bl_click}; sort {app.sort_var.get()!r})',
      _bl_deferred and not _bl_started and app.selected_note_id == _bl_click
      and app.sort_var.get() == 'Recently updated'
      and not any('order' in n for n in app.notes))
app.__dict__.pop('DRAG_EDGE', None)

# 5c. Select all ticks exactly what the list shows (USER_GUIDE), and a
# folded group shows its header, not its notes. Asked only of the search and
# the filter, Select all ticked the five notes folded away too, and bulk
# Trash took them. Pressed on the bar's own button, as a person presses it.
_bl_work_added = 'Work' not in NO.CATEGORY_COLORS
NO.CATEGORY_COLORS.setdefault('Work', '#4cc9f0')
_co_fresh([dict(n, category='Work') for n in _bl_notes[:5]]
          + [dict(n, category='General') for n in _bl_notes[5:9]])
_bl_general = {n['id'] for n in _bl_notes[5:9]}
app.group_by_category.set(True)
app.collapsed_groups.clear()
app.collapsed_groups.add('Work')
app.refresh_note_list(); _ls_settle()
check(f'fixture: a grouped list with Work folded shows only the General '
      f'cards ({app._card_order()}; Work header '
      f'{(app._header_view("Work") or {}).get("label")!r})',
      set(app._card_order()) == _bl_general
      and (app._header_view('Work') or {}).get('caret') == '▶')
app._toggle_selection_mode(); _ls_settle()
app._bulk_select_all_btn.invoke(); _ls_settle()
check(f'Select all over a folded group ticks only the notes the list shows '
      f'({sorted(app.selected_note_ids)}; label '
      f'{app.bulk_selected_lbl.cget("text")!r}, button '
      f'{app._bulk_select_all_btn.cget("text")!r})',
      app.selected_note_ids == _bl_general
      and app.bulk_selected_lbl.cget('text') == '4 selected'
      and app._bulk_select_all_btn.cget('text') == 'Unselect all')
app._toggle_group_collapsed('Work'); _ls_settle()
check(f'...and unfolding the group puts unticked notes on show, so the button '
      f'offers Select all again ({app._bulk_select_all_btn.cget("text")!r})',
      app._bulk_select_all_btn.cget('text') == 'Select all'
      and app.selected_note_ids == _bl_general)
app._toggle_selection_mode(); _ls_settle()
app.group_by_category.set(False)
app.collapsed_groups.clear()
if _bl_work_added:
    NO.CATEGORY_COLORS.pop('Work', None)

# 5d. A ticked note that is deleted leaves the selection. It kept its tick:
# the bar went on counting it, and since a new note's id is the highest plus
# one, the next note made took the freed id and arrived ticked -- trashed by
# a Trash nobody aimed at it. Two routes, because deletes end in two places:
# the one card taken off (_remove_note_cards), or a rebuild.
_co_fresh(_bl_notes[:8])
_bl_ids = sorted(n['id'] for n in app.notes)
_bl_top, _bl_keep = _bl_ids[-1], _bl_ids[2]
app._toggle_selection_mode(); _ls_settle()
for _bl_n in (_bl_keep, _bl_top):
    _bl_pt = app._card_point(_bl_n)
    app._scroll_row_into_view(app._note_cards[_bl_n]); _ls_settle()
    _bl_pt = app._card_point(_bl_n)
    _qa_click(app.canvas, x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
check(f'fixture: two notes ticked on their cards, one of them the highest id '
      f'({sorted(app.selected_note_ids)}, {app.bulk_selected_lbl.cget("text")!r})',
      app.selected_note_ids == {_bl_keep, _bl_top}
      and app.bulk_selected_lbl.cget('text') == '2 selected')
app.ask_yes_no = lambda *a, **k: True
try:
    app._context_delete_note(app.find_note(_bl_top)); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
check(f'a ticked note deleted from its own menu leaves the selection, and the '
      f'bar says so ({sorted(app.selected_note_ids)}, '
      f'{app.bulk_selected_lbl.cget("text")!r})',
      app.find_note(_bl_top) is None and app.selected_note_ids == {_bl_keep}
      and app.bulk_selected_lbl.cget('text') == '1 selected')
app.open_blank_tab(); _ls_settle()
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'Brand new shopping list')
app.save_current_note(auto=True); _ls_settle()
_bl_new = app.selected_note_id
_bl_view = app._card_view(_bl_new) or {}
check(f'...so a new note that takes the freed id arrives unticked (new id '
      f'{_bl_new}, freed {_bl_top}; ticked: {_bl_view.get("checked")}; '
      f'selection {sorted(app.selected_note_ids)})',
      _bl_new == _bl_top and _bl_view.get('checked') is False
      and app.selected_note_ids == {_bl_keep})
app._toggle_selection_mode(); _ls_settle()

# The rebuild's route: a category deleted together with its notes.
_bl_work_colour = NO.CATEGORY_COLORS.get('Work')
NO.CATEGORY_COLORS.setdefault('Work', '#4cc9f0')
_co_fresh([dict(n, category='Work') for n in _bl_notes[:3]]
          + [dict(n, category='General') for n in _bl_notes[3:8]])
_bl_work = {n['id'] for n in _bl_notes[:3]}
_bl_gen = _bl_notes[4]['id']
app._toggle_selection_mode(); _ls_settle()
app.selected_note_ids = set(_bl_work) | {_bl_gen}
app._sync_card_checkboxes(); app._update_bulk_selected_label(); _ls_settle()
app._ask_category_deletion = lambda *a, **k: 'delete_notes'
try:
    app._delete_category('Work', lambda: None); _ls_settle()
finally:
    app.__dict__.pop('_ask_category_deletion', None)
check(f'...and so do ticked notes that went with their category '
      f'({sorted(app.selected_note_ids)}, '
      f'{app.bulk_selected_lbl.cget("text")!r})',
      not any(app.find_note(i) for i in _bl_work)
      and app.selected_note_ids == {_bl_gen}
      and app.bulk_selected_lbl.cget('text') == '1 selected')
app._toggle_selection_mode(); _ls_settle()
# The category was really deleted; one that was there before comes back.
if _bl_work_colour is not None:
    NO.CATEGORY_COLORS['Work'] = _bl_work_colour
    NO.persist_categories()
    app.refresh_category_widgets(); _ls_settle()

# 5e. An arrangement made by hand is never replaced without a word. A move
# made while the list is sorted another way still starts Custom order from
# the order shown (as documented), but when notes already had places, the
# toast says the old arrangement went and offers it back. It used to go in
# silence: one Alt+Down while looking at the list by title, and the
# arrangement was gone from the notes file.
_bl_fruit = ['Zebra', 'Apple', 'Mango', 'Banana', 'Kiwi', 'Cherry', 'Lemon',
             'Grape']
_bl_hand = ['Lemon', 'Apple', 'Zebra', 'Grape', 'Kiwi', 'Banana', 'Cherry',
            'Mango']
_bl_placed = [{'id': 1900 + i, 'title': t + ' note', 'body': 'b',
               'category': 'General', 'created': '2026-01-01 00:%02d' % i,
               'updated': '2026-02-01 00:%02d' % i, 'order': _bl_hand.index(t)}
              for i, t in enumerate(_bl_fruit)]
_bl_hand_ids = [1900 + _bl_fruit.index(t) for t in _bl_hand]


def _bl_names():
    return [app.find_note(i)['title'].split()[0] for i in app._card_order()]


def _bl_sort(value):
    """Choose a sort the way the dropdown does."""
    app.sort_var.set(value)
    app._on_sort_chosen(value); _ls_settle()


def _bl_file_names():
    """The notes file's Custom order, by the first word of each title: a
    note brought back from the Trash returns under a new id."""
    return [app.find_note(i)['title'].split()[0] for i in _co_file_order()]


# Every question a sort asks in this block is answered here and written
# down: a real one would wait for a person who is not there.
_bl_questions = []
_bl_answer = [False]
app.ask_yes_no = lambda title, message, **k: (
    _bl_questions.append((title, message)), _bl_answer[0])[1]
_co_fresh(_bl_placed, sort='Custom order')
check(f'fixture: a Custom order arranged by hand ({_bl_names()})',
      _bl_names() == _bl_hand and _co_file_order() == _bl_hand_ids)
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
_bl_said = app.toast_lbl.cget('text')
check(f'a move in another sort that replaces an arrangement made by hand says '
      f'so and offers it back ({_bl_said!r}; sort now {app.sort_var.get()!r})',
      app.sort_var.get() == 'Custom order' and app._toast_action is not None
      and 'Title A–Z' in _bl_said)
_qa_click(app.toast_action_lbl); _ls_settle()
check(f'...and Undo on the toast puts back the arrangement and the sort, in '
      f'the notes file too (sort {app.sort_var.get()!r}; file order '
      f'{_co_file_order() == _bl_hand_ids})',
      app.sort_var.get() == 'Title A–Z' and _co_file_order() == _bl_hand_ids)
_bl_sort('Custom order')
check(f'...so choosing Custom order again shows it as it was made, and asks '
      f'nothing -- Undo already put it back ({_bl_names()}; asked '
      f'{[q[0] for q in _bl_questions]})',
      _bl_names() == _bl_hand and not _bl_questions)
# Moves made on top of the replacement go with it: they were made on it.
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
_qa_click(app.toast_action_lbl); _ls_settle()
_bl_sort('Custom order')
check(f'...also after more moves made in the new order before Undo '
      f'({_bl_names()})',
      _bl_names() == _bl_hand and _co_file_order() == _bl_hand_ids)
# Nothing to replace, nothing said: the first move ever still starts Custom
# order from the order shown, quietly, as it always did.
_co_fresh([{k: v for k, v in n.items() if k != 'order'} for n in _bl_placed],
          sort='Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
check(f'...while a first move, with no arrangement to lose, says nothing '
      f'(sort {app.sort_var.get()!r}, an offer on screen: '
      f'{app._toast_action is not None})',
      app.sort_var.get() == 'Custom order' and app._toast_action is None
      and len(_co_file_order()) == len(_bl_placed))
app._hide_toast()
# The offer outlives its toast. The app shows one toast at a time, and the
# next one with an Undo -- a delete's, within the offer's eight seconds --
# took its place: the arrangement made by hand then had no way back at all.
# It is kept for the session, and choosing Custom order asks, once, whether
# to bring it back.
_co_fresh(_bl_placed, sort='Custom order')
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
_bl_answer[0] = True
app._context_delete_note(next(n for n in app.notes
                              if n['title'].startswith('Zebra'))); _ls_settle()
_bl_said = app.toast_lbl.cget('text')
# The delete's own Undo: the note comes back from the Trash, a new dict.
_qa_click(app.toast_action_lbl); _ls_settle()
del _bl_questions[:]
_bl_sort('Custom order')
_bl_asked = list(_bl_questions)
check(f'...and when a later toast took the offer\'s place, choosing Custom '
      f'order asks to bring the arrangement back, naming the sort that '
      f'replaced it, and Yes does -- the note deleted and restored meanwhile '
      f'too (the toast then: {_bl_said!r}; asked {[q[0] for q in _bl_asked]}; '
      f'now {_bl_names()}, in the file {_bl_file_names()})',
      'Trash' in _bl_said and len(_bl_asked) == 1
      and 'Title A–Z' in _bl_asked[0][1]
      and _bl_names() == _bl_hand and _bl_file_names() == _bl_hand)
del _bl_questions[:]
_bl_sort('Custom order')
check(f'...asked once: choosing Custom order again asks nothing (asked '
      f'{[q[0] for q in _bl_questions]})', not _bl_questions)
# A second move made in a sorted view counted the first move's order as an
# arrangement made by hand: its marks took the offer's place, and the
# arrangement really made by hand had no way back at all -- choosing
# Custom order asked nothing.
_co_fresh(_bl_placed, sort='Custom order')
for _bl_i in range(2):
    _bl_sort('Title A–Z')
    app._hide_toast()
    app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
del _bl_questions[:]
_bl_answer[0] = True
_bl_sort('Custom order')
check(f'...and after two moves made in a sorted view, choosing Custom order '
      f'offers back the arrangement made by hand, and Yes brings it (asked '
      f'{[q[0] for q in _bl_questions]}; now {_bl_names()})',
      len(_bl_questions) == 1 and _bl_names() == _bl_hand
      and _bl_file_names() == _bl_hand)
# The second move's own Undo puts back what that move replaced -- the first
# replacement -- and leaves the offer of the arrangement made by hand.
_co_fresh(_bl_placed, sort='Custom order')
for _bl_i in range(2):
    _bl_sort('Title A–Z')
    app._hide_toast()
    app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
_qa_click(app.toast_action_lbl); _ls_settle()
_bl_after_undo = app.sort_var.get()
del _bl_questions[:]
_bl_sort('Custom order')
check(f'...also when the second move\'s Undo was taken first (sort after it '
      f'{_bl_after_undo!r}; asked {[q[0] for q in _bl_questions]}; now '
      f'{_bl_names()})',
      _bl_after_undo == 'Title A–Z' and len(_bl_questions) == 1
      and _bl_names() == _bl_hand)
# Moves made by hand in Custom order after a sorted-view move make the
# list an arrangement made by hand again; a second sorted-view move then
# replaces THAT one, and it is the one offered back. The older offer was
# kept instead, and the newer arrangement had no way back.
_co_fresh(_bl_placed, sort='Custom order')
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[3]); _ls_settle()
app._list_move_by_keyboard(-1); _ls_settle()
app._list_move_by_keyboard(-1); _ls_settle()
_bl_newer = _bl_names()
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
del _bl_questions[:]
_bl_answer[0] = True
_bl_sort('Custom order')
check(f'...and when the replaced order was rearranged by hand in between, '
      f'the newer arrangement is the one offered back (asked '
      f'{[q[0] for q in _bl_questions]}; now {_bl_names()}; newer {_bl_newer})',
      len(_bl_questions) == 1 and _bl_names() == _bl_newer
      and _bl_newer != _bl_hand)
# Moves by hand that cancel out arrange nothing. Alt+Down then Alt+Up on one
# card left the list as the first sorted-view move had, and counted as an
# arrangement made by hand they gave the kept offer's place to that move's
# own result: choosing Custom order then asked nothing, and the arrangement
# really made by hand was gone.
_co_fresh(_bl_placed, sort='Custom order')
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
_bl_first = _bl_names()
app._put_keyboard_on_card(app._card_order()[3]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._list_move_by_keyboard(-1); _ls_settle()
_bl_back = _bl_names() == _bl_first
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
del _bl_questions[:]
_bl_answer[0] = True
_bl_sort('Custom order')
check(f'...and moves by hand that cancel out arrange nothing: the '
      f'arrangement made by hand is still the one offered back (back where '
      f'the first move left it: {_bl_back}; asked '
      f'{[q[0] for q in _bl_questions]}; now {_bl_names()})',
      _bl_back and len(_bl_questions) == 1 and _bl_names() == _bl_hand)
# A move's own Undo puts back what that move replaced -- which nobody
# arranged by hand since -- so a later sorted-view move keeps the offer it
# finds. The two moves move different cards, so the order each leaves is
# its own: the same move twice left one order, and could not tell the
# Undo's from the move's.
_co_fresh(_bl_placed, sort='Custom order')
for _bl_i in range(2):
    _bl_sort('Title A–Z')
    app._hide_toast()
    app._put_keyboard_on_card(app._card_order()[2 * _bl_i]); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
_qa_click(app.toast_action_lbl); _ls_settle()
_bl_after_undo = app.sort_var.get()
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
del _bl_questions[:]
_bl_answer[0] = True
_bl_sort('Custom order')
check(f'...and after the second move\'s Undo and a third move, it is still '
      f'the arrangement made by hand that is offered back (sort after the '
      f'Undo {_bl_after_undo!r}; asked {[q[0] for q in _bl_questions]}; now '
      f'{_bl_names()})',
      _bl_after_undo == 'Title A–Z' and len(_bl_questions) == 1
      and _bl_names() == _bl_hand)
# A NEW note placed by hand is an arrangement made by hand too: compared
# only among the notes the last sorted-view move knew, its placing counted
# for nothing, and the older arrangement was offered back.
_co_fresh(_bl_placed, sort='Custom order')
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
app.new_note()
app.title_entry.insert(0, 'Golf note')
app.body_text.insert('1.0', 'a new note')
app.save_current_note()
_ls_settle()
_bl_golf = app.selected_note_id
for _bl_i in range(2):
    app._put_keyboard_on_card(_bl_golf); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
_bl_newer = _bl_names()
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
del _bl_questions[:]
_bl_answer[0] = True
_bl_sort('Custom order')
check(f'...and a new note placed by hand makes the newer arrangement the one '
      f'offered back (asked {[q[0] for q in _bl_questions]}; now '
      f'{_bl_names()}; newer {_bl_newer})',
      len(_bl_questions) == 1 and _bl_names() == _bl_newer
      and 'Golf' in _bl_newer)
# A note deleted and brought back from the Trash meanwhile is the same note:
# known by the dict alone, it came back as one the last move had never
# seen, and counted as placed by hand -- the arrangement really made by
# hand gave its place to the first move's result.
_co_fresh(_bl_placed, sort='Custom order')
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
_bl_answer[0] = True
_bl_victim = next(n for n in app.notes if n['title'].startswith('Kiwi'))
app._delete_note(_bl_victim, None); _ls_settle()
app._hide_toast()
app._restore_trash_entries(
    [e for e in app.trash if (e.get('title') or '').startswith('Kiwi')])
_ls_settle()
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
app._hide_toast()
del _bl_questions[:]
_bl_sort('Custom order')
check(f'...while a note only deleted and restored in between arranges '
      f'nothing: the arrangement made by hand is still the one offered back '
      f'(asked {[q[0] for q in _bl_questions]}; now {_bl_names()})',
      len(_bl_questions) == 1 and _bl_names() == _bl_hand)
# A duplicate is born with its original's place, and a move by hand of
# ANOTHER card gives every note a place, a new one included: neither is a
# note placed by hand. Counted as one, it gave the kept offer's place to the
# first move's result, and the arrangement made by hand was gone.
_bl_kept_hand = []
for _bl_how in ('duplicate', 'jiggle'):
    _co_fresh(_bl_placed, sort='Custom order')
    _bl_sort('Title A–Z')
    app._hide_toast()
    app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
    app._hide_toast()
    if _bl_how == 'duplicate':
        app.duplicate_note(next(n for n in app.notes
                                if n['title'].startswith('Kiwi')))
        _ls_settle()
    else:
        app.new_note()
        app.title_entry.insert(0, 'Golf note')
        app.body_text.insert('1.0', 'a new note')
        app.save_current_note()
        _ls_settle()
        _bl_kiwi = next(n['id'] for n in app.notes
                        if n['title'].startswith('Kiwi'))
        app._put_keyboard_on_card(_bl_kiwi); _ls_settle()
        app._list_move_by_keyboard(1); _ls_settle()
        app._list_move_by_keyboard(-1); _ls_settle()
    app._hide_toast()
    _bl_sort('Title A–Z')
    app._hide_toast()
    app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
    app._hide_toast()
    del _bl_questions[:]
    _bl_answer[0] = True
    _bl_sort('Custom order')
    _bl_kept_hand.append(
        (_bl_how, len(_bl_questions),
         [i for i in app._card_order() if i in _bl_hand_ids] == _bl_hand_ids))
check(f'...and neither a duplicate nor a new note given its place by '
      f'another card\'s move arranges anything: the arrangement made by hand '
      f'comes back ({_bl_kept_hand})',
      _bl_kept_hand == [('duplicate', 1, True), ('jiggle', 1, True)])
# A known card moved past a new note arranges something -- the new note
# stands where the person put it beside that card -- though the notes the
# last move knew keep their order. Counted only when the new note itself
# was moved, it lost the newest arrangement to the older offer. Moved past
# it and straight back, nothing is arranged, as with any other card.
_bl_past = []
for _bl_how in ('past', 'past and back', 'duplicate, then a jiggle'):
    _co_fresh(_bl_placed, sort='Custom order')
    _bl_sort('Title A–Z')
    app._hide_toast()
    app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
    app._hide_toast()
    if _bl_how == 'duplicate, then a jiggle':
        # A duplicate stands beside its original, mid-list: the record
        # learns it there, so a card moved down and back arranges nothing.
        app.duplicate_note(next(n for n in app.notes
                                if n['title'].startswith('Kiwi')))
        _ls_settle()
        _bl_other = next(i for i in app._card_order()
                         if not app.find_note(i)['title'].startswith('Kiwi'))
        app._put_keyboard_on_card(_bl_other); _ls_settle()
        app._list_move_by_keyboard(1); _ls_settle()
        app._list_move_by_keyboard(-1); _ls_settle()
    else:
        app.new_note()
        app.title_entry.insert(0, 'Golf note')
        app.body_text.insert('1.0', 'a new note')
        app.save_current_note()
        _ls_settle()
        _bl_order = app._card_order()
        _bl_golf = next(n['id'] for n in app.notes
                        if n['title'].startswith('Golf'))
        _bl_under = _bl_order[_bl_order.index(_bl_golf) + 1]
        app._put_keyboard_on_card(_bl_under); _ls_settle()
        app._list_move_by_keyboard(-1); _ls_settle()
        if _bl_how == 'past and back':
            app._list_move_by_keyboard(1); _ls_settle()
    app._hide_toast()
    _bl_made = app._card_order()
    _bl_sort('Title A–Z')
    app._hide_toast()
    app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
    app._list_move_by_keyboard(1); _ls_settle()
    app._hide_toast()
    del _bl_questions[:]
    _bl_answer[0] = True
    _bl_sort('Custom order')
    _bl_back = app._card_order()
    _bl_past.append(
        (_bl_how, len(_bl_questions),
         _bl_back == _bl_made if _bl_how == 'past'
         else [i for i in _bl_back if i in _bl_hand_ids] == _bl_hand_ids))
check(f'...and a card moved past a new note arranges something, the new '
      f'arrangement offered back; moved past it and back, or beside a '
      f'duplicate and back, nothing ({_bl_past})',
      _bl_past == [('past', 1, True), ('past and back', 1, True),
                   ('duplicate, then a jiggle', 1, True)])
# No: the list stays as the replacement left it, and the question does not
# come back.
_bl_sort('Title A–Z')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
_bl_replacement = _bl_names()
app._hide_toast()
_bl_sort('Recently updated')
del _bl_questions[:]
_bl_answer[0] = False
_bl_sort('Custom order')
_bl_no = (len(_bl_questions), _bl_names() == _bl_replacement)
del _bl_questions[:]
_bl_sort('Custom order')
check(f'...while No leaves the list as the move left it and is not asked '
      f'again (asked {_bl_no[0]}, list as the move left it: {_bl_no[1]}; '
      f'asked after: {len(_bl_questions)})',
      _bl_no == (1, True) and not _bl_questions
      and _bl_replacement != _bl_hand)
# An offer the toast's Undo has taken is gone for good. Right after Undo the
# old arrangement IS the list's, so there is nothing to offer -- but here
# the arrangement made by hand is alphabetical, so a later move made while
# sorted Title A–Z replaces nothing, and a stale offer would then try to
# undo that move the next time Custom order is chosen.
_bl_abc = sorted(_bl_fruit)
_co_fresh([dict(n, order=_bl_abc.index(n['title'].split()[0]))
           for n in _bl_placed], sort='Custom order')
_bl_sort('Title Z–A')
app._hide_toast()
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
_qa_click(app.toast_action_lbl); _ls_settle()
_bl_sort('Title A–Z')
app._put_keyboard_on_card(app._card_order()[0]); _ls_settle()
app._list_move_by_keyboard(1); _ls_settle()
_bl_moved = _bl_names()
del _bl_questions[:]
_bl_sort('Custom order')
check(f'...and an offer Undo has taken does not come back over a move made '
      f'since (asked {[q[0] for q in _bl_questions]}; the move kept: '
      f'{_bl_names() == _bl_moved}, {_bl_moved[:3]})',
      not _bl_questions and _bl_names() == _bl_moved
      and _bl_moved[:2] == ['Banana', 'Apple'])
app.ask_yes_no = _ls_real_ask
app._hide_toast()

# 5f. One card wears the open note's outline: the open note's. A new note's
# first save draws its card as the open one, and the outline used to be
# moved only off the card it had last been put on by hand -- so opening
# another note next left two "open" cards, until a full rebuild.


def _bl_outlined():
    """The cards whose ring says "open", read off the drawing -- with the
    keyboard away from the list, where the colour means only that."""
    app._list_focus_out()
    return sorted(n for n in app._card_order()
                  if app._card_view(n)['ring'] == app.colors['accent'])


_co_fresh(_bl_notes[:6])
_bl_o = app._card_order()
app.open_note_in_tab(app.find_note(_bl_o[2])); _ls_settle()
app.open_blank_tab(); _ls_settle()
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'Fresh one')
app.save_current_note(auto=True); _ls_settle()
_bl_new = app.selected_note_id
check(f'fixture: a new note\'s first save outlines its card, and only its '
      f'card ({_bl_outlined()}, new {_bl_new})', _bl_outlined() == [_bl_new])
app._scroll_row_into_view(app._note_cards[_bl_o[4]]); _ls_settle()
_bl_pt = app._card_point(_bl_o[4])
_qa_click(app.canvas, x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
check(f'...and a note clicked open next takes the outline off it: one open '
      f'card, the one open ({_bl_outlined()}, open {app.selected_note_id})',
      app.selected_note_id == _bl_o[4] and _bl_outlined() == [_bl_o[4]])
# Ctrl+N from an open note: the new note's first save moves the outline
# onto it, although nothing moved it off the note before. The note is
# opened without the keyboard, which stays on another card: taking the
# keyboard away repaints ITS card, and on the open one that would hide
# exactly the outline this is about.
app.open_note_in_tab(app.find_note(_bl_o[1])); _ls_settle()
app._shortcut_new_note(); _ls_settle()
# Before that save no note is open, so no card is: new_note() is where
# Ctrl+N, a calendar day's "Add note" and Use template all pass.
check(f'...and Ctrl+N takes the outline off the note it leaves, before the '
      f'new one is saved ({_bl_outlined()}, the note open before {_bl_o[1]})',
      app.selected_note_id is None and _bl_outlined() == [])
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'Made with Ctrl+N')
app.save_current_note(auto=True); _ls_settle()
check(f'...and after Ctrl+N, the new note\'s first save leaves one outline, '
      f'on it ({_bl_outlined()}, open {app.selected_note_id}, the note open '
      f'before {_bl_o[1]}; the keyboard on {app._focused_note_id})',
      _bl_outlined() == [app.selected_note_id]
      and app.selected_note_id not in _bl_o and app._focused_note_id != _bl_o[1])
# Grouped, a new note's first save changes its group's count, so the whole
# list is rebuilt rather than one card redrawn -- and the card is drawn as
# the open one with nothing noting that it was.
app.group_by_category.set(True)
app.refresh_note_list(); _ls_settle()
app.open_note_in_tab(app.find_note(_bl_o[2])); _ls_settle()
app.open_blank_tab(); _ls_settle()
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'Fresh in a group')
app.save_current_note(auto=True); _ls_settle()
app._scroll_row_into_view(app._note_cards[_bl_o[4]]); _ls_settle()
_bl_pt = app._card_point(_bl_o[4])
_qa_click(app.canvas, x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
check(f'...and in a grouped list, where that save rebuilds the list, too '
      f'({_bl_outlined()}, open {app.selected_note_id})',
      app.selected_note_id == _bl_o[4] and _bl_outlined() == [_bl_o[4]])
app.group_by_category.set(False)
app.refresh_note_list(); _ls_settle()

# 5g. Every text on the list stays inside it. A category may be named with
# up to 80 characters, and its header drew name and count as one line with
# no width: the name ran past the list's edge and took the count -- all a
# folded group says about its size -- with it.
_bl_long = "Kids' school forms and permission slips 2026"
_bl_edge = app.LIST_DRAW_WIDTH - app.CARD_INSET_X
NO.CATEGORY_COLORS[_bl_long] = '#f4a261'
_co_fresh([dict(n, category=_bl_long) for n in _bl_notes[:3]]
          + [dict(n, category='General') for n in _bl_notes[3:6]])
app.group_by_category.set(True)
app.collapsed_groups.clear()
app.refresh_note_list(); _ls_settle()


def _bl_header_fits(cat, count):
    rec = app._group_headers.get(cat)
    if rec is None:
        return False, None
    box = app.canvas.bbox(rec['items']['label'])
    text = app.canvas.itemcget(rec['items']['label'], 'text')
    return (box is not None and box[2] <= _bl_edge
            and text.endswith(' (%d)' % count)), (text, box and box[2])


_bl_ok, _bl_seen = _bl_header_fits(_bl_long, 3)
check(f'a header with a long name keeps its count inside the list, the name '
      f'shortened first ({_bl_seen}; the edge is {_bl_edge})', _bl_ok)
# The count changes without a rebuild when a note is deleted from the group.
app.ask_yes_no = lambda *a, **k: True
try:
    app._delete_note(app.find_note(_bl_notes[0]['id']), None); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
_bl_ok, _bl_seen = _bl_header_fits(_bl_long, 2)
check(f'...and so does the count a delete brings down in place ({_bl_seen})',
      _bl_ok)
_bl_short = (app._header_view('General') or {}).get('label')
check(f'...while a name that fits is drawn whole, as before ({_bl_short!r})',
      _bl_short == 'General (3)')
# And the one text the list draws when it has no rows at all.
_ls_search('zzz-no-such-note')
_bl_box = app.canvas.bbox('list_empty')
check(f'...and the empty list\'s message stays inside it too ({_bl_box})',
      _bl_box is not None and _bl_box[2] <= _bl_edge)
_ls_search('')
app.group_by_category.set(False)
NO.CATEGORY_COLORS.pop(_bl_long, None)
app.refresh_note_list(); _ls_settle()

# 5h. The keyboard folds and opens groups. A header is a stop on the ring's
# walk, drawn with the ring as a card is; Enter or Space on it does what a
# click does, Left on a card folds its group and takes the ring to the
# header, Right opens a folded header. Without them a folded group opened
# only to the mouse, and with every group folded -- as a person may leave
# the list -- no key on the list did anything at all. Keys are called as
# their bindings call them (see 4.), and the bindings are asked for too.
_bl_work_colour = NO.CATEGORY_COLORS.get('Work')
NO.CATEGORY_COLORS.setdefault('Work', '#4cc9f0')
_co_fresh([dict(n, category='General') for n in _bl_notes[:2]]
          + [dict(n, category='Work') for n in _bl_notes[2:4]])
_bl_work_ids = [n['id'] for n in _bl_notes[2:4]]
app.group_by_category.set(True)
app.collapsed_groups.clear()
app.collapsed_groups.update({'General', 'Work'})
app.refresh_note_list(); _ls_settle()


def _bl_ring_on_header(cat):
    rec = app._group_headers.get(cat)
    return (rec is not None and app._focused_header == cat
            and app.canvas.itemcget(rec['items']['ring'], 'outline')
            == app.colors['text'])


check(f'fixture: every group folded, nothing but headers on the list '
      f'({app._list_drawn_keys})',
      app._list_drawn_keys == [('header', 'General'), ('header', 'Work')])
app._list_focus_in(); _ls_settle()
check(f'with every group folded, the keyboard arriving puts the ring on the '
      f'first header, drawn as a card\'s is ({app._focused_header!r})',
      _bl_ring_on_header('General'))
app._list_step(1); _ls_settle()
check(f'...Down walks it to the next header ({app._focused_header!r})',
      _bl_ring_on_header('Work'))
app._list_activate(); _ls_settle()
check(f'...Enter on a header opens its group, and the ring stays on the '
      f'header (open groups: {sorted({"General", "Work"} - app.collapsed_groups)})',
      'Work' not in app.collapsed_groups and _bl_ring_on_header('Work'))
app._list_step(1); _ls_settle()
check(f'...Down from the header goes to its first card '
      f'({app._focused_note_id}, header ring off: '
      f'{not _bl_ring_on_header("Work")})',
      app._focused_note_id == (app._card_order() or [None])[0]
      and app._focused_note_id in _bl_work_ids
      and not _bl_ring_on_header('Work'))
app._list_fold_by_keyboard(True); _ls_settle()
check(f'...Left on a card folds its group and takes the ring to its header '
      f'({sorted(app.collapsed_groups)}, ring on {app._focused_header!r})',
      'Work' in app.collapsed_groups and _bl_ring_on_header('Work'))
app._list_fold_by_keyboard(False); _ls_settle()
check(f'...Right on the folded header opens it again '
      f'({sorted(app.collapsed_groups)})',
      'Work' not in app.collapsed_groups and _bl_ring_on_header('Work'))
app._list_fold_by_keyboard(False); _ls_settle()
check('...and Right on an open header leaves it open',
      'Work' not in app.collapsed_groups and _bl_ring_on_header('Work'))
app._list_activate(); _ls_settle()
check('...and Space (the same handler as Enter) folds it again',
      'Work' in app.collapsed_groups and _bl_ring_on_header('Work'))
# To a theme whose text colour differs -- a recolour that repaints the
# same colour would prove nothing.
_bl_theme = app.theme_name
_bl_other = next(t for t, p in NO.THEMES.items()
                 if p.get('text') != app.colors['text'])
app.set_theme(_bl_other); _ls_settle()
_bl_recoloured = _bl_ring_on_header('Work')
app.set_theme(_bl_theme); _ls_settle()
check(f'...the header\'s ring follows a theme switch ({_bl_other})',
      _bl_recoloured and _bl_ring_on_header('Work'))
app._list_focus_out(); _ls_settle()
_bl_hdr = app._group_headers.get('Work')
check('...and the keyboard leaving the list takes the ring off the header',
      _bl_hdr is not None
      and app.canvas.itemcget(_bl_hdr['items']['ring'], 'outline')
      == app.colors['sidebar'])
_bl_bound = set(app.canvas.bind())
check(f'Left and Right are bound on the list '
      f'({sorted(s for s in _bl_bound if "Left" in s or "Right" in s)})',
      '<Key-Left>' in _bl_bound and '<Key-Right>' in _bl_bound)
app.group_by_category.set(False)
app.collapsed_groups.clear()
app.refresh_note_list(); _ls_settle()
if _bl_work_colour is None:
    NO.CATEGORY_COLORS.pop('Work', None)

# The open note's own card, pressed or Enter on it, leaves the note as it is:
# loaded again, it jumped to its top and Ctrl+Z lost all it held.
_co_fresh(_bl_notes)
_oc_id = (app._card_order() or [None])[0]
app.open_note_in_tab(app.find_note(_oc_id)); _ls_settle()


def _oc_can_undo():
    return bool(app.body_text.tk.call(app.body_text._w, 'edit', 'canundo'))


app.body_text.insert('end', ' and a line typed since')
app.body_text.edit_separator()
_oc_typed = _oc_can_undo()
app._put_keyboard_on_card(_oc_id); _ls_settle()
app._list_activate(); _ls_settle()
_oc_enter = _oc_can_undo()
app._list_press_row(app._note_cards[_oc_id], types.SimpleNamespace(x=5, y=5)); _ls_settle()
check(f"the open note's own card, Enter or a press on it, leaves its Undo in place "
      f"({_oc_typed}, {_oc_enter}, {_oc_can_undo()})",
      _oc_typed and _oc_enter and _oc_can_undo())
# ...and so do the Calendar's Open in editor and the menu's Open / Edit, for a
# one-off note on its own date: they asked of the date, not of the note the
# editor opens for it, and loaded it again.
_oc_note = app.find_note(_oc_id)
_oc_note['date'] = '2026-11-05'
app.save_notes()
app.open_note_in_tab(_oc_note); _ls_settle()
app.body_text.insert('end', ' and a line more')
app.body_text.edit_separator()
app._open_note_from_calendar(_oc_note, '2026-11-05'); _ls_settle()
_oc_panel = _oc_can_undo()
app._ctx_open(_oc_note, '2026-11-05'); _ls_settle()
check(f"...and the Calendar's Open in editor and the menu's Open / Edit too "
      f"({_oc_panel}, {_oc_can_undo()})",
      _oc_panel and _oc_can_undo())

# 5i. The ring stays where the person can see it. It could sit on a card
# 900px above the view: Tab brought the keyboard back to a list the wheel
# had scrolled away, Enter then opened a note nobody could see, the menu
# key posted its menu off the screen, and pinning the ringed card from its
# menu sent it to the top while the view stayed put.
_co_fresh(_bl_notes)
_bl_o = app._card_order()
_bl_menus = []


def _bl_seen(nid):
    rec = app._note_cards.get(nid)
    return app._row_on_screen(rec) if rec else 'not drawn'


def _bl_scroll_away(px):
    """The person scrolling the list, while the keyboard is elsewhere or
    still on the list -- the scrollbar's way: a deliberate scroll, which
    beats any restore. A bare yview_moveto stood in for it once, and once
    the list learned to tell the person's scrolls from its own moves
    (5k), that stand-in was the list's own move."""
    app._list_scrollbar_moved('moveto', str(px / float(app._list_extent()[3])))
    _ls_settle()


app._put_keyboard_on_card(_bl_o[0]); _ls_settle()
app._list_focus_out(); _ls_settle()
_bl_scroll_away(700)
_bl_top = app.canvas.canvasy(0)
check(f'fixture: the ring\'s card scrolled out of sight ({_bl_seen(_bl_o[0])}, '
      f'view at {_bl_top:.0f})', _bl_seen(_bl_o[0]) == 'none' and _bl_top > 300)
app._list_focus_in(); _ls_settle()
check(f'Tab into a list scrolled away from the ring puts the ring on a card in '
      f'sight and leaves the view alone (ring on {app._focused_note_id}: '
      f'{_bl_seen(app._focused_note_id)}; view {app.canvas.canvasy(0):.0f})',
      _bl_seen(app._focused_note_id) == 'all'
      and abs(app.canvas.canvasy(0) - _bl_top) < 1
      and app._card_view(_bl_o[0])['ring'] != app.colors['text'])
# The wheel is the person's own scroll as much as the scrollbar is. It is
# bound by the sidebar's _bind_mousewheel_recursive, which has to say so
# through _list_scrolled_by_hand, as the scrollbar does.
app._put_keyboard_on_card(_bl_o[0]); _ls_settle()
app._list_focus_out(); _ls_settle()
for _ in range(15):
    _qa_fire(app.canvas, '<MouseWheel>', delta=-120)
    app.update()
_bl_top = app.canvas.canvasy(0)
_bl_was = _bl_seen(_bl_o[0])
app._list_focus_in(); _ls_settle()
check(f'...and so does one the wheel scrolled away (the ring\'s card was '
      f'{_bl_was}; ring now on {app._focused_note_id}: '
      f'{_bl_seen(app._focused_note_id)}; view {app.canvas.canvasy(0):.0f}, '
      f'left at {_bl_top:.0f})',
      _bl_was == 'none' and app._focused_note_id != _bl_o[0]
      and _bl_seen(app._focused_note_id) == 'all'
      and abs(app.canvas.canvasy(0) - _bl_top) < 1)
# Half in sight: it stays on its card, and the card comes into view.
_bl_v = app._card_view(_bl_o[5])
app._put_keyboard_on_card(_bl_o[5]); _ls_settle()
app._list_focus_out(); _ls_settle()
_bl_scroll_away(_bl_v['y0'] + 30)
_bl_was = _bl_seen(_bl_o[5])
app._list_focus_in(); _ls_settle()
check(f'...and a ring half in sight stays on its card, which comes into view '
      f'(was {_bl_was}, now {_bl_seen(_bl_o[5])}; ring on {app._focused_note_id})',
      _bl_was == 'part' and _bl_seen(_bl_o[5]) == 'all'
      and app._focused_note_id == _bl_o[5])
# The keys that act on the ring bring it back first, when the wheel has
# scrolled it away while the keyboard stayed on the list.
app.show_note_context_menu = lambda ev, note, **k: _bl_menus.append(
    (ev.y_root, note['id']))
try:
    app._put_keyboard_on_card(_bl_o[1]); _ls_settle()
    _bl_scroll_away(700)
    _bl_was = _bl_seen(_bl_o[1])
    app._list_open_menu(); _ls_settle()
finally:
    app.__dict__.pop('show_note_context_menu', None)
_bl_lo = app.canvas.winfo_rooty()
_bl_hi = _bl_lo + app.canvas.winfo_height()
check(f'the menu key on a ring scrolled out of sight opens the note\'s menu at '
      f'its card, in view ({_bl_menus}; card {_bl_seen(_bl_o[1])}, was '
      f'{_bl_was}; the list spans {_bl_lo}-{_bl_hi})',
      _bl_was == 'none' and len(_bl_menus) == 1 and _bl_menus[0][1] == _bl_o[1]
      and _bl_lo <= _bl_menus[0][0] <= _bl_hi and _bl_seen(_bl_o[1]) == 'all')
app._put_keyboard_on_card(_bl_o[2]); _ls_settle()
_bl_scroll_away(700)
app._list_activate(); _ls_settle()
check(f'...and Enter on it opens the note with its card in view (open '
      f'{app.selected_note_id}, card {_bl_seen(_bl_o[2])})',
      app.selected_note_id == _bl_o[2] and _bl_seen(_bl_o[2]) == 'all')
# A rebuild that moves the ringed card out of sight: pinned from its menu,
# the card goes to the top, and the view goes with it.
_bl_scroll_away(500)
_bl_mid = next(n for n in _bl_o if _bl_seen(n) == 'all')
app._put_keyboard_on_card(_bl_mid); _ls_settle()
# The keyboard on the list, as <FocusIn> records it -- the ring is only
# shown, and only followed, while it is (qa/README on focus).
app._list_focus_in(); _ls_settle()
_bl_kb = app._keyboard_on_card
app.toggle_pin(app.find_note(_bl_mid)); _ls_settle()
_ls_let_restores_finish()
check(f'pinning the ringed card from its menu keeps the ring in sight '
      f'(keyboard on the list: {_bl_kb}; card first: '
      f'{app._card_order()[:1] == [_bl_mid]}; {_bl_seen(_bl_mid)}; view '
      f'{app.canvas.canvasy(0):.0f})',
      _bl_kb and app._card_order()[:1] == [_bl_mid]
      and _bl_seen(_bl_mid) == 'all' and app._focused_note_id == _bl_mid)
app.toggle_pin(app.find_note(_bl_mid)); _ls_settle()
# The menu's place is kept to the list even for a card taller than the
# view, which no scroll can show whole: the smallest window, a full card,
# its top scrolled out of sight -- brought back into view top first, its
# bottom (where the menu opens) is below the list.
app.geometry('1100x600'); _ls_settle()
_bl_tall = {'id': 1990, 'title': 'A title long enough to wrap over two lines',
            'body': 'x ' * 40, 'category': 'General', 'comments': 'c',
            'date': '2026-09-01', 'created': '2026-01-01 00:00',
            'updated': '2026-02-01 00:00',
            'recurrence': {'freq': 'weekly', 'interval': 1, 'weekdays': [],
                           'end': ''},
            'checklist': [{'text': 'a', 'done': True}, {'text': 'b', 'done': False}],
            'attachments': [{'filename': 'f.txt', 'stored_as': 'f.txt'}]}
_co_fresh([_bl_tall] + _bl_notes[:3])
_bl_card = app._card_view(1990)
_bl_view_h = app.canvas.winfo_height()
app._put_keyboard_on_card(1990); _ls_settle()
_bl_scroll_away(_bl_card['y0'] + 30)
_bl_cut = app.canvas.canvasy(0) > _bl_card['y0']
_bl_menus = []
app.show_note_context_menu = lambda ev, note, **k: _bl_menus.append(
    (ev.y_root, note['id']))
try:
    app._list_open_menu(); _ls_settle()
finally:
    app.__dict__.pop('show_note_context_menu', None)
_bl_lo = app.canvas.winfo_rooty()
_bl_hi = _bl_lo + app.canvas.winfo_height()
check(f'...and a card taller than the view still gets its menu inside the '
      f'list (card {_bl_card["y1"] - _bl_card["y0"]}px in a {_bl_view_h}px '
      f'view, its top cut off: {_bl_cut}; menu at {_bl_menus}, the list '
      f'spans {_bl_lo}-{_bl_hi})',
      _bl_card['y1'] - _bl_card['y0'] > _bl_view_h and _bl_cut
      and len(_bl_menus) == 1 and _bl_lo <= _bl_menus[0][0] <= _bl_hi)
app.geometry('1100x850'); _ls_settle()

# 5k. ...but the LIST moving the ring's card away is not the person
# scrolling away from it. With the keyboard elsewhere, a save takes the card
# to the top of a list sorted by date, a search keystroke filters away the
# notes above it -- and the keyboard coming back gave the ring to the first
# card in view: another note, which Enter then opened instead of the one
# being edited. The ring stays on its card, and the card comes into view.
_bl_alpha = [{'id': 2000 + i, 'title': 'Alpha %02d' % i,
              'body': 'b %d' % i + (' zeta' if i >= 15 else ''),
              'category': 'General', 'created': '2026-01-01 00:00',
              'updated': '2026-02-01 00:%02d' % (59 - i)} for i in range(40)]
_co_fresh(_bl_alpha)
_bl_scroll_away(app._card_view(2017)['y0'] - 20)
_bl_pt = app._card_point(2017)
_qa_click(app.canvas, x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
# A small scroll of the person's own that leaves the card in sight: the
# keyboard arriving after it finds the ring where it was, and from then on
# that scroll no longer counts as having scrolled away from it.
_bl_scroll_away(app.canvas.canvasy(0) + 10)
app._list_focus_in(); _ls_settle()
_ls_let_restores_finish()
_bl_opened = (app.selected_note_id, app._focused_note_id, _bl_seen(2017))
# Into the editor, and typing there saves: the card goes to the top.
app._list_focus_out(); _ls_settle()
app.body_text.insert('end', ' typed')
app.save_current_note(auto=True); _ls_settle()
_ls_let_restores_finish()
_bl_away = (app._card_order()[:1] == [2017], _bl_seen(2017))
check(f'fixture: a card clicked deep in the list goes to the top, out of '
      f'sight, when its note is saved from the editor (opened, ring, seen: '
      f'{_bl_opened}; first, seen: {_bl_away})',
      _bl_opened == (2017, 2017, 'all') and _bl_away == (True, 'none'))
app._list_focus_in(); _ls_settle()
_bl_back = (app._focused_note_id, _bl_seen(2017),
            app._card_view(2017)['ring'] == app.colors['text'])
app._list_activate(); _ls_settle()
check(f'the keyboard coming back after a save took its card out of sight '
      f'puts the ring back on that card, in view (ring, seen, drawn: '
      f'{_bl_back}) -- so Enter opens the note being edited (open '
      f'{app.selected_note_id})',
      _bl_back == (2017, 'all', True) and app.selected_note_id == 2017)
# A wheel turn that leaves the card in sight is no scroll away from it.
# Every notch said it was -- even one that moved nothing -- and after a
# save took the card away, the ring went to another note.
_co_fresh(_bl_alpha)
_bl_scroll_away(app._card_view(2017)['y0'] - 20)
_bl_pt = app._card_point(2017)
_qa_click(app.canvas, x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
_ls_let_restores_finish()
app._list_focus_out(); _ls_settle()
for _bl_d in (-120, 120):
    _qa_fire(app.canvas, '<MouseWheel>', delta=_bl_d)
    app.update()
_ls_settle()
_bl_wheel_seen = (app.selected_note_id, _bl_seen(2017))
app.body_text.insert('end', ' typed')
app.save_current_note(auto=True); _ls_settle()
_ls_let_restores_finish()
_bl_away = (app._card_order()[:1] == [2017], _bl_seen(2017))
app._list_focus_in(); _ls_settle()
check(f'...and so it does after a wheel turn that left the card in sight '
      f'(open, seen after the wheel: {_bl_wheel_seen}; first, seen after the '
      f'save: {_bl_away}; ring now on {app._focused_note_id}: '
      f'{_bl_seen(app._focused_note_id)})',
      _bl_wheel_seen == (2017, 'all') and _bl_away == (True, 'none')
      and app._focused_note_id == 2017 and _bl_seen(2017) == 'all')
# A wheel turn made while the ring's card is not drawn at all -- a save
# carried it below the rows the list drew -- is the person scrolling away
# from it too. It was not noted, and the keyboard's return drew every row
# down to the card and pulled the view there.
_bl_many = [{'id': 3000 + i, 'title': 'Many %03d' % i, 'body': 'b',
             'category': 'General', 'created': '2026-01-01 00:00',
             'updated': '2026-02-01 %02d:%02d' % (i // 60, i % 60)}
            for i in range(120)]
_co_fresh(_bl_many, sort='Oldest updated')
_bl_nid = app._card_order()[4]
_bl_pt = app._card_point(_bl_nid)
_qa_click(app.canvas, x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
_qa_fire(app.canvas, '<ButtonRelease-1>', x=_bl_pt[0], y=_bl_pt[1]); _ls_settle()
_ls_let_restores_finish()
app._list_focus_out(); _ls_settle()
app.body_text.insert('end', ' typed')
app.save_current_note(auto=True); _ls_settle()
_ls_let_restores_finish()
_bl_undrawn = _bl_seen(_bl_nid)
for _bl_d in (-120, -120):
    _qa_fire(app.canvas, '<MouseWheel>', delta=_bl_d)
    app.update()
_ls_settle()
_bl_top = app.canvas.canvasy(0)
app._list_focus_in(); _ls_settle()
check(f'...while a wheel turn made with the ring\'s card not drawn leaves the '
      f'view where the person put it, the ring on a card in sight (the card '
      f'was {_bl_undrawn}; view {_bl_top:.0f} -> {app.canvas.canvasy(0):.0f}; '
      f'ring on {app._focused_note_id}: {_bl_seen(app._focused_note_id)})',
      _bl_undrawn == 'not drawn' and _bl_top > 0
      and abs(app.canvas.canvasy(0) - _bl_top) < 1
      and app._focused_note_id != _bl_nid
      and _bl_seen(app._focused_note_id) == 'all')
# A search: its results start from the top, and the card, far down them,
# is out of sight. (A search once kept the view, and the notes filtered
# away above the card took it out of sight instead.)
_co_fresh(_bl_alpha)
_ls_scroll_to_end()
app._put_keyboard_on_card(2037); _ls_settle()
app._list_focus_in(); _ls_settle()
app._list_focus_out(); _ls_settle()
_ls_search('zeta'); _ls_let_restores_finish()
_bl_away = (round(app.canvas.canvasy(0)), _bl_seen(2037))
app._list_focus_in(); _ls_settle()
check(f'...and after a search, which starts its results from the top, left '
      f'the card far below them (view, card: {_bl_away}; ring on '
      f'{app._focused_note_id}: {_bl_seen(app._focused_note_id)})',
      _bl_away[0] == 0 and _bl_away[1] in ('none', 'not drawn')
      and app._focused_note_id == 2037 and _bl_seen(2037) == 'all')
app._list_focus_out(); _ls_settle()
_ls_search('')
# A sort chosen meanwhile can take the card past what the rebuild drew: a
# list rebuilt while the keyboard is elsewhere draws what the view needs.
_co_fresh(_bl_alpha)
app._put_keyboard_on_card(2005); _ls_settle()
app._list_focus_in(); _ls_settle()
app._list_focus_out(); _ls_settle()
_bl_sort('Oldest updated')
_bl_drawn = 2005 in app._note_cards
app._list_focus_in(); _ls_settle()
check(f'...and after a sort chosen meanwhile took it past what the list had '
      f'drawn (drawn before: {_bl_drawn}; ring on {app._focused_note_id}: '
      f'{_bl_seen(app._focused_note_id)})',
      not _bl_drawn and app._focused_note_id == 2005
      and _bl_seen(2005) == 'all')
app._list_focus_out(); _ls_settle()
app.sort_var.set('Recently updated')

# 5j. The list stays quick however far it has been scrolled, and whatever
# is typed. Asked of the WORK done, never of a stopwatch (qa/README): a
# canvas finds a tag by walking every item it holds, so closing the gap a
# delete left by moving each row by its own tag cost rows times items -- 2.6 s
# in a list drawn to the end of 5,000 notes; and every rebuild scanned the
# whole notebook's text to find that an empty search matches everything.
_bl_many = [{'id': 2100 + i, 'title': 'Quick %03d' % i, 'body': 'b %d' % i,
             'category': 'General', 'created': '2026-01-01 00:00',
             'updated': '2026-02-%02d 00:%02d' % (1 + i // 60, i % 60)}
            for i in range(120)]
_co_fresh(_bl_many)
_ls_scroll_to_end()
_bl_moves = []
_bl_real_move = app.canvas.move
app.canvas.move = lambda *a: (_bl_moves.append(a[0]), _bl_real_move(*a))[1]
_bl_o = app._card_order()
app.ask_yes_no = lambda *a, **k: True
try:
    app._delete_note(app.find_note(_bl_o[3]), None); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
    app.canvas.__dict__.pop('move', None)
check(f'a delete in a list drawn to its end closes the gap with one move of '
      f'the rows below, not one per row ({len(_bl_moves)} canvas moves for '
      f'{len(_bl_o) - 4} rows)',
      len(_bl_o) == 120 and 1 <= len(_bl_moves) <= 2
      and _ls_same_as_rebuild())
# A save that takes a card from far down to the top slides every row above
# its old place -- one band too.
_ls_scroll_to_end()
_bl_o = app._card_order()
app.open_note_in_tab(app.find_note(_bl_o[100])); _ls_settle()
app.body_text.insert('end', ' moved up')
_bl_moves = []
app.canvas.move = lambda *a: (_bl_moves.append(a[0]), _bl_real_move(*a))[1]
try:
    app.save_current_note(auto=True); _ls_settle()
finally:
    app.canvas.__dict__.pop('move', None)
check(f'...and a save that takes a card from the 101st place to the top slides '
      f'the hundred above it with one move ({len(_bl_moves)} canvas moves; '
      f'now first: {app._card_order()[:1] == [_bl_o[100]]})',
      app._card_order()[:1] == [_bl_o[100]] and 1 <= len(_bl_moves) <= 2
      and _ls_same_as_rebuild())
# The band is trusted only if it holds exactly its rows' items: anything
# else inside it -- an item the list never drew -- sends those rows back to
# moving one by one, and the stranger stays where it was.
_ls_scroll_to_end()
_bl_o = app._card_order()
_bl_v = app._card_view(_bl_o[60])
_bl_stranger = app.canvas.create_rectangle(
    100, _bl_v['y0'] + 10, 110, _bl_v['y0'] + 20, outline='')
app.ask_yes_no = lambda *a, **k: True
try:
    app._delete_note(app.find_note(_bl_o[2]), None); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
_bl_where = app.canvas.coords(_bl_stranger)
app.canvas.delete(_bl_stranger)
check(f'...and a band holding an item the list never drew moves its rows one '
      f'by one, leaving that item where it was ({_bl_where[1]:.0f}, was '
      f'{_bl_v["y0"] + 10:.0f}; every card where its record is: '
      f'{_bl_drawing_ok()})',
      abs(_bl_where[1] - (_bl_v['y0'] + 10)) < 0.5 and _bl_drawing_ok())
# In Select mode every unticked card's tick mark is drawn HIDDEN, and Tk's
# search for what lies inside a band skips hidden items: each band came up
# short and moved its rows one by one (4.7 s for a delete at 5,000 notes).
# One card ticked, so the band holds both kinds of mark.
app._toggle_selection_mode(); _ls_settle()
_ls_scroll_to_end()
_bl_o = app._card_order()
app._toggle_note_selected(_bl_o[40], True)
app._paint_card_check(_bl_o[40])


def _bl_marks_stray():
    """The cards whose tick box or mark is not inside the card -- shown or
    hidden, a mark left behind by a move shows here."""
    bad = []
    for rec in app._list_drawn:
        it = rec['items']
        for key in ('check', 'mark'):
            if key not in it:
                continue
            ys = app.canvas.coords(it[key])[1::2]
            if not ys or min(ys) < rec['y0'] or max(ys) > rec['y1']:
                bad.append((rec['note']['id'], key))
    return bad


_bl_moves = []
app.canvas.move = lambda *a: (_bl_moves.append(a[0]), _bl_real_move(*a))[1]
app.ask_yes_no = lambda *a, **k: True
try:
    app._delete_note(app.find_note(_bl_o[3]), None); _ls_settle()
finally:
    app.ask_yes_no = _ls_real_ask
    app.canvas.__dict__.pop('move', None)
_bl_stray = _bl_marks_stray()
_bl_ticked = app._card_view(_bl_o[40])['checked']
check(f'...and in Select mode too, the unticked cards\' hidden tick marks '
      f'travelling with their cards ({len(_bl_moves)} canvas moves for '
      f'{len(_bl_o) - 4} rows; marks out of their cards: {_bl_stray[:4]}; '
      f'the ticked card still ticked: {_bl_ticked})',
      1 <= len(_bl_moves) <= 2 and not _bl_stray and _bl_ticked
      and _bl_drawing_ok() and not app.canvas.find_withtag('reflow0'))
app._toggle_selection_mode(); _ls_settle()
# The search: nothing typed reads no note's text; a first search reads each
# note's once, the next keystroke none; a note saved since is read again.
_bl_reads = []
_bl_asked = []
_bl_real_texts = app._search_texts
_bl_real_cached = app._cached_search_texts
app._search_texts = lambda note: (_bl_reads.append(note['id']),
                                  _bl_real_texts(note))[1]
# The cache is asked too: a note read before this check (the fixture's own
# rebuilds) answers from it, and would hide an empty query that still walked
# every note.
app._cached_search_texts = lambda note: (_bl_asked.append(note['id']),
                                         _bl_real_cached(note))[1]
try:
    _ls_search('')
    _bl_empty = len(_bl_reads) + len(_bl_asked)
    del _bl_reads[:]
    _ls_search('quick 0')
    _bl_first = len(_bl_reads)
    del _bl_reads[:]
    _ls_search('quick 00')
    _bl_again = len(_bl_reads)
    _bl_found = sorted(app._card_order())
    _bl_note = app.find_note(_bl_many[50]['id'])
    app.open_note_in_tab(_bl_note); _ls_settle()
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'Quick 00x renamed')
    # Counted across the save AND the next search: with a search active,
    # the save's own one-card redraw is what reads the note again.
    del _bl_reads[:]
    app.save_current_note(auto=True); _ls_settle()
    _ls_search('quick 00x')
    _bl_after_save = list(_bl_reads)
    _bl_found_saved = app._card_order()
finally:
    app.__dict__.pop('_search_texts', None)
    app.__dict__.pop('_cached_search_texts', None)
    _ls_search('')
check(f'a rebuild with nothing typed reads no note\'s text, nor asks the cache '
      f'for any ({_bl_empty} read or asked)', _bl_empty == 0)
check(f'...a first search reads each note\'s text once, the next keystroke '
      f'none ({_bl_first} then {_bl_again} of {len(app.notes)}; found '
      f'{len(_bl_found)})',
      _bl_first == len(app.notes) and _bl_again == 0
      and _bl_found == sorted(2100 + i for i in range(10)))
check(f'...and a note saved since is read again -- it alone -- and found by '
      f'its new words (read {_bl_after_save}; found {_bl_found_saved})',
      _bl_after_save == [_bl_note['id']]
      and _bl_found_saved == [_bl_note['id']])

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
        # A box that draws its own well and mark (indicatoron off) is judged
        # on its pixels below, on every theme; its selectcolor matches the
        # surface on purpose, so ticking it does not flood the words.
        if str(widget.cget('indicatoron')) in ('0', 'false', 'False'):
            continue
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

# ...and a tick box's MARK, on every theme, judged on what a person sees.
# Tk paints a box's mark in the box's text colour. The Share and Duplicates
# boxes carry light words on a dark theme, so their mark was light on the
# light well, and a ticked box looked empty (field-reported: "the tick
# doesn't work in dark mode"). The rule above held boxes only to "the well
# is light". A box with words now draws its own box; either way, the mark
# a person sees must stand apart from the well it sits in.


def _seen_tick(box):
    """(well, mark) luminance of a ticked box as it is drawn."""
    def lum(r, g, b):
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    if str(box.cget('indicatoron')) in ('0', 'false', 'False'):
        image = str(box.cget('selectimage'))
        if not image:
            return None
        size = int(app.tk.call(image, 'cget', '-height'))
        pixels = [tuple(int(v) / 255.0 for v in app.tk.splitlist(
            app.tk.call(image, 'get', x, y))[:3])
            for x in range(1, size - 1) for y in range(1, size - 1)]
        well = lum(*pixels[0])
        return well, min(lum(*p) for p in pixels)
    well = lum(*(v / 65535.0 for v in box.winfo_rgb(box.cget('selectcolor'))))
    return well, lum(*(v / 65535.0 for v in box.winfo_rgb(box.cget('fg'))))


app.notes = [NO.normalize_note({'id': 990 + i, 'title': 'Twin', 'body': 'same',
                                'category': 'General'}) for i in range(2)]
app.save_notes()
app.refresh_note_list()
app.update()
_tk_lost, _tk_seen = [], set()
_tk_before = app.theme_name
def _judge_ticks(theme):
    for box in _every_toggle(app):
        if isinstance(box, tk.Radiobutton) or not box.winfo_ismapped():
            continue
        _tk_seen.add(str(box.cget('text')).split('   ')[0])
        judged = _seen_tick(box)
        if judged is None or abs(judged[0] - judged[1]) < 0.5:
            _tk_lost.append('%s/%s' % (theme, box.cget('text')))


for _tk_theme in NO.THEMES:
    app.set_theme(_tk_theme)
    app.update()
    # Opened each round: Settings, visited below, puts the find bar away.
    app._shortcut_find()
    app.update()
    app.toggle_share_panel()          # built now, in this theme
    app.update()
    _judge_ticks(_tk_theme)           # Share, Group by category, Aa
    app.show_settings_page()
    app.toggle_settings_panel('duplicates')
    app.update()
    _judge_ticks(_tk_theme)           # Duplicates
    app.hide_settings_page()
    app.toggle_share_panel()
    app.update()
app.set_theme(_tk_before)
app.update()
check('the boxes judged include Share, Duplicates, Group by category and '
      'Aa (%s)' % sorted(_tk_seen),
      {'Twin', 'Delete this copy', 'Group by category', 'Aa'} <= _tk_seen)
check('on every theme, a ticked box\'s mark stands out from its well '
      '(%s)' % (', '.join(sorted(set(_tk_lost))[:6]) or 'every box, every theme'),
      not _tk_lost)

# The theme switched WHILE Share and Duplicates are open: neither panel is
# rebuilt, and a ticked box's fill kept the old theme's surface, its words
# unreadable on it (audit). Each box must wear the new theme's colours.
app.set_theme(list(NO.DARK_THEMES)[0])
app.update()
app.toggle_share_panel()
app.show_settings_page()
app.toggle_settings_panel('duplicates')
app.update()
_tw_boxes = [b for b in _every_toggle(app)
             if str(b.cget('text')).split('   ')[0] in ('Twin', 'Delete this copy')
             and str(b.cget('indicatoron')) in ('0', 'false', 'False')]
for _tw_b in _tw_boxes:
    _tw_b.select()
app.set_theme(list(NO.LIGHT_THEMES)[0])
app.update()
_tw_wrong = [str(b.cget('text'))[:20] for b in _tw_boxes
             if str(b.cget('selectcolor')).lower() != app.colors['sidebar'].lower()
             or str(b.cget('fg')).lower() != app.colors['text'].lower()]
check(f'a ticked box in an open panel takes the new theme when it switches '
      f'({len(_tw_boxes)} boxes; wrong: {_tw_wrong})',
      len(_tw_boxes) >= 2 and not _tw_wrong)
# The Share panel's search box, in the same open panel: its caret and its
# ✕'s pressed colours are not bg/fg, so the straggler pass lays them only
# because the widgets name them (palette_keys).
_tw_entry = getattr(app, 'share_search_entry', None)
_tw_clear = getattr(app, 'share_search_clear', None)
check(f'the Share search box takes the new theme too, caret and ✕ '
      f'({_tw_entry.cget("insertbackground") if _tw_entry else None})',
      _tw_entry is not None and _tw_clear is not None
      and str(_tw_entry.cget('insertbackground')).lower()
      == app.colors['text'].lower()
      and str(_tw_entry.cget('bg')).lower() == app.colors['card'].lower()
      and str(_tw_clear.cget('activebackground')).lower()
      == app.colors['card'].lower()
      and str(_tw_clear.cget('activeforeground')).lower()
      == app.colors['text'].lower())
for _tw_b in _tw_boxes:
    _tw_b.deselect()
app.hide_settings_page()
app.toggle_share_panel()
app.set_theme(_tk_before)
app.update()
app._close_find()
app.update()

app.hide_settings_page()
app.update()
if app.selection_mode:
    app._toggle_selection_mode()
app.notes = []
app.save_notes()
app.new_note()
app.update()

# ---- A THEME SWITCH SAVES NOTHING, AND A SAVE THAT STORED NOTHING SAYS NOTHING ----
# Field-reported: a green "Note updated" after every theme change. The switch
# repainted the repeat panel through the function that also refreshes the
# repeat's summary, which schedules a save; and a save that could only leave
# an unreadable date out toasted before learning it had stored nothing.
_ts_toasts = []
app._show_toast = lambda text, *a, **k: _ts_toasts.append(text)
app.notes = [
    NO.normalize_note({'id': 7001, 'title': 'Plain', 'body': 'words'}),
    NO.normalize_note({'id': 7002, 'title': 'Table',
                       'body': 'Intro\n| a | b |\n| c | d |'}),
    NO.normalize_note({'id': 7003, 'title': 'Dated', 'body': 'x',
                       'date': '2026-10-20'})]
app.save_notes()
app.refresh_note_list()
_ts_scheduled, _ts_said, _ts_restamped = [], [], []
for _ts_note in list(app.notes):
    app.open_note_in_tab(_ts_note)
    app.update()
    for _ts_job in _qa_waiting(app, '_autosave_now'):
        app.after_cancel(_ts_job)        # the open's own business, not the switch's
    _ts_stamp = _ts_note['updated']
    del _ts_toasts[:]
    app.toggle_theme()
    app.update()
    if _qa_waiting(app, '_autosave_now'):
        _ts_scheduled.append(_ts_note['title'])
    _ts_end = time.time() + 0.8
    while time.time() < _ts_end:
        app.update()
        time.sleep(0.02)
    if _ts_toasts:
        _ts_said.append(_ts_note['title'])
    if app.find_note(_ts_note['id'])['updated'] != _ts_stamp:
        _ts_restamped.append(_ts_note['title'])
check('a theme switch schedules no save, on a plain note, a table and a dated '
      'note (%s)' % (_ts_scheduled or 'none'), not _ts_scheduled)
check('...and nothing says "Note updated", nor does any note look newly '
      'edited (%s / %s)' % (_ts_said or 'quiet', _ts_restamped or 'untouched'),
      not _ts_said and not _ts_restamped)
app.open_note_in_tab(app.find_note(7001))
app.update()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '31/09/2026')   # a day that does not exist
del _ts_toasts[:]
app._autosave_now()
app.update()
check('an autosave that can only leave an unreadable date out says no '
      '"Note updated" (%s)' % (_ts_toasts or 'quiet'), not _ts_toasts)
app.body_text.insert('end', ' and more')
app._autosave_now()
app.update()
check('...while a real edit beside it still does (%s)' % _ts_toasts,
      _ts_toasts == ['Note updated'])
del app._show_toast
app.date_entry.delete(0, 'end')
app.notes = []
app.save_notes()
app.new_note()
app.update()


print()
print(f"=== QA4 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
