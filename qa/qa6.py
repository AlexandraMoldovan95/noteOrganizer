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
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         leaves_nothing_behind as _qa_leaves_nothing_behind,
                         out_of_sight as _qa_out_of_sight,
                         pin_popup_visibility as _qa_pin)
_qa_pin(NO)
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.geometry('1100x850'); app.update()

def find_widget(w, cls, text_contains=None):
    for c in w.winfo_children():
        if isinstance(c, cls):
            if text_contains is None or text_contains in str(c.cget('text')):
                return c
        r = find_widget(c, cls, text_contains)
        if r: return r
    return None

# ---- GROUPING ----
app.notes = [
    {'id':1,'title':'A','body':'x','category':'Work','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
    {'id':2,'title':'B','body':'x','category':'Personal','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
]
NO.CATEGORY_COLORS.setdefault('Work', '#7c5cff')
NO.CATEGORY_COLORS.setdefault('Personal', '#4cafef')

app.group_by_category.set(True)
app._on_toggle_group_by_category()
app.refresh_note_list()
app.update()
check('grouping enabled shows category headers', bool(app._group_headers))

# collapse a group and verify state
app._toggle_group_collapsed('Work')
check('collapsing a group records it', 'Work' in app.collapsed_groups)
app._toggle_group_collapsed('Work')
check('expanding a group removes it from collapsed set', 'Work' not in app.collapsed_groups)

# collapse persists across a settings save/reload
app._toggle_group_collapsed('Personal')
saved = NO.load_settings()
check('collapsed group persisted to settings.json', 'Personal' in saved.get('collapsed_groups', []))

# search + grouping together
app.search_var.set('A')
app.update()
check('search narrows list while grouping stays on', app.group_by_category.get() is True)
app.search_var.set('')
app.group_by_category.set(False)
app._on_toggle_group_by_category()
app.refresh_note_list()
app.update()

# ---- SETTINGS: username greeting ----
# The REAL variable, not a replacement: assigning a fresh StringVar
# here detached the attribute from the entry built at startup, and the
# KeyRelease-correction checks below then talked to a variable no
# widget was listening to.
app.username_var.set('Alexandra')
app.save_username('Alexandra')
app._refresh_greeting()
app.update()
check('greeting shows the saved name', app.greeting_lbl.cget('text') == 'Hi Alexandra,')

app.save_username('')
app._refresh_greeting()
app.update()
check('greeting disappears when name is cleared', app.greeting_lbl.cget('text') == '')

app.save_username('Alexandra')  # restore for later checks
app._refresh_greeting()

# ---- SETTINGS: username length cap (regression) ----
# The per-keystroke validation alone isn't fully reliable under rapid/
# held-down typing (a known Tk limitation), so there are two independent
# safety nets: an immediate correction on every KeyRelease (so it doesn't
# wait for a save to fix an over-length value), and a save-time truncation
# as a final backstop. Both are tested directly here by forcing the value
# over the limit the way a validation bypass would.
app.show_settings_page()
app.update()
# THE username entry, found by its variable -- 'the first Entry on the
# page' silently became a different field once the tests stopped
# inheriting a real settings file (hermetic seed) and the page rendered
# its fresh-install state.
# The 'name' section first: Settings shows exactly one section at a
# time and a section's widgets only exist while it is the one showing.
# On the pre-hermetic runs an inherited real settings file happened to
# leave the right section up; a fresh install does not.
app.toggle_settings_panel('name')
app.update()
name_entry = None
_stack6 = [app]
while _stack6:
    _w6 = _stack6.pop()
    if (isinstance(_w6, tk.Entry)
            and str(_w6.cget('textvariable')) == str(app.username_var)):
        name_entry = _w6
        break
    _stack6.extend(_w6.winfo_children())
# Synthetic KEY events follow FOCUS; under a busy desktop focus_set is
# silently refused and the KeyRelease lands elsewhere. Insist.
for _try6 in range(40):
    name_entry.focus_force()
    app.update()
    try:
        if app.focus_get() is name_entry:
            break
    except (KeyError, tk.TclError):
        pass

app.username_var.set('3' * 70)
name_entry.event_generate('<KeyRelease>')
app.update()
check('a single KeyRelease immediately corrects an over-length value, '
      'without waiting for a save', len(app.username_var.get()) == 30)

# A paste past the 30 is shortened to fit and said, as in every limited box:
# its own check refused it whole, without a word (the final audit's eleventh round).
app.username_var.set('Ana ')
name_entry.icursor('end')
_yn_told = []
_yn_real_status = app.set_status
app.set_status = lambda text, *a, **k: _yn_told.append(text)
try:
    app.clipboard_clear()
    app.clipboard_append('Maria-Magdalena Popescu-Ionescu de la Vale')
    _qa_fire(name_entry, '<<Paste>>')
    app.update()
finally:
    app.set_status = _yn_real_status
    app._hide_toast()
check(f"a paste into Your name past its 30 characters is shortened to fit, and said "
      f"({app.username_var.get()!r}; {_yn_told})",
      app.username_var.get() == ('Ana Maria-Magdalena Popescu-Ionescu de la Vale')[:30]
      and 'Pasted text shortened: your name can be up to 30 characters' in _yn_told)

app.username_var.set('2' * 70)
name_entry.event_generate('<Return>')
app.update()
check('over-length name gets truncated to 30 chars on save',
      len(app.username_var.get()) == 30)
check('truncated name is what gets persisted',
      len(NO.load_settings().get('username', '')) == 30)
check('greeting reflects the truncated name, not the original 70 chars',
      len(app.greeting_lbl.cget('text')) < 40)

# ---- SETTINGS + THEME SWITCH + CLICKS: NO CALLBACK ERRORS ----
# Flipping themes rebuilds settings widgets; a click that still named a
# destroyed widget crashed the focus-clearing handler ('something went
# wrong', intermittent). The whole flow must stay silent.
_theme_before6 = app.theme_name
_errs6 = []
_origRep6 = app.report_callback_exception
app.report_callback_exception = lambda *a, **k: _errs6.append(1)
name_entry.focus_force()
app.update()
app.set_theme('light' if 'dark' in str(app.theme_name) else 'dark')
app.update()
for _xy6 in ((200, 200), (400, 300), (60, 60)):
    _qa_fire(app, '<Button-1>', x=_xy6[0], y=_xy6[1])
    app.update()
app.set_theme(_theme_before6)
app.update()
app.report_callback_exception = _origRep6
check('settings + theme flip + stray clicks raise nothing', not _errs6)

# ---- SETTINGS: clicking elsewhere on the page clears field focus (regression) ----
# Previously, clicking a non-interactive part of the Settings page (a
# section title, card background) left whatever field was focused — e.g.
# the username entry — still showing a blinking cursor, even though the
# value had already autosaved. Switching tabs and back already cleared it
# correctly; this is specifically the same-page click case.
def _focus_settles_on(widget, cap_s=2.0):
    """Focus under Windows lands asynchronously — a bare focus_set +
    update read the OLD focus now and then (a 1-in-3 flake, solo runs
    included). Promised-state wait: poll until the widget HOLDS focus,
    hard-capped so a real regression still fails red."""
    t0 = time.time()
    while time.time() - t0 < cap_s:
        try:
            if app.focus_get() is widget:
                return True
        except (KeyError, tk.TclError):
            pass
        app.update()
        time.sleep(0.02)
    return False

def _take_focus(widget, cap_s=2.0):
    """FORCE focus onto a widget and wait until Tk agrees -- for a
    PRECONDITION, never for an assertion about where the app put it.

    focus_set() is a request the window manager may take its time over,
    and _focus_settles_on below only waits: used on a precondition it
    turns a loaded machine into a false red about an app that did
    nothing wrong. Both of this file's preconditions went red that way
    in a full-suite run (the same class as qa1's cell editor, closed as
    COVERAGE_LEDGER C11b). Forcing is correct here precisely because the
    promise under test is what happens when focus LEAVES."""
    widget.focus_force()
    t0 = time.time()
    while time.time() - t0 < cap_s:
        try:
            if app.focus_get() is widget:
                return True
        except (KeyError, tk.TclError):
            pass
        app.update()
        app.update_idletasks()
        time.sleep(0.02)
    return False


def _focus_leaves(widget, cap_s=2.0):
    """The mirror wait: poll until focus is NOT on the widget — clearing
    focus is as asynchronous as granting it."""
    t0 = time.time()
    while time.time() - t0 < cap_s:
        try:
            if app.focus_get() is not widget:
                return True
        except (KeyError, tk.TclError):
            return True
        app.update()
        time.sleep(0.02)
    return False

check('username entry has focus before clicking elsewhere',
      _take_focus(name_entry))
# Click the section's own title. It has to be a title that's actually on
# screen: Settings shows one section at a time, so reaching into a section
# that isn't selected would be clicking a widget the user cannot see, and
# Tk defers focus changes on unmapped widgets rather than applying them.
# Ask the app what this section is called rather than hardcoding it -- the
# label changed from "Your name" to "General" when the greeting settings were
# grouped, and a hardcoded string turned that into a crash here.
_section_labels = {k: l for k, l, _b, _e in app.SETTINGS_SECTIONS}
name_title = find_widget(app.settings_name_panel, tk.Label, _section_labels['name'])
check('the section title label was found', name_title is not None)
check('the shown section\'s title is actually visible', name_title.winfo_ismapped())
_qa_click(name_title)
app.update()
check('clicking a section title elsewhere in Settings clears the field\'s focus',
      _focus_leaves(name_entry))

# Regression: clicking "Back to Notes" directly (without clicking elsewhere
# in Settings first) must also clear focus — this is the exact path a user
# takes when they finish typing and immediately leave, and it broke once
# during development when the fix above was implemented too narrowly
# (bound to individual widgets instead of centrally).
check('username entry has focus before leaving Settings',
      _take_focus(name_entry))
back_btn = find_widget(app.settings_page, tk.Button, 'Back to Notes')
_qa_click(back_btn)
_qa_fire(back_btn, '<ButtonRelease-1>')
app.update()
check('clicking "Back to Notes" directly clears the field\'s focus',
      _focus_leaves(name_entry))
app.show_settings_page()
app.update()

# ---- A MESSAGE THAT POINTS INTO SETTINGS NAMES A SECTION IT HAS ----
# "Manage templates" became "Templates" when Settings became a list of
# sections, but the hint shown when there is no template to pick kept the
# old name and sent people to a section that was not there. Asked of that
# hint, then of every "Settings → X" in the app's code, so the next rename
# cannot leave one behind.
import ast, glob, re
_hint = []
_tpl_kept = app.templates
app.templates = []
app.show_info = lambda title, message='', *a, **k: _hint.append(message) or True
app.show_template_picker(); app.update()
app.show_info = lambda *a, **k: True
app.templates = _tpl_kept


def _names_a_section(text):
    return all(any(text[m.end():].startswith(label)
                   for label in _section_labels.values())
               for m in re.finditer('Settings → ', text))


check(f'with no templates, the hint names the section that holds them ({_hint})',
      len(_hint) == 1 and 'Settings → ' in _hint[0] and _names_a_section(_hint[0]))
_src = os.path.dirname(os.path.abspath(NO.__file__))
_stale = []
for _path in [os.path.join(_src, 'note_organizer.py')] + glob.glob(
        os.path.join(_src, 'noteorganizer', '**', '*.py'), recursive=True):
    with open(_path, encoding='utf-8') as _fh:
        _tree = ast.parse(_fh.read())
    _stale += [(os.path.basename(_path), n.lineno, n.value[:70])
               for n in ast.walk(_tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and 'Settings → ' in n.value and not _names_a_section(n.value)]
check(f'every "Settings → X" the app can show names a real section ({_stale})',
      not _stale)

# ---- SETTINGS: scrolling over a theme preview card scrolls the page (regression) ----
# The theme picker's preview cards are small Canvas widgets, which have a
# built-in default mouse-wheel behavior of their own — swallowing the wheel
# event instead of letting it reach the Settings page's own scroll.
def find_all(w, cls, acc=None):
    if acc is None: acc = []
    for c in w.winfo_children():
        if isinstance(c, cls):
            acc.append(c)
        find_all(c, cls, acc)
    return acc
# Three things have to be true before this can observe anything. The
# section owning the cards must be the selected one; the content pane must
# actually overflow (one section on its own fits the window at full size,
# and a pane with nothing to scroll looks exactly like the bug this
# guards); and the cards must be ones the page-wide recursive wheel bind
# never saw. That last one is the whole point: switching theme destroys and
# rebuilds every card, so the replacements are created long after
# build_settings_tab bound the tree, and only the theme picker's own
# forwarding covers them. Testing the first build instead passes even with
# that forwarding deleted.
app.toggle_settings_panel('appearance')
app.geometry('900x400')          # 400 is the app's own minimum height
app.update(); app.update_idletasks()
theme_before_wheel_test = app.theme_name
app.set_theme('light' if app.theme_name in NO.DARK_THEMES else 'dark')
app.update(); app.update_idletasks()
theme_canvases = find_all(app.theme_picker_frame, tk.Canvas)
check('theme picker has preview canvases to test', len(theme_canvases) > 0)
check('theme card is on screen', theme_canvases[0].winfo_ismapped())
check('Settings pane actually overflows, so scrolling is observable',
      app.settings_canvas.yview()[1] < 1.0)
before_scroll = app.settings_canvas.yview()
_qa_fire(theme_canvases[0], '<MouseWheel>', delta=-120)
app.update()
check('scrolling with the cursor over a theme card scrolls the Settings page',
      app.settings_canvas.yview() != before_scroll)
app.set_theme(theme_before_wheel_test)   # leave the theme as we found it
app.geometry('1100x850')
app.update()

# ---- SETTINGS: scrolling over a Statistics chip scrolls the page (regression) ----
# Same class of bug as the theme picker above, but a different root cause:
# these chips are plain Frames/Labels (no Canvas involved), just never
# wired into the page's wheel-forwarding at all — found by hand right after
# the theme picker fix above shipped.
# Enough categories that the chips wrap to several rows and the section is
# genuinely taller than the pane. Two categories no longer overflow now that
# Statistics is shown on its own rather than stacked under everything else,
# and a pane with nothing to scroll would pass this test no matter how badly
# the wheel were wired.
stat_cats = [f'Cat{i:02d}' for i in range(20)]
for c in stat_cats:
    NO.CATEGORY_COLORS.setdefault(c, '#7c5cff')
app.notes = [
    {'id': 900 + i, 'title': f'StatChip{i}', 'body': 'x',
     'category': stat_cats[i % len(stat_cats)], 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}
    for i in range(40)
]
app.show_settings_page()
app.toggle_settings_panel('statistics')
app.update()
chip_frames = find_all(app.stats_frame, tk.Frame)
check('statistics has category chips to test', len(chip_frames) > 0)
app.geometry('900x400')          # 400 is the app's own minimum height
app.update(); app.update_idletasks()
check('Settings pane overflows for the chip test too',
      app.settings_canvas.yview()[1] < 1.0)
before_stats_scroll = app.settings_canvas.yview()
# Found again, here, and not reused from before the resize. The
# statistics panel was destroyed and rebuilt from scratch on every
# note-list refresh while Settings was open (it updates its figures in
# place now, and still rebuilds on a palette or category change), so a
# chip captured earlier can name a widget that no longer exists by the
# time the wheel is aimed at it -- "bad window path name", and the
# script dies rather than fails.
#
# It was always this fragile; it only started biting when gating the
# panel's redraw on whether Settings is open moved WHEN that rebuild
# lands. Two runs in four on Linux, none on Windows, and none at all
# before that change -- which is the shape of a check holding a
# reference across something that rebuilds.
chip_frames = find_all(app.stats_frame, tk.Frame)
check('the chips are still there to aim at after the resize',
      len(chip_frames) > 0)
_qa_fire(chip_frames[0], '<MouseWheel>', delta=-120)
app.update()
check('scrolling with the cursor over a statistics chip scrolls the Settings page',
      app.settings_canvas.yview() != before_stats_scroll)
app.geometry('1100x850')
app.update()

app.save_username('Alexandra')  # restore for later checks
app._refresh_greeting()

# ---- SETTINGS: statistics chips are informational only, not clickable ----
# Chips used to navigate to a filtered note list on click, but real usage
# showed the click silently failing in both the script and the packaged
# .exe after scrolling the Settings page (never reproduced headlessly,
# despite trying several ways). Rather than chase that further, the
# interactivity was removed outright — Statistics is meant to be a
# read-only snapshot, not another way to filter notes. This guards
# against the interactivity accidentally coming back.
app.notes = [
    {'id':10,'title':'StatNote','body':'x','category':'Work','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
]
app.show_settings_page()
app.update()
app.filter_var.set('All')
app.notebook.select(app.TAB_CALENDAR)
app.update()
_stat_frames = find_all(app.stats_frame, tk.Frame)
# Indexed [0] straight off a find_all() before, which turns "the panel
# was rebuilt just now and is briefly empty" into an IndexError -- the
# script dies instead of failing, and a dead script reports no failures
# at all. Same family as the chips held across a rebuild below.
check('the statistics panel has a chip grid to inspect', bool(_stat_frames))
grid_frame = _stat_frames[0] if _stat_frames else None
chip = (grid_frame.winfo_children() or [None])[0] if grid_frame else None
check('statistics chip has no hand cursor (not clickable-looking)',
      chip is not None and str(chip.cget('cursor')) != 'hand2')
if chip is not None:
    _qa_click(chip)
    _qa_fire(chip, '<ButtonRelease-1>')
app.update()
check('clicking a statistics chip does not change tabs',
      app.notebook.index(app.notebook.select())==app.TAB_CALENDAR)
check('clicking a statistics chip does not change the filter',
      app.filter_var.get()=='All')

# stats freshness: total should reflect current note count after add
before_count = len(app.notes)
app.notes.append({'id':11,'title':'New','body':'x','category':'General','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]})
app.show_settings_page()
app.update()
check('note count grew after adding a note', len(app.notes) == before_count + 1)

# ---- SETTINGS: statistics update live, without leaving/reopening Settings
# (regression) ---- Deleting a category (its notes move to General) used to
# leave Statistics showing the stale, now-deleted category until the user
# left Settings and came back. refresh_note_list() (called by
# _delete_category) now unconditionally refreshes Statistics too. (An
# earlier version of this fix gated the refresh on the Settings page's
# winfo_ismapped() state, which looked right but wasn't reliably true right
# after pack() in real interactive use — it silently skipped real updates,
# which is worse than doing the (cheap) work unconditionally.)
def stats_label_texts():
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                out.append(str(c.cget('text')))
            walk(c)
    walk(app.stats_frame)
    return out

def stats_pairs():
    """Every "big number + caption beneath it" in the Statistics panel.

    Statistics used to render its figures as sentences ("2 templates"), so
    these checks matched substrings. It now shows a number and its caption
    as two labels, which reads far better but means a substring match finds
    nothing. Reading the pair structure instead tests the actual figure and
    survives the next presentation change too.

    Returns {caption: number} for the stat tiles, and {name: count} for the
    category pills, which have the same shape (a label and a number).
    """
    tiles, pills = {}, {}
    def walk(w):
        kids = w.winfo_children()
        labels = [c for c in kids if isinstance(c, tk.Label)]
        if len(labels) == 2:
            a, b = (str(labels[0].cget('text')), str(labels[1].cget('text')))
            if a.isdigit():          # tile: number above, caption below
                tiles[b] = int(a)
            elif b.isdigit():        # pill: name then count
                pills[a] = int(b)
        for c in kids:
            walk(c)
    walk(app.stats_frame)
    tiles.update(pills)
    return tiles

def category_in_stats(name):
    """Is this category shown in the Statistics breakdown?"""
    return name in stats_pairs()

NO.CATEGORY_COLORS['TempStatsCat'] = '#ff0000'
NO.persist_categories()
app.notes.append({'id':12,'title':'TempCatNote','body':'x','category':'TempStatsCat',
                   'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
                   'checklist':[],'attachments':[]})
app.show_settings_page()
app.update()
check('stats show the category before it is deleted',
      category_in_stats('TempStatsCat'))

app.ask_yes_no = lambda *a, **k: True
app._ask_category_deletion = lambda name, count, days_only=0: "move"
app._delete_category('TempStatsCat', redraw=lambda: None)
app.update()
check('stats no longer show the deleted category, without reopening Settings',
      not category_in_stats('TempStatsCat'))
check('the moved note is now counted under General in stats',
      category_in_stats('General'))

# ---- SETTINGS: stats reflect ALL categories, not just the first one
# (regression) ---- Saving notes into several different categories via the
# normal editor flow, then opening Settings once at the end (like a real
# user session, not forcing an update() after every micro-step), should
# show every category that has notes — not just whichever one happened to
# be current when Statistics last rendered.
NO.CATEGORY_COLORS['StatsCatA'] = '#00aaff'
NO.CATEGORY_COLORS['StatsCatB'] = '#ffaa00'
NO.persist_categories()
for cat_name in ('StatsCatA', 'StatsCatB'):
    app.new_note()
    app.title_entry.insert(0, f'{cat_name}Note')
    app.body_text.insert('1.0', 'x')
    app.category_var.set(cat_name)
    app.save_current_note(auto=False)
app.show_settings_page()
app.update()
texts = stats_label_texts()
check('stats show StatsCatA after a normal save sequence',
      category_in_stats('StatsCatA'))
check('stats show StatsCatB after a normal save sequence',
      category_in_stats('StatsCatB'))

# ---- SETTINGS: templates/checklists/deleted counts and first-launch date ----
# Templates and checklists are counted as standalone things (how many exist),
# not how many notes reference them — a template can be reused across many
# notes, a checklist only ever lives inside the one note it's on. "Deleted"
# is whatever's currently in Trash right now, not an all-time total.
app.templates = [
    NO.normalize_template({'name': 'StatsTplA'}),
    NO.normalize_template({'name': 'StatsTplB'}),
]
app.notes.append({'id': 900, 'title': 'ChecklistNote', 'body': 'x', 'category': 'General',
                   'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
                   'checklist': [{'text': 'item', 'done': False}], 'attachments': []})
app.trash = [{'id': 901, 'title': 'Deleted', 'category': 'General', 'deleted_at': '2026-01-01 00:00'}]
app.show_settings_page()
app.update()
texts = stats_label_texts()
check('stats show the correct template count',
      stats_pairs().get('Templates') == 2)
check('stats show the correct checklist-notes count',
      stats_pairs().get('With a checklist') == 1)
check('stats show the correct deleted (Trash) count',
      stats_pairs().get('In trash') == 1)
check('stats show a first-launch date',
      any('Using Note Organizer since' in t for t in texts))

# ---- SETTINGS: template count updates live, entirely within Settings
# (regression) ---- Adding/deleting a template via the Manage Templates
# panel used to leave Statistics showing the stale count until the user
# switched away (to the editor) and back. _edit_template's save() and
# _build_template_row's delete() now call _render_statistics() themselves,
# so this updates immediately, without leaving Settings at all. Uses the
# real popup/button flow, not direct self.templates mutation, so it
# actually exercises the same path a user would.
def find_all2(w, cls, acc=None):
    if acc is None: acc = []
    for c in w.winfo_children():
        if isinstance(c, cls):
            acc.append(c)
        find_all2(c, cls, acc)
    return acc

app.templates = []
NO.save_templates(app.templates)
app.show_settings_page()
app.update()
app.toggle_settings_panel('templates')
app.update()
check('template count starts at 0', stats_pairs().get('Templates') == 0)

app._edit_template(None, app._refresh_templates_panel)
app.update()
popup = app._mini_popup
find_all2(popup, tk.Entry)[0].insert(0, 'LiveTplTest')
save_btn = next(b for b in find_all2(popup, tk.Button) if str(b.cget('text')) == 'Save')
save_btn.invoke()
app.update()
check('template count updates live after saving a new template, no navigation away',
      stats_pairs().get('Templates') == 1)

# Row actions are drawn glyphs on a Canvas now, not Buttons carrying an
# emoji label, so find them by the kind each widget records.
delete_btn = next(c for c in find_all2(app.settings_templates_panel, tk.Canvas)
                  if getattr(c, '_icon_kind', None) == 'trash')
_qa_click(delete_btn)
app.update()
check('template count updates live after deleting a template, no navigation away',
      stats_pairs().get('Templates') == 0)

# The template editor kept a template's styles as offsets beside its text,
# so any edit before a bold run moved the bold onto other words -- and every
# note made from the template inherited it (2026-10-28, the final audit).
_tf_body = 'Attendees: Ana, Bo\nDecisions are final'
app.templates = [NO.normalize_template({
    'name': 'Minutes', 'body': _tf_body,
    'formatting': [{'start': 19, 'end': 38, 'style': 'bold'}]})]
NO.save_templates(app.templates)
app._refresh_templates_panel(); app.update()
app._edit_template(app.templates[0], app._refresh_templates_panel)
app.update()
_tf_box = find_all2(app._mini_popup, tk.Text)[0]
_tf_box.insert('1.0', 'Present: ')
next(b for b in find_all2(app._mini_popup, tk.Button)
     if str(b.cget('text')) == 'Save').invoke()
app.update()
_tf_saved = next(t for t in app.templates if t.get('name') == 'Minutes')
_tf_bold = [_tf_saved['body'][s['start']:s['end']]
            for s in _tf_saved.get('formatting') or [] if s.get('style') == 'bold']
check(f'an edit in the template editor keeps the bold on the words it was on '
      f'({_tf_bold})', _tf_bold == ['Decisions are final'])
app.templates = []
NO.save_templates(app.templates)
app._refresh_templates_panel(); app.update()

# ---- SETTINGS: templates/checklists stay current when switching away and
# back (regression) ---- Checklist edits happen in the note editor, a
# genuinely different screen from Settings, so they can't live-update
# Statistics while Settings itself is showing — but show_settings_page()
# always recomputes fresh from current data, so leaving Settings and
# coming back should still show accurate counts.
app.templates.append(NO.normalize_template({'name': 'StatsTplC'}))
NO.save_templates(app.templates)
app.hide_settings_page()
app.update()
app.show_settings_page()
app.update()
check('template count reflects a template added while away, on return to Settings',
      stats_pairs().get('Templates') == 1)

app.hide_settings_page()
app.update()
app.new_note()
app.title_entry.insert(0, 'SwitchChecklistNote')
app.body_text.insert('1.0', 'x')
app._working_checklist = [{'text': 'a checklist item', 'done': False}]
if hasattr(app, '_render_checklist_items'):
    app._render_checklist_items()
app.save_current_note(auto=False)
app.update()
app.show_settings_page()
app.update()
check('checklist count reflects a note saved from the editor, on return to Settings',
      stats_pairs().get('With a checklist') == 2)

# ---- ATTACHMENTS (through the UI functions, not just file cleanup) ----
tmp_file = os.path.join(tempfile.gettempdir(), 'qa6_attachment.txt')
with open(tmp_file, 'w') as f:
    f.write('sample content')

app.new_note()
app.title_entry.insert(0, 'AttachTest')
app.body_text.insert('1.0', 'x')
app.current_attachments = []
fd.askopenfilenames = lambda **k: (tmp_file,)
app.add_attachment()
app.update()
check('add_attachment adds one entry', len(app.current_attachments) == 1)
check('add_attachment preserves original filename', app.current_attachments[0]['filename'] == 'qa6_attachment.txt')
stored_path = os.path.join(NO.ATTACHMENTS_DIR, app.current_attachments[0]['stored_as'])
check('add_attachment actually copies the file to disk', os.path.isfile(stored_path))

app.save_current_note(auto=False)
app.update()
saved_note = app.find_note(app.selected_note_id)
check('attachment persists on the saved note', len(saved_note.get('attachments', [])) == 1)

# reopen the note — attachment should still be listed (persist across note switch)
app.new_note()
app.load_note(saved_note)
app.update()
check('attachment survives switching away and back', len(app.current_attachments) == 1)

# ---- Removing an attachment CONFIRMS first (the no-confirm sweep) ----
# The ✕ deleted the stored file permanently with no question at all —
# the one destructive gesture outside the dialog system, found by the
# docs auditor by accident and closed by the C1 sweep. Answering No
# must leave both the list entry and the file untouched.
_orig_ask_att = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: False
try:
    app.remove_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _orig_ask_att
check('answering No keeps the attachment in the list',
      len(app.current_attachments) == 1)
check('and keeps the stored file on disk', os.path.isfile(stored_path))
_att_ask = {}
app.ask_yes_no = lambda t, m, **kw: (_att_ask.update(kw), True)[1]
try:
    app.remove_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _orig_ask_att
check('the confirm asks with the warning glyph and No pre-selected',
      _att_ask.get('icon') == 'warning' and _att_ask.get('default') == 'no')
check('remove_attachment clears the list', len(app.current_attachments) == 0)
check('remove_attachment deletes the file from disk', not os.path.isfile(stored_path))

# The file asked about is the file removed. While the question waited, the
# editor could move on to another note; the index then named THAT note's
# attachment, whose stored file went for good.
_mv_files = []
for _mv_name in ('mv_a.txt', 'mv_b.txt'):
    _mv_path = os.path.join(NO.ATTACHMENTS_DIR, _mv_name)
    with open(_mv_path, 'w') as _mv_f:
        _mv_f.write('keep me')
    _mv_files.append(_mv_path)
app.current_attachments = [{'filename': 'mine.txt', 'stored_as': 'mv_a.txt'}]
_mv_other = [{'filename': 'theirs.txt', 'stored_as': 'mv_b.txt'}]
_mv_note_before = app.selected_note_id


def _mv_answer(*a, **k):
    # Another note opens under the waiting question, then the answer: Yes.
    app.selected_note_id = (_mv_note_before or 0) + 999
    app.current_attachments = list(_mv_other)
    return True


app.ask_yes_no = _mv_answer
try:
    app.remove_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _orig_ask_att
    app.selected_note_id = _mv_note_before
check('a Yes given after the editor moved on removes nothing: the other '
      'note\'s file stays on disk and in its list (%s)' % app.current_attachments,
      os.path.isfile(_mv_files[1]) and app.current_attachments == _mv_other
      and os.path.isfile(_mv_files[0]))
app.current_attachments = []
for _mv_path in _mv_files:
    if os.path.isfile(_mv_path):
        os.remove(_mv_path)

# A file another note or a Trash entry still shows stays on disk: a
# duplicate or an import that could not copy a file keeps its name, and
# removing it from one note deleted it from under the other.
_sh_path = os.path.join(NO.ATTACHMENTS_DIR, 'shared_dup.txt')
_sh_att = {'filename': 'shared.txt', 'stored_as': 'shared_dup.txt'}
for _sh_where in ('notes', 'trash'):
    with open(_sh_path, 'w') as _sh_f:
        _sh_f.write('two notes show me')
    _sh_holder = {'id': 99001, 'title': 'the duplicate',
                  'attachments': [dict(_sh_att)]}
    getattr(app, _sh_where).append(_sh_holder)
    app.current_attachments = [dict(_sh_att)]
    app.ask_yes_no = lambda *a, **k: True
    try:
        app.remove_attachment(0)
        app.update()
    finally:
        app.ask_yes_no = _orig_ask_att
        getattr(app, _sh_where).remove(_sh_holder)
    check('removing a file one of the %s still shows keeps it on disk' % _sh_where,
          app.current_attachments == [] and os.path.isfile(_sh_path))
# Only if still there: a regression deletes it, and the suite must still
# reach its footer to say so.
if os.path.isfile(_sh_path):
    os.remove(_sh_path)

# A file attached or removed after a save in the same visit. The save stored
# the editor's own list in the note, so the attach changed the note too: the
# editor read as saved, and closing the app lost the file's entry -- and a
# removed file stayed listed with its stored copy already deleted.
import json as _json6a
app.new_note()
app.title_entry.insert(0, 'AttachAfterSave')
app.body_text.insert('1.0', 'typed first')
app.save_current_note(auto=False)
app.update()
# A second save, of the note as it now exists: the first one made a new
# note, whose fields are copied on the way in, and it is the save of an
# existing note that stored the editor's own list.
app.body_text.insert('end-1c', ' and typed again')
app.save_current_note(auto=False)
app.update()
_aa_id = app.selected_note_id
check('fixture: the note was saved twice, the second time as itself',
      _aa_id is not None and 'typed again' in app.find_note(_aa_id)['body'])
_aa_files = []
for _aa_name in ('qa6_after_one.txt', 'qa6_after_two.txt'):
    _aa_path = os.path.join(tempfile.gettempdir(), _aa_name)
    with open(_aa_path, 'w') as _aa_f:
        _aa_f.write('after a save')
    _aa_files.append(_aa_path)


def _aa_disk():
    with open('notes_data.json', encoding='utf-8') as _aa_f:
        return [a.get('filename') for n in _json6a.load(_aa_f)
                if n.get('id') == _aa_id for a in n.get('attachments') or []]


fd.askopenfilenames = lambda **k: tuple(_aa_files)
app.add_attachment()
app.update()
_aa_unsaved = not app.editor_state_matches_saved(app.capture_editor_state())
app._flush_autosave()
app.update()
check(f'files attached after a save read as unsaved ({_aa_unsaved}), and the '
      f'next flush stores them ({_aa_disk()})',
      _aa_unsaved and _aa_disk() == ['qa6_after_one.txt', 'qa6_after_two.txt'])
app.ask_yes_no = lambda *a, **k: True
try:
    app.remove_attachment(1)
    app.update()
finally:
    app.ask_yes_no = _orig_ask_att
_aa_unsaved = not app.editor_state_matches_saved(app.capture_editor_state())
app._flush_autosave()
app.update()
check(f'...and a file removed after that save reads as unsaved '
      f'({_aa_unsaved}), and the next flush stores the removal ({_aa_disk()})',
      _aa_unsaved and _aa_disk() == ['qa6_after_one.txt'])
app.ask_yes_no = lambda *a, **k: True
try:
    app.remove_attachment(0)
    app.update()
finally:
    app.ask_yes_no = _orig_ask_att
app._flush_autosave()
for _aa_path in _aa_files:
    if os.path.isfile(_aa_path):
        os.remove(_aa_path)
app.new_note()
app.current_attachments = []

# ---- COMBINATIONS ----

# Template + Checklist + Category together
app.templates.append({
    'name': 'ComboTemplate', 'title': 'Combo Title', 'body': 'Combo body',
    'comments': '', 'category': 'Work',
    'checklist': [{'text': 'step one', 'done': False}, {'text': 'step two', 'done': False}],
})
NO.save_templates(app.templates)
app.new_note()
tpl = next(t for t in app.templates if t['name'] == 'ComboTemplate')
app._apply_template(tpl)
app.update()
check('template applies its category', app.category_var.get() == 'Work')
check('template applies its checklist', len(app._working_checklist) == 2)

# Pin + Sort + Group behaving consistently
app.notes = [
    {'id':20,'title':'Zebra','body':'x','category':'General','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[],'pinned':False},
    {'id':21,'title':'Apple','body':'x','category':'General','updated':'2026-01-02 00:00','created':'2026-01-02 00:00','checklist':[],'attachments':[],'pinned':False},
]
zebra = app.find_note(20)
app.toggle_pin(zebra)
if hasattr(app, 'sort_var'):
    app.sort_var.set('Title A-Z')
app.refresh_note_list()
app.update()
check('pinned note stays pinned regardless of sort mode', app.find_note(20)['pinned'] is True)

# Autosave + checklist + immediate note switch (nothing lost)
app.new_note()
app.title_entry.insert(0, 'AutosaveComboA')
app.body_text.insert('1.0', 'x')
app.save_current_note(auto=False)
app.update()
note_a = app.find_note(app.selected_note_id)
app.load_note(note_a)
app.checklist_add_var.set('quick item')
app._add_checklist_item()  # the real add path — also schedules autosave, unlike directly mutating the list
app.open_blank_tab()  # what the actual "+ New Note" button calls — flushes pending autosave first, unlike new_note() alone
app.update()
saved_a = app.find_note(note_a['id'])
check('checklist change is captured by autosave-on-switch', any(
    it.get('text') == 'quick item' for it in saved_a.get('checklist', [])))

# ---- LAYOUT (the parts that are genuinely checkable, not just "looks nice") ----

# Sidebar hide/show
before_hidden = app._sidebar_hidden
app.toggle_sidebar()
app.update()
# ---- PAGE SWITCHES DISMISS THE OPEN POPUP ----
# A dropdown opened in Settings kept floating over the editor after
# Back to Notes -- a popup belongs to the page it was opened on.
_was_settings = bool(app.settings_page.winfo_ismapped())
app._edit_template(None, lambda: None)
app.update()
check('a popup opens in Settings', app._mini_popup is not None)
app.hide_settings_page()
app.update()
check('Back to Notes dismisses it', app._mini_popup is None)
app.show_settings_page()
app.update()
app._edit_template(None, lambda: None)
app.update()
app.hide_settings_page()
app.update()
app._edit_template(None, lambda: None)
app.update()
_popT = app._mini_popup
app.notebook.event_generate('<<NotebookTabChanged>>')
app.update()
check('a notebook tab change dismisses it too', app._mini_popup is None)
app.hide_settings_page()
app.update()
app._edit_template(None, lambda: None)
app.update()
app.show_settings_page()
app.update()
check('and entering Settings dismisses a popup left open in Notes',
      app._mini_popup is None)
if _was_settings:
    app.show_settings_page()
else:
    app.hide_settings_page()
app.update()

check('toggle_sidebar flips the hidden state', app._sidebar_hidden != before_hidden)
app.toggle_sidebar()
app.update()
check('toggling again restores the sidebar', app._sidebar_hidden == before_hidden)

# Dialogs stay within the app window's own bounds (never a separate OS window
# that could be dragged outside it)
def find_btn_qa6(w, label):
    for c in w.winfo_children():
        if isinstance(c, tk.Button) and str(c.cget('text')) == label:
            return c
        r = find_btn_qa6(c, label)
        if r: return r
    return None

choice_holder = {}
def capture_choice(var):
    app.update()
    for frame in app.place_slaves():
        if find_btn_qa6(frame, "OK"):
            # Check everything about the dialog HERE, while it still exists —
            # _themed_dialog destroys it as soon as this callback returns
            # (that's what "wait_variable returned" means to its own cleanup
            # code), so a stored widget reference checked afterward would
            # already be pointing at a destroyed widget.
            choice_holder['found'] = True
            app.update_idletasks()
            within_x = app.winfo_rootx() <= frame.winfo_rootx() <= app.winfo_rootx() + app.winfo_width()
            within_y = app.winfo_rooty() <= frame.winfo_rooty() <= app.winfo_rooty() + app.winfo_height()
            choice_holder['within_bounds'] = within_x and within_y
            return
app.wait_variable = capture_choice
app._themed_dialog("Test", "Just checking dialog bounds", kind="question",
                   buttons=[("OK", "ok")])
check('dialog renders as an in-window overlay, not a separate Toplevel',
      choice_holder.get('found', False))
check('dialog is positioned within the app window bounds',
      choice_holder.get('within_bounds', False))

# ---- DIALOG: icon= and default= are honoured (audit Z07-F05) ----
# A destructive confirm (template-replace, delete-forever, empty-trash,
# open-risky-file) passed icon="warning", default="no" — but ask_yes_no
# dropped both kwargs, so the dialog drew the ❓ glyph and focused "Yes".
# A reflexive Enter then fired the dangerous action. Lock the two pure
# decision helpers (deterministic) AND the end-to-end wiring.
check('dialog focus index: default names the button, case-insensitive',
      app._dialog_focus_index([("No", False), ("Yes", True)], "no") == 0
      and app._dialog_focus_index([("No", False), ("Yes", True)], "YES") == 1)
check('dialog focus index: no default -> primary (last) button',
      app._dialog_focus_index([("No", False), ("Yes", True)], None) == 1)
check('dialog focus index: unknown default falls back to primary, never unfocused',
      app._dialog_focus_index([("No", False), ("Yes", True)], "maybe") == 1)
check('dialog kind: icon= is honoured, not dropped for the fallback glyph',
      app._kind_from("warning", None, "question") == "warning"
      and app._kind_from(None, None, "question") == "question")
# The same class, closed at the root rather than guarded one keyword at a
# time. The five wrappers took **kw and forwarded a subset, so anything
# they did not understand vanished: first that `default="no"`, then seven
# `parent=` arguments that read like they anchored the dialog somewhere
# and did nothing -- this is an overlay inside the app window, and
# _themed_dialog has never had such a parameter. The signatures are named
# and keyword-only now, so Python refuses a stray keyword at the call.
#
# Reached through the CLASS, not the instance: this file monkeypatches
# show_info, show_warning and ask_yes_no to lambdas that swallow anything,
# so the first version of this check tested the stubs and passed nothing.
# Safe to call for real -- an unexpected keyword is a TypeError at binding
# time, before a line of the body runs, so no dialog ever opens.
_kw_refused = []
for _kw_name in ('show_info', 'show_warning', 'show_error',
                 'ask_yes_no', 'ask_yes_no_cancel'):
    try:
        getattr(app.__class__, _kw_name)(app, "t", "m", parent=app)
    except TypeError:
        _kw_refused.append(_kw_name)
    except Exception:
        # Anything else means the keyword got through and the body ran.
        pass
check('dialog: a keyword the dialogs cannot honour is refused, not swallowed',
      len(_kw_refused) == 5)

def _find_label_with(w, needle):
    if isinstance(w, tk.Label) and needle in str(w.cget('text')):
        return w
    for c in w.winfo_children():
        r = _find_label_with(c, needle)
        if r:
            return r
    return None

# Record which button the dialog CALLS focus_set on, rather than reading
# keyboard focus back with focus_get() — under a full-suite run focus
# lands asynchronously and a focus_get() read flakes (a documented class,
# qa/README). The call is synchronous and deterministic. A 3-button
# ask_yes_no_cancel with default="no" focuses the MIDDLE button, so this
# one case fails if the code focuses the primary (Yes), the first
# (Cancel), or any hard-coded position.
_warn_probe = {}
_focus_calls = []
_orig_focus_set = tk.Misc.focus_set
def _rec_focus_set(self):
    _focus_calls.append(self)
    return _orig_focus_set(self)

def _capture_warn(var):
    app.update()
    for frame in app.place_slaves():
        if find_btn_qa6(frame, "No"):
            head = _find_label_with(frame, "Danger check")
            # ⚠ is the base warning sign; the dropped-icon fallback is ❓.
            _warn_probe['glyph_ok'] = head is not None and "⚠" in str(head.cget('text'))
            focused = [w for w in _focus_calls if isinstance(w, tk.Button)
                       and str(w.cget('text')) in ("Cancel", "No", "Yes")]
            _warn_probe['no_focused'] = (
                bool(focused)
                and all(str(w.cget('text')) == "No" for w in focused))
            return

_saved_wv = app.wait_variable
app.wait_variable = _capture_warn
tk.Misc.focus_set = _rec_focus_set
try:
    # ask_yes_no(_cancel) is monkeypatched to a lambda elsewhere in this
    # file, so reach the REAL wrapper via the class to genuinely exercise
    # its icon=/default= forwarding (that is the fix under test).
    app.__class__.ask_yes_no_cancel(app, "Danger check", "Replace everything?",
                                    icon="warning", default="no")
finally:
    tk.Misc.focus_set = _orig_focus_set
    app.wait_variable = _saved_wv
check('warning confirm draws the warning glyph, not the question glyph',
      _warn_probe.get('glyph_ok', False))
check('default="no" focuses the No button, not the primary/first (Enter is safe)',
      _warn_probe.get('no_focused', False))

# ---- SETTINGS: "Back to Notes" stays fixed while scrolling (regression) ----
# It used to be just another row inside the scrollable page, so it
# scrolled away like any other content instead of staying visible.
app.show_settings_page()
app.update()
back_btn2 = find_widget(app.settings_page, tk.Button, 'Back to Notes')
check('back to notes button found', back_btn2 is not None)
if back_btn2:
    before_y = back_btn2.winfo_rooty()
    app.settings_canvas.yview_moveto(0.5)
    app.update()
    after_y = back_btn2.winfo_rooty()
    check('"Back to Notes" does not move when the settings page scrolls',
          before_y == after_y)

def _resize(width, height, attempts=60):
    """Resize the window and wait until it has really happened.

    geometry() is a request to the window manager, not a resize. Reading a
    widget's size straight after it can still give the old one, which makes
    any check that depends on the new size flaky rather than wrong.
    """
    app.geometry(f'{width}x{height}')
    for _ in range(attempts):
        app.update()
        app.update_idletasks()
        if abs(app.winfo_width() - width) <= 2 and                 abs(app.winfo_height() - height) <= 2:
            break
        time.sleep(0.02)
    app.update()
    app.update_idletasks()
    app.update()


# ---- THE SECTION LIST SCROLLS WHEN THE WINDOW IS SHORT ----
# Nine entries in four groups, plus a brand and the theme toggle, need more
# height than a short window has. The list was a plain Frame, so whatever
# did not fit was simply unreachable.
_resize(1100, 420)
app.show_settings_page()
_resize(1100, 420)

_nav = app._settings_nav_canvas
_box = _nav.bbox('all')
check(f'the section list overflows a short window '
      f'({_box[3] if _box else 0}px of entries in {_nav.winfo_height()}px)',
      bool(_box) and _box[3] > _nav.winfo_height())


class _Wheel:
    delta = -360


_before = _nav.yview()[0]
app._settings_nav_wheel(_Wheel())
app.update()
check('the wheel scrolls the section list', _nav.yview()[0] > _before)

check('the wheel reaches the entries themselves, not just the canvas behind',
      any(bool(w.bind('<MouseWheel>'))
          for w in (app._settings_nav_buttons['about'],
                    app._settings_nav_buttons['about'].master)))

# Tall enough for everything: scrolling would only shift content that is
# already fully visible, which reads as the list drifting for no reason.
_resize(1100, 1000)
_nav.yview_moveto(0)
app.update()
app._settings_nav_wheel(_Wheel())
app.update()
check('a window tall enough for every entry does not scroll',
      _nav.yview()[0] == 0.0)

_resize(1100, 850)

# ---- DERIVED SURFACES FOLLOW A THEME SWITCH (regression) ----
# Settings blends `card` toward `text` for the well inside a card, and
# toward `subtext` for its hairlines. Neither result is in any theme's
# palette, so _recolor_stragglers -- which remaps palette colours -- could
# not see them: a panel built under a dark theme kept the dark inset on a
# light one, and the information bars in General, Backup and About were
# unreadable.
def _all_backgrounds(widget, found=None):
    found = [] if found is None else found
    for child in widget.winfo_children():
        try:
            found.append(str(child.cget('bg')).lower())
        except tk.TclError:
            pass
        _all_backgrounds(child, found)
    return found


app.show_settings_page()
app.update()
for _section in ('name', 'backup', 'about'):
    app.toggle_settings_panel(_section)
    app.update()

for _theme in ('light', 'dark'):
    app.set_theme(_theme)
    app.update()
    _current = {NO.inset_surface(app.colors).lower(),
                NO.hairline(app.colors).lower()}
    _foreign = set()
    for _name, _palette in NO.THEMES.items():
        if _name == app.theme_name:
            continue
        for _derived in (NO.inset_surface(_palette), NO.hairline(_palette)):
            if _derived.lower() not in _current:
                _foreign.add(_derived.lower())
    _stale = []
    for _section in ('name', 'backup', 'about'):
        _panel = getattr(app, f'settings_{_section}_panel', None)
        if _panel is None:
            continue
        _stale += [b for b in _all_backgrounds(_panel) if b in _foreign]
    check(f'no Settings panel keeps another theme\'s derived surface '
          f'after switching to {_theme} ({len(_stale)} found)', not _stale)

app.hide_settings_page()
app.update()

# ---- SETTINGS → ABOUT: the privacy policy, and feedback as a Store review ----
# About opens pages in the browser: the privacy policy always, a Store
# review once the app has a Store page -- and before that, no Feedback card
# at all. The browser is stood in for here: nothing is opened. The running
# app's own details still head every crash_log.txt entry (core/diagnostics).
import webbrowser as _fb_web
from noteorganizer.core import diagnostics as _fb_diag, paths as _fb_paths
_fb_opened, _fb_warned = [], []
_fb_real = (_fb_web.open, _fb_diag.STORE_REVIEW_URL, app.notes, app.show_warning,
            _fb_diag.NOTICES, getattr(os, 'startfile', None))
app.notes = [NO.normalize_note({'id': 1, 'title': 'SECRET-TITLE', 'body': 'SECRET-BODY',
                                'attachments': [{'name': 'a.pdf', 'stored_as': '1_a.pdf'}]}),
             NO.normalize_note({'id': 2, 'title': 'two', 'body': 'x'})]
_fb_frame = tk.Frame(app)
try:
    _fb_web.open = lambda url, *a, **k: (_fb_opened.append(url), True)[1]
    app.show_warning = lambda *a, **k: _fb_warned.append(' '.join(map(str, a)))
    _fb_said = dict(_fb_diag.details())
    check(f'the running app hands a crash log its version, how it draws and how big '
          f'the notebook is ({_fb_said})',
          _fb_said.get('version') == NO.APP_VERSION and _fb_said.get('notes') == 2
          and _fb_said.get('files') == 1
          and _fb_said.get('theme') == NO.THEME_LABELS[app.theme_name]
          and str(_fb_said.get('scale', '')).endswith('%')
          and _fb_said.get('sharp') in ('on', 'off'))
    check('...and nothing from the notes', 'SECRET' not in repr(_fb_said))
    app._build_settings_about_panel(_fb_frame)
    check('no Feedback card while the app is not in the Store',
          find_btn_qa6(_fb_frame, 'Write a review') is None)

    def _fb_texts(w):
        # Only labels a geometry manager shows: one built and never packed
        # is in the tree but not on the screen.
        out = [str(w.cget('text'))] if isinstance(w, tk.Label) and w.winfo_manager() else []
        for c in w.winfo_children():
            out += _fb_texts(c)
        return out
    check('About says the app is free software, provided as is, under the MIT license',
          _fb_diag.ABOUT_TERMS in _fb_texts(_fb_frame)
          and 'MIT license' in _fb_diag.ABOUT_TERMS and 'as is' in _fb_diag.ABOUT_TERMS)
    _fb_privacy = find_btn_qa6(_fb_frame, 'Read')
    if _fb_privacy is not None:
        _fb_privacy.invoke()
    check('About opens the privacy policy',
          _fb_privacy is not None and _fb_opened[-1:] == [_fb_diag.PRIVACY_URL])
    # A browser that will not open: the link is copied, and the words say
    # where to paste it.
    _fb_web.open = lambda url, *a, **k: False
    if _fb_privacy is not None:
        _fb_privacy.invoke()
    check('a browser that will not open leaves the link copied, and says so',
          bool(_fb_warned) and 'copied' in _fb_warned[-1]
          and app.clipboard_get() == _fb_diag.PRIVACY_URL)
    # The licenses: a text file that ships with the app, opened in the
    # person's editor -- stood in for here too.
    os.startfile = lambda p, *a, **k: _fb_opened.append(p)
    _fb_lic = find_btn_qa6(_fb_frame, 'Open')
    if _fb_lic is not None:
        _fb_lic.invoke()
    _fb_lic_path = _fb_paths.bundled_file(_fb_diag.NOTICES)
    check('About opens the licenses file that ships with the app',
          _fb_lic is not None and _fb_opened[-1:] == [_fb_lic_path])
    _fb_lic_text = open(_fb_lic_path, encoding='utf-8').read() if os.path.isfile(_fb_lic_path) else ''
    check('...which holds the app\'s own license and those of Python, Pillow and '
          'the PyInstaller bootloader',
          all(part in _fb_lic_text for part in
              ('Note Organizer -- MIT License', 'PYTHON SOFTWARE FOUNDATION LICENSE',
               '\nPillow ', 'Bootloader Exception')))
    _fb_diag.NOTICES = 'no-such-licenses.txt'
    _fb_count = len(_fb_opened)
    if _fb_lic is not None:
        _fb_lic.invoke()
    check('a copy of the app without the file says so, and opens nothing',
          len(_fb_opened) == _fb_count and bool(_fb_warned)
          and 'missing' in _fb_warned[-1])
    # Once the app has a Store page, feedback is a review there.
    _fb_diag.STORE_REVIEW_URL = 'ms-windows-store://review/?ProductId=TEST'
    _fb_web.open = lambda url, *a, **k: (_fb_opened.append(url), True)[1]
    _fb_frame.destroy()
    _fb_frame = tk.Frame(app)
    app._build_settings_about_panel(_fb_frame)
    _fb_store = find_btn_qa6(_fb_frame, 'Write a review')
    if _fb_store is not None:
        _fb_store.invoke()
    check('with a Store page, Feedback\'s Write a review opens its review page',
          _fb_store is not None and _fb_opened[-1] == _fb_diag.STORE_REVIEW_URL)
finally:
    # Put back what was there -- the script's own silent stand-in from its
    # first lines -- not the real dialog a del would have uncovered.
    (_fb_web.open, _fb_diag.STORE_REVIEW_URL, app.notes, app.show_warning,
     _fb_diag.NOTICES, _fb_startfile) = _fb_real
    if _fb_startfile is not None:
        os.startfile = _fb_startfile
    elif hasattr(os, 'startfile'):
        del os.startfile   # not Windows: there was none to put back
    _fb_frame.destroy()
    app.update()

# ---- EXPANDING THE BODY BOX ----
# Twelve rows suits most notes and is cramped for a long one, so the writing
# area has the same one-click Expand toggle the comments box has. Dragging an
# edge was tried first and abandoned: the editor sits in a scrolling canvas
# that recomputes its scrollregion on every resize, and a drag sends dozens a
# second, leaving widgets drawn at stale positions. Checked here because what
# makes this one different from the comments box is persistence, which is what
# the rest of this file is about.
app.new_note()
app.update()


def _rows(w):
    return int(w.cget('height'))


_btn = app.body_resize_btn
check('the body box has an expand button', _btn is not None)
check(f'it starts compact at 12 rows ({_rows(app.body_text)})',
      _rows(app.body_text) == 12)

_btn.invoke()
app.update()
check(f'one click takes it to 26 rows ({_rows(app.body_text)})',
      _rows(app.body_text) == 26)
check(f'the button then offers to collapse ({_btn.cget("text")!r})',
      'Collapse' in str(_btn.cget('text')))
check(f'the taller box is really taller on screen ({app.body_text.winfo_height()}px)',
      app.body_text.winfo_height() > 300)

# The point of the feature: a taller box must not put the Save row out of
# reach. The editor already scrolls, so the page just gets longer.
app.update_idletasks()
_region = app.editor_canvas.bbox('all')
check('the whole editor still fits inside the scrollable region',
      app.editor.winfo_reqheight() <= _region[3] - _region[1] + 2)

check('expanding is written to settings',
      NO.load_settings().get('editor_body_expanded') is True)
_btn.invoke()
app.update()
check(f'clicking again returns it to 12 rows ({_rows(app.body_text)})',
      _rows(app.body_text) == 12)
check('collapsing is written too',
      NO.load_settings().get('editor_body_expanded') is False)

# A box built while the setting says expanded must open expanded -- the read
# side of the same preference. Built on a throwaway widget rather than by
# opening a second window, which would mean two Tk interpreters at once.
NO.save_setting('editor_body_expanded', True)
_scratch_host = tk.Frame(app)
_scratch_text = tk.Text(_scratch_host, height=12)
_scratch_text.pack()
app._add_text_resize_toggle(_scratch_host, _scratch_text, compact=12, expanded=26,
                            remember_key='editor_body_expanded')
check(f'a box built while the stored choice is "expanded" opens expanded '
      f'({_rows(_scratch_text)} rows)', _rows(_scratch_text) == 26)
_scratch_host.destroy()
NO.save_setting('editor_body_expanded', False)

# The comments box shares the helper and must be untouched by all this: same
# toggle, still four rows by default, and -- since 0.75.186 -- remembered the
# same way the body's is. The asymmetry was never argued for: the only thing
# written down about it was a line at the BODY's call site noting that the
# comments box did not remember, which states the difference without giving a
# reason, while the helper's own docstring draws the line at "a box whose size
# is incidental" against "one someone chose".
check(f'the comments box is still compact at 4 rows ({_rows(app.comments_text)})',
      _rows(app.comments_text) == 4)
# Both boxes now carry a toggle reading "Expand", so the body's own button
# has to be excluded by identity -- matching on the label alone finds two.
_comment_btns = [w for w in app.editor.winfo_children()
                 if isinstance(w, tk.Button) and 'Expand' in str(w.cget('text'))
                 and w is not app.body_resize_btn]
check(f'the comments box still has its own toggle ({len(_comment_btns)} found)',
      len(_comment_btns) == 1)
if _comment_btns:
    _comment_btns[0].invoke()
    app.update()
    check(f'the comments toggle still works ({_rows(app.comments_text)} rows)',
          _rows(app.comments_text) == 12)
    # This line used to read
    #     check('the comments box is deliberately not persisted',
    #           'comments_expanded' not in NO.load_settings())
    # and it could never have failed. The key the helper would write is
    # `editor_comments_expanded`; `comments_expanded` was never a candidate
    # for it, so the check asserted the absence of a name nothing would ever
    # have created. It stayed green through the change that made the box
    # persist, which is how it was found. A check about an absence has to name
    # the thing that would actually be there.
    check('expanding the comments box is written to settings now',
          NO.load_settings().get('editor_comments_expanded') is True)
    _comment_btns[0].invoke()
    app.update()
    check('and collapsing it is written too',
          NO.load_settings().get('editor_comments_expanded') is False)
    # The read side, on a throwaway widget for the same reason as above: a
    # second window would mean two Tk interpreters at once.
    NO.save_setting('editor_comments_expanded', True)
    _c_host = tk.Frame(app)
    _c_text = tk.Text(_c_host, height=4)
    _c_text.pack()
    app._add_text_resize_toggle(_c_host, _c_text, compact=4, expanded=12,
                                remember_key='editor_comments_expanded')
    check(f'a comments box built while the stored choice is "expanded" opens '
          f'expanded ({_rows(_c_text)} rows)', _rows(_c_text) == 12)
    _c_host.destroy()
    # THE CONTROL, so the check above is not just reading a default: the same
    # build with the choice stored as collapsed must open compact.
    NO.save_setting('editor_comments_expanded', False)
    _c_host2 = tk.Frame(app)
    _c_text2 = tk.Text(_c_host2, height=4)
    _c_text2.pack()
    app._add_text_resize_toggle(_c_host2, _c_text2, compact=4, expanded=12,
                                remember_key='editor_comments_expanded')
    check(f'and one built while it is "collapsed" opens compact '
          f'({_rows(_c_text2)} rows)', _rows(_c_text2) == 4)
    _c_host2.destroy()
    # The two boxes must not share one key, or expanding either would expand
    # both at the next launch.
    NO.save_setting('editor_comments_expanded', True)
    NO.save_setting('editor_body_expanded', False)
    _s = NO.load_settings()
    check('the two boxes remember separately',
          _s.get('editor_comments_expanded') is True
          and _s.get('editor_body_expanded') is False)
    NO.save_setting('editor_comments_expanded', False)
app.update()

# ---- BOTH TEXT BOXES USE THE FULL WIDTH ----
# The Expand toggle used to call pack_configure(expand=False) on the box it
# was given. Both boxes are packed with side="left", where expand hands out
# horizontal space -- so it never affected the height it was meant to control,
# and left the box at its default eighty characters inside a much wider frame.
# The text then wrapped halfway across with no way to reach the rest, and
# deleting a character did not reflow it, because the box really was that
# narrow. Measured at the time: 752px of 1027px for the body, 672px for
# comments.
_resize(1400, 900)

for _name, _box in (('the body box', app.body_text),
                    ('the comments box', app.comments_text)):
    _frame_w = _box.master.winfo_width()
    _unused = _frame_w - _box.winfo_width()
    # A scrollbar sits beside each one, so a small remainder is expected.
    check(f'{_name} fills its frame ({_box.winfo_width()}px of {_frame_w}px)',
          _unused <= 25)

# The pixel comparison above can be fooled: a box left at its default eighty
# characters is about 700px, and a frame can happen to be about that too. The
# invariant behind it cannot. Both boxes are packed with side="left", where
# expand is what hands out horizontal space -- without it the box can never
# fill its frame at any window size, whatever this particular window measures.
for _name, _box in (('the body box', app.body_text),
                    ('the comments box', app.comments_text)):
    _info = _box.pack_info()
    check(f'{_name} is packed to take the width it is given '
          f'(side={_info["side"]}, expand={_info["expand"]})',
          str(_info['side']) == 'left' and str(_info['expand']) in ('1', 'True'))

# And still does after being expanded and collapsed again, which is when the
# packing was being changed out from under it.
app.body_resize_btn.invoke()
app.update(); app.update_idletasks()
check(f'the body box still fills its frame while expanded '
      f'({app.body_text.winfo_width()}px)',
      app.body_text.master.winfo_width() - app.body_text.winfo_width() <= 25)
app.body_resize_btn.invoke()
app.update(); app.update_idletasks()
check(f'and after collapsing again ({app.body_text.winfo_width()}px)',
      app.body_text.master.winfo_width() - app.body_text.winfo_width() <= 25)
check('expanding and collapsing leaves the packing alone',
      str(app.body_text.pack_info()['expand']) in ('1', 'True'))

# Deliberately not checked here: how far across the box the text runs before
# it wraps. Text always fills whatever box it is given -- with the bug it
# filled a 752px box perfectly well -- so that measurement cannot tell the
# two apart. What distinguishes them is the box against its frame, above.

# ---- SETTINGS QUICK WINS ----
# F1: the Backup panel says when the notes last left this computer --
# the export is the only copy outside the app's own folder.
app.show_settings_page()
app.toggle_settings_panel('backup')
app.update()
check('backup admits nothing was ever exported',
      'Never exported' in str(app.last_export_lbl.cget('text')))
app._export_state = {'current': 1, 'total': 1, 'done': True,
                     'error': None, 'save_path': 'X:/fake.zip'}
app._poll_export_progress()
app.update()
check('a finished export stamps the Backup line',
      'Last exported: 20' in str(app.last_export_lbl.cget('text')))
check('and remembers the stamp in settings',
      str(NO.get_setting('last_export_at', ''))[:2] == '20')
NO.save_setting('last_export_at', 'marker')
_origErrQW = app.show_error
app.show_error = lambda *a, **k: None
app._export_state = {'current': 0, 'total': 1, 'done': True,
                     'error': 'disk full', 'save_path': 'X:/fake.zip'}
app._poll_export_progress()
app.show_error = _origErrQW
check('a FAILED export leaves the stamp alone',
      NO.get_setting('last_export_at') == 'marker')

# F2: trash retention is a real setting now, honoured end to end.
app.toggle_settings_panel('trash')
app.update()
check('the trash panel names the current retention window',
      'Kept for 30 days' in str(app._trash_subtitle_lbl.cget('text')))
_ddQW = []


def _find_dd_qw(w):
    for ch in w.winfo_children():
        try:
            if (ch.winfo_class() == 'Label' and str(ch.cget('textvariable'))
                    == str(app.trash_retention_var)):
                _ddQW.append(ch.master)
                return
        except Exception:
            pass
        _find_dd_qw(ch)


_find_dd_qw(app.settings_trash_panel)
_qa_click(_ddQW[0])
app.update()
_optQW = []


def _find_opt_qw(w):
    for ch in w.winfo_children():
        if ch.winfo_class() == 'Label' and str(ch.cget('text')) == '60 days':
            _optQW.append(ch)
        _find_opt_qw(ch)


_find_opt_qw(app._mini_popup)
_qa_click(_optQW[0])
app.update()
check('picking 60 days in the dropdown saves the setting',
      NO.get_setting('trash_retention_days') == 60)
check('the subtitle follows the choice',
      'Kept for 60 days' in str(app._trash_subtitle_lbl.cget('text')))
check('the purge window follows too', NO.trash_retention_days() == 60)
# A value no app writes is a window not known, and then nothing is purged:
# 'forever' used to read as 30, and 0 as one day -- purge almost everything.
NO.save_setting('trash_retention_days', 'forever')
check("a hand-edited 'forever' is a window not known",
      NO.trash_retention_days() is None)
NO.save_setting('trash_retention_days', 0)
check('zero days is a window not known -- never purge-everything',
      NO.trash_retention_days() is None)
import datetime as _dtQW
_oldQW = (_dtQW.datetime.now()
          - _dtQW.timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
_entryQW = {'id': 9990, 'title': 'old', 'deleted_at': _oldQW,
            'attachments': []}
NO.save_setting('trash_retention_days', 7)
_keptQW, _nQW = NO.purge_expired_trash([dict(_entryQW)], app.notes)
NO.save_setting('trash_retention_days', 30)
_keptQW2, _nQW2 = NO.purge_expired_trash([dict(_entryQW)], app.notes)
check('a 10-day-old entry purges under a 7-day window', _nQW == 1)
check('and survives under the 30-day default', _nQW2 == 0)

# ---- SHORTENING THE WINDOW ASKS, AND ONLY WHEN IT COSTS SOMETHING ----
# The dropdown used to save on the click. Pick "7 days" with notes in the
# trash from last month and they were destroyed at the next startup --
# their attached files with them -- with no dialog, while every other
# permanent deletion in this panel warns. Finding C-3.
#
# The count comes from the same function the purge acts on, so the
# question cannot name a number the purge will not deliver.
_rt_saved_trash = list(app.trash)
_rt_real_ask = app.ask_yes_no
_rt_asked = {}


def _rt_answer(reply):
    """Record the question and give a fixed answer. Recording matters as
    much as answering: what the dialog SAYS is half the fix."""
    def _ask(title, message, **kw):
        _rt_asked.clear()
        _rt_asked.update({'title': title, 'msg': message, 'kw': kw})
        return reply
    app.ask_yes_no = _ask


def _rt_days_ago(n):
    return (_dtQW.datetime.now()
            - _dtQW.timedelta(days=n)).strftime('%Y-%m-%d %H:%M:%S')


_RT_OLD = {'id': 9801, 'title': 'from last month',
           'deleted_at': _rt_days_ago(40),
           'attachments': [{'filename': 'a.txt', 'stored_as': 'a.txt'},
                           {'filename': 'b.txt', 'stored_as': 'b.txt'}]}
_RT_RECENT = {'id': 9802, 'title': 'yesterday',
              'deleted_at': _rt_days_ago(1), 'attachments': []}
_RT_BROKEN = {'id': 9803, 'title': 'no stamp', 'deleted_at': 'not a date',
              'attachments': []}
_RT_SERIES = {'id': 9804, 'title': 'standup', 'deleted_at': _rt_days_ago(40),
              'attachments': [], 'recurrence': {'freq': 'daily',
                                                'interval': 1}}
# Older than every window the dropdown offers. A lengthening fixture built
# from a 40-day-old note proves nothing: 40 is inside a 90-day window, so
# the doomed list is empty and the "is this shorter?" test never has to
# hold. This one stays expired at 90 days, so dropping that test really
# does produce a question about a change that destroys nothing new.
_RT_ANCIENT = {'id': 9805, 'title': 'from last year',
               'deleted_at': _rt_days_ago(200), 'attachments': []}
# Twelve hours, not one day: the clamp turns a previewed 0 into a 1, and
# only an entry INSIDE one day can tell those apart. A day-old entry sits
# exactly on the boundary and reads as expired either way.
_RT_HOURS = {'id': 9806, 'title': 'this morning',
             'deleted_at': (_dtQW.datetime.now()
                            - _dtQW.timedelta(hours=12)
                            ).strftime('%Y-%m-%d %H:%M:%S'),
             'attachments': []}
# Past the 365-day ceiling, which is the only way to see the ceiling: a
# 40-day-old note is inside both 365 and 10000, so comparing those two
# windows on it returns zero twice and proves nothing.
_RT_BEYOND = {'id': 9807, 'title': 'ancient history',
              'deleted_at': _rt_days_ago(400), 'attachments': []}


def _rt_setup(entries, retention):
    """Put the panel in a stated state and say so -- the checks below are
    only meaningful because the window really is `retention` and the trash
    really holds these entries."""
    NO.save_setting('trash_retention_days', retention)
    app.trash = [dict(e) for e in entries]
    app.toggle_settings_panel('trash')
    app.update()
    _rt_asked.clear()
    return (NO.trash_retention_days() == retention
            and str(app.trash_retention_var.get()) == '%d days' % retention)


def _rt_pick(label_text):
    """Open the retention dropdown and click an option, through the widgets
    the app drew -- never by calling set_retention here."""
    _rt_btn = []

    def _rt_find_btn(w):
        for ch in w.winfo_children():
            try:
                if (ch.winfo_class() == 'Label'
                        and str(ch.cget('textvariable'))
                        == str(app.trash_retention_var)):
                    _rt_btn.append(ch.master)
                    return
            except Exception:
                pass
            _rt_find_btn(ch)

    _rt_find_btn(app.settings_trash_panel)
    if not _rt_btn:
        return False
    _qa_click(_rt_btn[0])
    app.update()
    _rt_opt = []

    def _rt_find_opt(w):
        for ch in w.winfo_children():
            if (ch.winfo_class() == 'Label'
                    and str(ch.cget('text')) == label_text):
                _rt_opt.append(ch)
            _rt_find_opt(ch)

    _rt_pop = getattr(app, '_mini_popup', None)
    if _rt_pop is None or not _rt_pop.winfo_exists():
        return False
    _rt_find_opt(_rt_pop)
    if not _rt_opt:
        return False
    _qa_click(_rt_opt[0])
    app.update()
    return True


# A question nobody needs teaches people to dismiss questions, so the
# silent cases are checks in their own right.
check('retention: fixture is 30 days with an empty trash', _rt_setup([], 30))
_rt_answer(False)
check('retention: the dropdown offers 7 days', _rt_pick('7 days'))
check('retention: shortening with an empty trash asks nothing', not _rt_asked)
check('retention: ...and still saves the shorter window',
      NO.trash_retention_days() == 7)

check('retention: fixture is 30 days with one recent note',
      _rt_setup([_RT_RECENT], 30))
_rt_answer(False)
_rt_pick('14 days')
check('retention: shortening past nothing old enough asks nothing',
      not _rt_asked)
check('retention: ...and saves', NO.trash_retention_days() == 14)

check('retention: fixture is 7 days with a note older than every window',
      _rt_setup([_RT_ANCIENT], 7)
      and len(NO.trash_entries_past_window([_RT_ANCIENT], 90)) == 1)
_rt_answer(False)
_rt_pick('90 days')
check('retention: lengthening never asks, even with notes already expired',
      not _rt_asked)
check('retention: ...and saves', NO.trash_retention_days() == 90)

# The case that destroys something.
check('retention: fixture is 30 days with a 40-day-old note carrying 2 files',
      _rt_setup([_RT_OLD, _RT_RECENT], 30))
_rt_answer(False)
check('retention: the dropdown offers 7 days again', _rt_pick('7 days'))
check('retention: shortening past something old DOES ask', bool(_rt_asked))
check('retention: the question counts only what would go',
      'holds 1 note older than 7 days' in _rt_asked.get('msg', ''))
check('retention: the question names both windows',
      'for 7 days instead of 30' in _rt_asked.get('msg', ''))
check('retention: the question says when it happens',
      'the next time the app starts' in _rt_asked.get('msg', ''))
check('retention: the question names the attached files going with them',
      'along with 2 attached files' in _rt_asked.get('msg', ''))
check("retention: the question says it can't be undone",
      "This can't be undone" in _rt_asked.get('msg', ''))
check('retention: it warns like the other permanent deletions in this panel',
      _rt_asked.get('kw', {}).get('icon') == 'warning'
      and _rt_asked.get('kw', {}).get('default') == 'no')
check('retention: answering No leaves the setting alone',
      NO.trash_retention_days() == 30)
check('retention: answering No puts the label back',
      str(app.trash_retention_var.get()) == '30 days')
check('retention: answering No leaves the subtitle alone',
      'Kept for 30 days' in str(app._trash_subtitle_lbl.cget('text')))

check('retention: fixture is 30 days again', _rt_setup([_RT_OLD, _RT_RECENT], 30))
_rt_answer(True)
_rt_pick('7 days')
check('retention: answering Yes saves the shorter window',
      NO.trash_retention_days() == 7)
check('retention: answering Yes moves the label',
      str(app.trash_retention_var.get()) == '7 days')
check('retention: answering Yes moves the subtitle',
      'Kept for 7 days' in str(app._trash_subtitle_lbl.cget('text')))


def _rt_row_lines():
    out, stack = [], [app.settings_trash_panel]
    while stack:
        w = stack.pop()
        try:
            if w.winfo_class() == 'Label' and 'left' in str(w.cget('text')):
                out.append(str(w.cget('text')))
        except Exception:
            pass
        stack.extend(w.winfo_children())
    return out


# Every row quotes the window too. Only the subtitle followed the choice:
# yesterday's note went on saying "29 day(s) left" under a 7-day window
# until the panel was opened again (2026-10-26). Asked of the app rather
# than written as 6: on the day the clocks spring forward, "a day ago" by
# the wall clock is 23 real hours, and the row rightly says 7.
_rt_left = app._days_left_in_trash(_RT_RECENT['deleted_at'])
check("retention: ...and a row's days left follow the new window at once",
      _rt_left in (6, 7)
      and any('%d day(s) left' % _rt_left in t for t in _rt_row_lines())
      and not any('%d day(s) left' % (_rt_left + 23) in t
                  for t in _rt_row_lines()))

# The preview and the purge must be the same judgement. A dialog that
# counts with one rule while the purge deletes by another is a dialog
# that lies.
check('retention: fixture is 30 days with a mixed trash',
      _rt_setup([_RT_OLD, _RT_RECENT, _RT_BROKEN, _RT_SERIES], 30))
_rt_answer(False)
_rt_pick('7 days')
check('retention: the question counts both old ones',
      'holds 2 notes older than 7 days' in _rt_asked.get('msg', ''))
check('retention: an unreadable deleted_at is not counted',
      'holds 3' not in _rt_asked.get('msg', ''))
check('retention: a repeating series in the trash is named',
      'repeating series' in _rt_asked.get('msg', ''))
NO.save_setting('trash_retention_days', 7)
_rt_previewed = len(NO.trash_entries_past_window(app.trash, 7))
_rt_kept, _rt_purged = NO.purge_expired_trash([dict(e) for e in app.trash],
                                              app.notes)
check('retention: the preview and the purge remove the same number',
      _rt_previewed == _rt_purged == 2)
check('retention: the purge keeps the unreadable stamp',
      any(e.get('id') == 9803 for e in _rt_kept))
check('retention: the preview of the CURRENT window matches the purge too',
      len(NO.trash_entries_past_window(app.trash)) == _rt_purged)

# The preview clamps a window the same way the stored one is clamped, so
# it can never be judged by looser arithmetic than what gets applied.
check('retention: a previewed 0 days is clamped to 1, like a stored one',
      len(NO.trash_entries_past_window([_RT_HOURS], 0)) == 0)
check('retention: a previewed nonsense window falls back to the default',
      len(NO.trash_entries_past_window([_RT_OLD], 'forever')) == 1
      and len(NO.trash_entries_past_window([_RT_BEYOND], 'forever')) == 1
      and len(NO.trash_entries_past_window([_RT_RECENT], 'forever')) == 0)
check('retention: a window past the ceiling is held at 365 days',
      len(NO.trash_entries_past_window([_RT_BEYOND], 10000)) == 1)
# WHICH entries, not just how many. A count alone is satisfied by the
# wrong answer: invert the window comparison and this fixture still yields
# one doomed entry, just the other one.
_rt_doomed_ids = [e.get('id')
                  for e in NO.trash_entries_past_window(
                      [_RT_OLD, _RT_RECENT, _RT_HOURS], 7)]
check('retention: the preview names the expired entry, not merely a count',
      _rt_doomed_ids == [9801])

# ---- A WINDOW NOT KNOWN: SAID, KEPT, AND CHOSEN AGAIN ----
# An unreadable settings.json leaves its marker (load_settings). The panel
# must say nothing is removed, and the first choice is a shorter one than
# "keep everything", so it asks about what it would remove.
_rt_said = []
_rt_real_info = app.show_info
app.show_info = lambda title, msg, *a, **k: _rt_said.append(msg)
NO.save_setting(NO.TRASH_WINDOW_UNKNOWN, True)
app.announce_startup_changes()
check('window not known: the next start says the Trash keeps everything',
      any('Nothing will be removed from the Trash' in m for m in _rt_said))
_rt_said.clear()
app.announce_startup_changes()
check('window not known: ...and says it once',
      not any('Nothing will be removed' in m for m in _rt_said)
      and NO.trash_retention_days() is None)
# The start's '(earlier text)' notes are said for both reasons, a day the
# note deleted among them: round 21's were said to be of days holding text
# of their own. The phone's line is the same.
_rt_said.clear()
app._set_aside_at_start = 1
app.announce_startup_changes()
app._set_aside_at_start = 0
check('the start says why earlier text became a note: other text there, or the day deleted',
      any('those days now show other text, or were deleted' in m
          and 'kept as 1 note of its own' in m for m in _rt_said))
app.show_info = _rt_real_info
app.trash = [dict(_RT_ANCIENT), dict(_RT_RECENT)]
app.toggle_settings_panel('trash')
app.update()
check('window not known: the panel says nothing is removed automatically',
      'nothing is removed automatically'
      in str(app._trash_subtitle_lbl.cget('text')))
check('window not known: the dropdown asks for a choice, names no number',
      str(app.trash_retention_var.get()) == 'Choose…')
check('window not known: a row names no days left',
      app._days_left_in_trash(_RT_ANCIENT['deleted_at']) is None)
_rt_answer(False)
_rt_pick('90 days')
check('window not known: choosing asks about what it would now remove',
      'holds 1 note older than 90 days' in _rt_asked.get('msg', ''))
check('window not known: ...with no "instead of" a window nobody knows',
      'instead of' not in _rt_asked.get('msg', ''))
check('window not known: answering No keeps it not known, and the label',
      NO.trash_retention_days() is None
      and str(app.trash_retention_var.get()) == 'Choose…')
_rt_answer(True)
_rt_pick('90 days')
check('window not known: answering Yes chooses 90 days and forgets the marker',
      NO.trash_retention_days() == 90
      and NO.TRASH_WINDOW_UNKNOWN not in NO.load_settings())
check('window not known: ...and the subtitle names the window again',
      'Kept for 90 days' in str(app._trash_subtitle_lbl.cget('text')))

app.ask_yes_no = _rt_real_ask
app.trash = list(_rt_saved_trash)
NO.save_setting('trash_retention_days', 30)
app.update()

# F3: the keyboard-shortcut reference exists and lists what is bound.
app.toggle_settings_panel('shortcuts')
app.update()
_txtQW = []


def _walk_qw(w):
    for ch in w.winfo_children():
        try:
            _txtQW.append(str(ch.cget('text')))
        except Exception:
            pass
        _walk_qw(ch)


_walk_qw(app.settings_shortcuts_panel)
_allQW = ' | '.join(_txtQW)
check('the shortcuts panel lists the formatting four',
      all(k in _allQW for k in ('Ctrl+B', 'Ctrl+I', 'Ctrl+U', 'Ctrl+D')))
check('and the undiscoverable rest',
      all(k in _allQW for k in ('Ctrl+Shift+V', 'Page Up', 'Home',
                                'Shift+Tab')))

# The page promises it holds everything the keyboard can do, and the
# promise was broken once: the note list's keys shipped in 0.81.199 and
# nobody added their rows, so the page and the user guide both went on
# claiming completeness they no longer had. Asking for the three names
# would only pin THIS omission. So this asks the LIST what it binds -- the
# cards are a drawing, and the list's canvas holds their keys -- and
# requires every answer to be named here: a key bound later with no row
# fails at the first check, and one that is named but not drawn fails at
# the second.
_QW_NOT_KEYS = {'<Button-1>', '<Button-3>', '<Button-2>', '<Enter>',
                '<Leave>', '<FocusIn>', '<FocusOut>', '<Motion>',
                '<MouseWheel>', '<Double-Button-1>', '<Configure>',
                '<B1-Motion>', '<ButtonRelease-1>'}
# Spelled the way Tk reports them back, not the way they were bound:
# bind('<Return>') is read back as '<Key-Return>', and this check was
# written with the binding spelling and caught its own mistake.
_QW_KEY_NAMES = {'<Key-Return>': 'Enter', '<Key-space>': 'Space',
                 '<Key-Down>': 'Down', '<Key-Up>': 'Up',
                 '<Key-Left>': 'Left', '<Key-Right>': 'Right',
                 '<Alt-Key-Down>': 'Alt+Down', '<Alt-Key-Up>': 'Alt+Up',
                 '<Key-Escape>': 'Escape',
                 '<Shift-Key-F10>': 'Shift+F10',
                 '<Key-App>': 'menu key', '<Key-Menu>': 'menu key'}
# A check that cannot find its subject must fail rather than pass on an
# empty list -- the shape of every check that has quietly stopped working.
check('a note card is on screen to ask about', bool(app._card_order()))
_qw_bound = [s for s in app.canvas.bind() if s not in _QW_NOT_KEYS]
_qw_unnamed = [s for s in _qw_bound if s not in _QW_KEY_NAMES]
check('every key the note list binds has a name here (unnamed: %s)'
      % _qw_unnamed, bool(_qw_bound) and _qw_unnamed == [])
_qw_missing = [s for s in _qw_bound
               if s in _QW_KEY_NAMES and _QW_KEY_NAMES[s] not in _allQW]
check('...and every one of them is on the shortcuts page (missing: %s)'
      % _qw_missing, _qw_missing == [])
# A checklist item's keys live on a tag every row's tick box carries, so
# they are asked of that tag -- and named in the Checklist group itself:
# Alt+Up is on the page already, for the note list.
_qw_cl_bound = [s for s in app.bind_class('ChecklistBox')
                if s not in _QW_NOT_KEYS]
_qw_cl_group = ' '.join(k for title, rows in app.SHORTCUT_GROUPS
                        if title.startswith('Checklist') for k, _d in rows)
check('every key a checklist item binds is named in the Checklist group '
      '(bound: %s)' % _qw_cl_bound,
      bool(_qw_cl_bound)
      and all(_QW_KEY_NAMES.get(s, s) in _qw_cl_group for s in _qw_cl_bound))

# Every nav entry draws a real glyph -- a section registered without a
# branch in _draw_icon would show a BLANK icon and nothing would error
# (exactly how the shortcuts section first shipped, caught in review).
_blankQW = [k for k, cv in app._settings_nav_icons.items()
            if not cv.find_withtag('glyph')]
check('every settings nav entry draws a glyph (blank: %s)' % _blankQW,
      _blankQW == [])

# F4: deleting a template says plainly that nothing comes back.
_askedQW = {}
_ansQW = {'v': False}
_origAskQW = app.ask_yes_no


def _fake_ask_qw(title, msg, **kw):
    _askedQW['title'] = title
    _askedQW['msg'] = msg
    return _ansQW['v']


app.ask_yes_no = _fake_ask_qw
app.templates = [NO.normalize_template({'name': 'Trial QW', 'body': 'x'})]
_holdQW = tk.Toplevel(app)
_frameQW = tk.Frame(_holdQW)
_frameQW.pack()
app._build_template_row(_frameQW, app.templates[0], lambda: None)
app.update()
_trashBtnQW = []


def _find_trash_qw(w):
    for ch in w.winfo_children():
        if getattr(ch, '_icon_kind', None) == 'trash':
            _trashBtnQW.append(ch)
        _find_trash_qw(ch)


_find_trash_qw(_frameQW)
_qa_click(_trashBtnQW[0])
app.update()
check('the delete ask says templates skip the Trash',
      "don't go to the Trash" in str(_askedQW.get('msg', ''))
      and "can't be undone" in str(_askedQW.get('msg', '')))
check('No keeps the template', len(app.templates) == 1)
_ansQW['v'] = True
_qa_click(_trashBtnQW[0])
app.update()
check('Yes deletes it for good', len(app.templates) == 0)
app.ask_yes_no = _origAskQW
_holdQW.destroy()

# ---- CATEGORY panel flows (coverage-lift #2) ----
# add / recolour / rename had never been driven through the real rows.
_CC6 = NO.CATEGORY_COLORS
_catf = tk.Frame(app)
app._build_settings_categories_panel(_catf)
app.update()
def _entries6(root):
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Entry):
                out.append(c)
            walk(c)
    walk(root)
    return out
def _btn6(root, txt):
    hit = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Button) and txt in str(c.cget('text')):
                hit.append(c)
            walk(c)
    walk(root)
    return hit[0] if hit else None
_new_entry = _entries6(_catf)[-1]
_new_entry.insert(0, 'Projects')
_btn6(_catf, '+ Add').invoke()
app.update()
check('adding a category through the panel lands in the palette map',
      'Projects' in _CC6
      and 'Projects' in NO.get_setting('categories', {}))

# The row rebuilt on redraw — find the Projects swatch and recolour it.
def _row_of6(root, name):
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label) and str(c.cget('text')).startswith(name):
                return c.master
            r = walk(c)
            if r is not None:
                return r
        return None
    return walk(root)
_prow = _row_of6(_catf, 'Projects')
check('the new category has its own row', _prow is not None)
_old_col = _CC6['Projects']
_swatch6 = next(c for c in _prow.winfo_children()
                if isinstance(c, tk.Frame)
                and str(c.cget('cursor')) == 'hand2')
_qa_click(_swatch6)
app.update()
_pal6 = [c for c in app._mini_popup.winfo_children()] if app._mini_popup else []
def _canvases6(root):
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Canvas) and str(c.cget('cursor')) == 'hand2':
                out.append(c)
            walk(c)
    walk(root)
    return out
_sw6 = _canvases6(app._mini_popup)
# The colour is a DRAWN item on each swatch canvas; pick one whose fill
# genuinely differs from the current colour (one click closes the
# palette, so there is no second chance).
def _fill6(c):
    items = c.find_all()
    return str(c.itemcget(items[0], 'fill')) if items else ''
_target6 = next(c for c in _sw6 if _fill6(c).startswith('#')
                and _fill6(c) != _old_col)
_want6 = _fill6(_target6)
_qa_click(_target6)
app.update()
check('recolouring through the swatch palette stores the clicked colour',
      _CC6.get('Projects') == _want6
      and NO.get_setting('categories', {}).get('Projects') == _want6)

# What a rename carries besides the notes: the note open in the editor,
# the templates, the Trash, a folded group, and its place among the
# groups. Only the notes were renamed -- the editor's box fell back to
# General and the next save filed the open note there, and a note
# restored from the Trash brought the old name back.
_rn_kept6 = (list(app.notes), list(app.trash), list(app.templates),
             set(app.collapsed_groups))
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Budget', 'body': 'x',
                                'category': 'Projects'})]
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
app.templates = [NO.normalize_template({'name': 'Weekly', 'category': 'Projects'})]
NO.save_templates(app.templates)
app.trash = [dict(NO.normalize_note({'id': 2, 'title': 'Old', 'body': 'x',
                                     'category': 'Projects'}),
                  deleted_at='2026-09-30 10:00:00')]
NO.save_trash(app.trash)
app.collapsed_groups = {'Projects'}
# A category AFTER the renamed one: added last, 'Projects' was already at
# the end, so "moved to the end" and "kept its place" read the same and the
# place check could not fail (a mutant restoring the move survived it).
_CC6['ZAfterProjects'] = '#556677'
_rn_order6 = list(_CC6)
check('fixture: the category about to be renamed is not the last one',
      _rn_order6.index('Projects') < len(_rn_order6) - 1)

# Rename through the pencil's inline editor.
_prow = _row_of6(_catf, 'Projects')
# children order = creation order: the pencil canvas is created before
# the trash one, so [0] is rename (touring them would hit trash's
# delete). The inline editor's <Return> needs REAL focus first, or the
# generated key is dropped (the documented class).
_pencil6 = [c for c in _prow.winfo_children() if isinstance(c, tk.Canvas)][0]
_qa_click(_pencil6)
app.update()
# The inline editor is a mini-POPUP (entry + Save button), not a row
# child — drive it through its own Save button, no focus needed.
_renamed = False
_ipop = app._mini_popup
if _ipop is not None and _ipop.winfo_exists():
    _ientry = _entries6(_ipop)[0]
    _ientry.delete(0, 'end')
    _ientry.insert(0, 'ProjectsX')
    _btn6(_ipop, 'Save').invoke()
    app.update()
    _renamed = 'ProjectsX' in _CC6 and 'Projects' not in _CC6
check('renaming through the inline editor moves the category',
      _renamed and 'ProjectsX' in NO.get_setting('categories', {}))
check('...the note open in the editor goes with it',
      app.category_var.get() == 'ProjectsX')
app._flush_autosave(); app.update()
check('...so its next save does not file it under General',
      app.find_note(1)['category'] == 'ProjectsX')
check('...templates and the Trash go with it too',
      app.templates[0]['category'] == 'ProjectsX'
      and app.trash[0]['category'] == 'ProjectsX')
check('...a folded group stays folded, under its new name',
      app.collapsed_groups == {'ProjectsX'}
      and NO.get_setting('collapsed_groups', []) == ['ProjectsX'])
check('...and the category keeps its place among the groups',
      list(_CC6).index('ProjectsX') == _rn_order6.index('Projects'))
app.new_note(); app.update()
_CC6.pop('ZAfterProjects', None)
NO.persist_categories()
app.notes, app.trash, app.templates, app.collapsed_groups = _rn_kept6
app.save_notes(); NO.save_trash(app.trash); NO.save_templates(app.templates)
NO.save_setting('collapsed_groups', sorted(app.collapsed_groups))

# ---- Add and Rename refuse what the loader will not keep ----
# Both doors took any length, and load_categories drops a name over the
# ceiling: the category worked all day, and the next launch filed every
# note under it into General. The doors now ask the loader's own rule.
_catwarn6 = []
_real_catwarn6 = app.show_warning
app.show_warning = lambda t, m, **k: _catwarn6.append((t, m))
_long6 = 'L' * (NO.MAX_CATEGORY_NAME + 1)
_new_entry = _entries6(_catf)[-1]
_new_entry.delete(0, 'end')
_new_entry.insert(0, _long6)
_btn6(_catf, '+ Add').invoke()
app.update()
check('Add refuses a category name longer than the app keeps',
      _long6 not in _CC6
      and _long6 not in NO.get_setting('categories', {}))
check('...and says why, naming the limit',
      bool(_catwarn6) and str(NO.MAX_CATEGORY_NAME) in _catwarn6[-1][1])
_catwarn6.clear()
_prow = _row_of6(_catf, 'ProjectsX')
_pencil6 = [c for c in _prow.winfo_children() if isinstance(c, tk.Canvas)][0]
_qa_click(_pencil6)
app.update()
_kept_name6 = False
_ipop = app._mini_popup
if _ipop is not None and _ipop.winfo_exists():
    _ientry = _entries6(_ipop)[0]
    _ientry.delete(0, 'end')
    _ientry.insert(0, _long6)
    _btn6(_ipop, 'Save').invoke()
    app.update()
    _kept_name6 = 'ProjectsX' in _CC6 and _long6 not in _CC6
    app._dismiss_mini_popup()
    app.update()
check('Rename refuses it too, and the category keeps its name',
      _kept_name6 and bool(_catwarn6)
      and str(NO.MAX_CATEGORY_NAME) in _catwarn6[-1][1])
app.show_warning = _real_catwarn6

for _nm in ('Projects', 'ProjectsX'):
    _CC6.pop(_nm, None)
NO.persist_categories()
_catf.destroy(); app.update()

# ---- The attachment ceiling refuses; it does not eat files ----
# MAX_ATTACHMENTS exists because a note carrying thousands of records is
# a way to make the app unopenable. normalize_note enforces it by
# TRUNCATING, which is right for a hostile share code and wrong for a
# person adding their own files: they were copied to disk, listed in the
# editor, and then silently dropped on the next load. The creation side
# refuses instead, and says why.
_cap6 = NO.MAX_ATTACHMENTS
app.new_note(); app.update()
app.current_attachments = [{'filename': 'f%d.txt' % i,
                            'stored_as': 'f%d.txt' % i}
                           for i in range(_cap6)]
app.refresh_attachments_list(); app.update()
_warned6 = []
_real_warn6 = app.show_warning
app.show_warning = lambda t, m, **k: _warned6.append((t, m))
fd.askopenfilenames = lambda **k: (tmp_file,)
try:
    app.add_attachment()
    app.update()
finally:
    app.show_warning = _real_warn6
check('a full note refuses another file instead of losing it',
      len(app.current_attachments) == _cap6 and len(_warned6) == 1)
check('...and the message says how many a note can hold',
      _warned6 and str(_cap6) in _warned6[0][1])

# One short of the ceiling, a multi-file pick asks before taking only
# what fits -- and answering No takes none of them.
app.current_attachments = app.current_attachments[:_cap6 - 1]
app.refresh_attachments_list(); app.update()
_asked6 = []
_real_ask6 = app.ask_yes_no
app.ask_yes_no = lambda t, m, **k: (_asked6.append((t, k)), False)[1]
fd.askopenfilenames = lambda **k: (tmp_file, tmp_file, tmp_file)
try:
    app.add_attachment()
    app.update()
finally:
    app.ask_yes_no = _real_ask6
check('picking more files than fit asks first, with No pre-selected',
      len(_asked6) == 1 and _asked6[0][1].get('default') == 'no')
# A question, not a warning: nothing is deleted, and a warning dresses its
# Yes in the dark red fill the app keeps for what cannot be undone.
check('...asked as a question, so its Yes is not the red of a deletion',
      len(_asked6) == 1 and _asked6[0][1].get('icon') != 'warning')
check('...and answering No attaches none of them',
      len(app.current_attachments) == _cap6 - 1)

# Saying yes takes exactly the room that was left.
app.ask_yes_no = lambda *a, **k: True
try:
    app.add_attachment()
    app.update()
finally:
    app.ask_yes_no = _real_ask6
check('answering Yes attaches exactly what fits, no more',
      len(app.current_attachments) == _cap6)
# ...and to the note it asked about: a Yes given after the editor moved on
# to another note attaches nothing to the note that opened meanwhile.
app.current_attachments = app.current_attachments[:_cap6 - 1]
app.refresh_attachments_list(); app.update()
_ad_note_before = app.selected_note_id
_ad_other = []


def _ad_answer(*a, **k):
    app.selected_note_id = (_ad_note_before or 0) + 999
    app.current_attachments = _ad_other
    return True


app.ask_yes_no = _ad_answer
fd.askopenfilenames = lambda **k: (tmp_file, tmp_file, tmp_file)
try:
    app.add_attachment()
    app.update()
finally:
    app.ask_yes_no = _real_ask6
    app.selected_note_id = _ad_note_before
check('a Yes given after the editor moved on attaches nothing to the note '
      'that opened meanwhile (%d)' % len(_ad_other), _ad_other == [])
app.current_attachments = []
app.refresh_attachments_list()
app.new_note(); app.update()


# ---- FIELD CASES AUTOMATED (test plan 107, 110, 118, 121, 125) ----
# The expensive end of the plan: each is two features meeting, which is
# where this project has lost most of its bugs.
import types as _types6, json as _json6, io as _io6
_b5_saved_notes = list(app.notes)
_b5_saved_trash = list(app.trash)

# ============================================================
# RECOVERING SEVERAL NOTES IS NOT FORTY CLICKS (C-14)
# ============================================================
# You could restore one note at a time or destroy all of them at once,
# and nothing in between -- the only bulk gesture on the screen was the
# irreversible one. And two notes both called "Notes" had nothing to
# tell them apart, so the safe answer was to restore both.
app.trash = [{'id': 5000 + i, 'title': 'Notes', 'body': 'body number %d' % i,
              'category': 'General',
              'deleted_at': '2026-02-%02d 00:00:00' % (i + 1)}
             for i in range(4)]
app.notes = []
app.save_notes()
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()


def _c14_widgets(root, kind, acc=None):
    acc = [] if acc is None else acc
    for child in root.winfo_children():
        if isinstance(child, kind):
            acc.append(child)
        _c14_widgets(child, kind, acc)
    return acc


_c14_ticks = _c14_widgets(app.settings_trash_panel, tk.Checkbutton)
check(f'every trash row carries a tick box ({len(_c14_ticks)} for 4 rows)',
      len(_c14_ticks) == 4)
# The preview the Duplicates panel already gives its rows, on the screen
# where the question "which of these two is which" is harder: a trashed
# note is not open anywhere.
_c14_hoverable = [w for w in _c14_widgets(app.settings_trash_panel, tk.Frame)
                  if '<Enter>' in w.bind()]
check(f'a trash row explains itself on hover ({len(_c14_hoverable)} rows '
      f'bound)', len(_c14_hoverable) >= 4)
# And the preview FLOATS rather than joining the panel. A Toplevel whose
# master is a widget appears in that widget's winfo_children(), so a
# preview parented to a row lands inside the panel's tree -- where
# everything that walks a panel meets it: a theme sweep, the wheel
# binding, and any check counting what is on screen.
#
# This is not hypothetical. It turned CI red on two pull requests while
# the same script passed on a desktop and on the local Linux image: qa3
# counts the trash rows by walking the panel, and on a headless display
# the pointer sits still over whatever is drawn under it, so one row's
# preview opened and was counted as an extra row. On a desktop the
# pointer is elsewhere and it never happened. This is the guard that
# would have caught it here.
_c14_labels_before = len(_c14_widgets(app.settings_trash_panel, tk.Label))
if _c14_hoverable:
    _c14_hoverable[0].event_generate('<Enter>', x=5, y=5)
    app.update()
    _c14_labels_after = len(_c14_widgets(app.settings_trash_panel, tk.Label))
    check(f'resting on a row does not add anything to the panel it floats '
          f'over ({_c14_labels_before} -> {_c14_labels_after})',
          _c14_labels_after == _c14_labels_before)
    _c14_tops = [w for w in _c14_widgets(app.settings_trash_panel, tk.Toplevel)]
    check(f'and no floating window is parented inside the panel '
          f'({len(_c14_tops)} found)', not _c14_tops)
    _c14_hoverable[0].event_generate('<Leave>')
    app.update()


def _c14_button(text):
    """Find a button by its words.

    Careful with "Restore": EVERY row carries one of those, and the first
    version of this looked for the bare word and kept finding a row's own
    button -- so it reported no bulk offer while one was on screen, and
    then invoked the wrong thing. The bulk one is the one that says
    "selected".
    """
    return next((b for b in _c14_widgets(app.settings_trash_panel, tk.Button)
                 if text.lower() in str(b.cget('text')).lower()), None)


# "selected" is on Delete N selected too since 2026-10-26: the bulk Restore
# is the one with the arrow, which no row's own Restore has.
_C14_RESTORE = '↩ restore'


check('no Restore-selected button while nothing is ticked',
      _c14_button(_C14_RESTORE) is None
      or not _c14_button(_C14_RESTORE).winfo_ismapped())
# Tick two of the four.
_c14_ticks[0].invoke(); _c14_ticks[2].invoke()
app.update()
_c14_restore = _c14_button(_C14_RESTORE)
check('ticking notes offers to restore them',
      _c14_restore is not None and _c14_restore.winfo_ismapped())
check(f'and the button says how many '
      f'({_c14_restore and str(_c14_restore.cget("text"))!r})',
      _c14_restore is not None and '2' in str(_c14_restore.cget('text')))
# THE CONTROL for the tick dict outliving its rows: redraw destroys every
# row, so a selection kept on the row itself would be silently lost by
# paging or by restoring anything.
_c14_kept = sum(1 for v in app._trash_sel.values() if v.get())
check('the ticks live on the panel, not on the rows that get destroyed',
      _c14_kept == 2)

# Read WHICH ones are ticked rather than assuming: the panel sorts newest
# first, so ticking the first and third rows is not ticking ids 5000 and
# 5002. The first version of this hardcoded that guess and failed on a
# correct app -- which is the whole reason to ask the state rather than
# predict it.
# The ticks are keyed by the entry's identity in the trash, not by its id
# alone (two entries can share an id -- see the check further down).
from noteorganizer.ui.settings_page import _trash_tick_key as _c14_key
_c14_picked = {k for k, v in app._trash_sel.items() if v.get()}
_c14_left = sorted(e['id'] for e in app.trash if _c14_key(e) not in _c14_picked)
# Identified by BODY, not by id, and that is not a workaround: restoring
# deliberately assigns a fresh id, because the trashed note's own may have
# been reused by a note created after it was deleted -- core/storage says
# so at the line that does it. All four of these are titled "Notes", which
# is the situation this row is about, so the body is the only thing that
# tells them apart -- exactly what the new hover preview shows a person.
_c14_want_bodies = sorted(e['body'] for e in app.trash
                          if _c14_key(e) in _c14_picked)
_c14_restore.invoke()
app.update()
check('restoring the ticked notes brings back exactly those two',
      len(app.notes) == 2 and len(app.trash) == 2)
check(f'and the two restored are the ones that were ticked '
      f'({_c14_want_bodies})',
      sorted(n['body'] for n in app.notes) == _c14_want_bodies)
check(f'while the untouched two are still in the trash ({_c14_left})',
      sorted(e['id'] for e in app.trash) == _c14_left)
_c14_after = _c14_button(_C14_RESTORE)
check('and the offer goes away once nothing is ticked',
      _c14_after is None or not _c14_after.winfo_ismapped())
# The destructive neighbour still works and still asks -- restoring must
# not have disturbed the one gesture this screen always had.
check('Empty trash is still there, and still wears the danger weight',
      _c14_button('Empty trash') is not None)
app.trash = []
app.notes = []
app.save_notes()

# Two Trash entries can share an id: a note's id is only its place in the
# notes file, handed out again after a delete -- delete the newest note,
# write another, delete that too. Keyed by the id alone, ticking one row
# ticked both, and "Restore selected" brought back a note nobody picked.
app.trash = [
    {'id': 2, 'title': 'Old draft', 'body': 'the old one', 'category': 'General',
     'deleted_at': '2026-09-20 10:00:00', 'uid': 'qa6-old-draft'},
    {'id': 2, 'title': 'Second draft', 'body': 'the new one',
     'category': 'General', 'deleted_at': '2026-09-21 10:00:00',
     'uid': 'qa6-second-draft'}]
NO.save_trash(app.trash)
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
_sid_ticks = _c14_widgets(app.settings_trash_panel, tk.Checkbutton)
check(f'fixture: two Trash rows sharing an id, a tick each ({len(_sid_ticks)})',
      len(_sid_ticks) == 2)


def _sid_ticked():
    return [int(app.getvar(str(t.cget('variable')))) for t in _sid_ticks]


_sid_picked = None
if len(_sid_ticks) == 2:
    _sid_titles = [str(l.cget('text'))
                   for l in _c14_widgets(_sid_ticks[0].master, tk.Label)]
    _sid_picked = next((t for t in ('Old draft', 'Second draft')
                        if any(t in s for s in _sid_titles)), None)
    _sid_ticks[0].invoke(); app.update()
_sid_btn = _c14_button(_C14_RESTORE)
check(f'ticking one of two rows that share an id ticks only that row '
      f'({_sid_ticked()}, {_sid_btn and str(_sid_btn.cget("text"))!r})',
      _sid_ticked() == [1, 0] and _sid_btn is not None
      and '1 selected' in str(_sid_btn.cget('text')))
if _sid_btn is not None:
    _sid_btn.invoke(); app.update()
check(f'...and Restore selected brings back only the ticked note ({_sid_picked})',
      _sid_picked is not None
      and [n['title'] for n in app.notes] == [_sid_picked]
      and [e['title'] for e in app.trash]
      == [t for t in ('Old draft', 'Second draft') if t != _sid_picked])
app.trash = []
app.notes = []
app.save_notes(); NO.save_trash(app.trash)

# ---- Select all, and Delete selected permanently ----
# Asked for by the owner (2026-10-26): keeping a few of a long Trash and
# deleting the rest, or restoring all of it, was a tick per row. Select all
# takes the whole Trash, the rows not drawn yet too -- paging hides nothing
# the way a filter does -- and the buttons name the count. 30 entries, so
# five wait under "Show more"; one shares its file with a living note, one
# carries a file of its own, one is a series.
_sa_ask = app.ask_yes_no
_sa_files = {'sa_shared.txt': None, 'sa_own.txt': None}
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
for _sa_name in _sa_files:
    _sa_files[_sa_name] = os.path.join(NO.ATTACHMENTS_DIR, _sa_name)
    with open(_sa_files[_sa_name], 'w') as _sa_fh:
        _sa_fh.write('x')
app.notes = [{'id': 1, 'title': 'Living', 'body': 'uses the shared file',
              'category': 'General', 'uid': 'sa-living',
              'attachments': [{'filename': 'a.txt', 'stored_as': 'sa_shared.txt'}]}]
app.save_notes()
app.trash = [{'id': 100 + i, 'title': 'Trashed %02d' % i, 'body': 'b%d' % i,
              'category': 'General', 'uid': 'sa-%d' % i,
              'deleted_at': '2026-10-%02d 09:00:00' % (1 + i % 25)}
             for i in range(30)]
app.trash[0]['attachments'] = [{'filename': 'a.txt', 'stored_as': 'sa_shared.txt'}]
app.trash[1]['attachments'] = [{'filename': 'o.txt', 'stored_as': 'sa_own.txt'}]
app.trash[2]['recurrence'] = {'freq': 'weekly'}
app.trash[2]['date'] = '2026-10-05'
NO.save_trash(app.trash)
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()


def _sa_ticked():
    return [int(app.getvar(str(t.cget('variable'))))
            for t in _c14_widgets(app.settings_trash_panel, tk.Checkbutton)]


def _sa_words(text):
    button = _c14_button(text)
    return str(button.cget('text')) if button is not None and button.winfo_ismapped() else None


def _sa_press(text):
    """Press the button whose words hold `text`. A button a mutant took away
    is a FAIL in the checks after it, never a crash before the footer."""
    button = _c14_button(text)
    if button is None or not button.winfo_ismapped():
        return False
    button.invoke()
    app.update()
    return True


_sa_btn = _c14_button('select all')
check('Select all is offered over a Trash that holds notes',
      _sa_btn is not None and _sa_btn.winfo_ismapped()
      and str(_sa_btn.cget('text')) == 'Select all')
check('fixture: a page of 25 rows drawn of the 30', len(_sa_ticked()) == 25)
_sa_press('select all')
check(f"Select all ticks every row drawn ({_sa_ticked().count(1)} of {len(_sa_ticked())})",
      _sa_ticked() and all(_sa_ticked()))
check(f"...and counts the rows not drawn yet ({_sa_words(_C14_RESTORE)!r}, "
      f"{_sa_words('permanently')!r})",
      _sa_words(_C14_RESTORE) == '↩ Restore 30 selected'
      and _sa_words('permanently') == 'Delete 30 selected permanently')
check('...and then offers Unselect all', _sa_words('select all') == 'Unselect all')
_sa_press('more')
check(f'the rows Show more draws come ticked ({len(_sa_ticked())} rows)',
      len(_sa_ticked()) == 30 and all(_sa_ticked()))
_sa_rows = _c14_widgets(app.settings_trash_panel, tk.Checkbutton)
if len(_sa_rows) > 3:
    _sa_rows[3].invoke(); app.update()
check(f"a row unticked by hand: Select all again, 29 counted ({_sa_words(_C14_RESTORE)!r})",
      _sa_words('select all') == 'Select all'
      and _sa_words(_C14_RESTORE) == '↩ Restore 29 selected')
_sa_press('select all')
check('Select all over a part-ticked Trash ticks the rest',
      all(_sa_ticked()) and _sa_words(_C14_RESTORE) == '↩ Restore 30 selected')
_sa_press('unselect all')
check('Unselect all clears every tick, and the buttons that act on them go',
      not any(_sa_ticked()) and _sa_words(_C14_RESTORE) is None
      and _sa_words('permanently') is None and _sa_words('select all') == 'Select all')

# A toast's Undo takes entries out of the Trash under the panel: the count
# follows what is still there.
if _sa_words('select all') == 'Select all':
    _sa_press('select all')
_sa_held = app.trash[-3:]
app.trash = app.trash[:-3]
app._refresh_open_trash_panel(); app.update()
check(f"entries an Undo took back leave the count ({_sa_words(_C14_RESTORE)!r})",
      _sa_words(_C14_RESTORE) == '↩ Restore 27 selected'
      and _sa_words('select all') == 'Unselect all')
app.trash = app.trash + _sa_held
NO.save_trash(app.trash)
app._refresh_open_trash_panel(); app.update()
if _sa_ticked() and all(_sa_ticked()):
    _sa_press('select all')

# Keep two, delete the rest: Select all, untick two, Delete selected.
_sa_press('select all')
_sa_keep = []
for _sa_tick in _c14_widgets(app.settings_trash_panel, tk.Checkbutton):
    _sa_title = ' '.join(str(l.cget('text')) for l in _c14_widgets(_sa_tick.master, tk.Label))
    if 'Trashed 05' in _sa_title or 'Trashed 06' in _sa_title:
        _sa_tick.invoke()
        _sa_keep.append(_sa_title)
app.update()
_rt_answer(False)
_rt_asked.clear()
_sa_press('permanently')
check(f"Delete selected asks first, naming the count and the file ({_rt_asked.get('msg', '')[:90]!r})",
      'Permanently delete 28 selected notes, along with 2 attached files?' in _rt_asked.get('msg', '')
      and "can't be undone" in _rt_asked.get('msg', '')
      and _rt_asked.get('kw', {}).get('default') == 'no')
check('...and names the series among them',
      'repeat' in _rt_asked.get('msg', '').lower())
check('...and answering No deletes nothing', len(app.trash) == 30)
_rt_answer(True)
_sa_press('permanently')
check(f"answering Yes deletes the 28 and keeps the two unticked ({[e['title'] for e in app.trash]})",
      sorted(e['title'] for e in app.trash) == ['Trashed 05', 'Trashed 06']
      and sorted(e['title'] for e in NO.load_trash()) == ['Trashed 05', 'Trashed 06'])
check('...a file a living note uses stays, one only the deleted used goes',
      os.path.exists(_sa_files['sa_shared.txt']) and not os.path.exists(_sa_files['sa_own.txt']))
check('...and nothing is left ticked, so nothing is offered',
      not any(_sa_ticked()) and _sa_words(_C14_RESTORE) is None and _sa_words('permanently') is None)

# Empty trash with rows ticked: the offers go with the rows.
_c14_ticks2 = _c14_widgets(app.settings_trash_panel, tk.Checkbutton)
if _c14_ticks2:
    _c14_ticks2[0].invoke(); app.update()
_sa_press('Empty trash')
check('Empty trash with a row ticked leaves no Restore, Delete or Select all over an empty Trash',
      app.trash == [] and _sa_words(_C14_RESTORE) is None
      and _sa_words('permanently') is None and _sa_words('select all') is None)
app.ask_yes_no = _sa_ask
if os.path.exists(_sa_files['sa_shared.txt']):
    os.remove(_sa_files['sa_shared.txt'])
app.notes = []
app.save_notes(); NO.save_trash(app.trash)

# Every redraw of Recently deleted bound a new handler on the frame that
# holds its rows -- a frame that outlives the redraw -- and Tk keeps a
# command for each one: one more per Restore, Delete, page or toast Undo
# while the panel was open, for good. The Categories list did the same
# on every rename, recolour and delete.
app.trash = [{'id': 6100 + i, 'title': 'Leak %d' % i, 'body': 'x',
              'category': 'General',
              'deleted_at': '2026-03-%02d 00:00:00' % (i + 1)} for i in range(3)]
NO.save_trash(app.trash)
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
_lk_redraw = app._trash_panel_redraw
_lk_clean, _lk_said = _qa_leaves_nothing_behind(app, _lk_redraw, 30)
check(f'redrawing Recently deleted leaves no Tcl command behind ({_lk_said})',
      _lk_clean)
_lk_canvas = app._active_panel_canvas
# The rows stand in chunks on the canvas (RowStack): the wheel on each chunk
# covers what lies between the rows, as it did on the one frame.
_lk_stack = getattr(_lk_canvas, '_row_stack', None)
_lk_chunks = ([c for g in _lk_stack.groups for c in g.chunks]
              if _lk_stack is not None else [])
_lk_rows = _lk_stack.rows() if _lk_stack is not None else []
check('...while the wheel still reaches the list and every row in it',
      bool(_lk_chunks) and all(c.bind('<MouseWheel>') for c in _lk_chunks)
      and len(_lk_rows) >= 3
      and all(r.bind('<MouseWheel>') for r in _lk_rows))
app.trash = []; NO.save_trash(app.trash)
# A hand-edited trash.json can hold a deleted_at that is not text (the
# backup import keeps text only): sorting it beside the dates, and showing
# it, raised, and Recently deleted did not open at all.
app.trash = [{'id': 6200, 'title': 'Odd number', 'body': 'x', 'category': 'General',
              'deleted_at': 5},
             {'id': 6201, 'title': 'Odd list', 'body': 'x', 'category': 'General',
              'deleted_at': [2026, 3, 1]},
             {'id': 6202, 'title': 'Plain date', 'body': 'x', 'category': 'General',
              'deleted_at': '2026-03-01 00:00:00'}]
_od_err = None
try:
    app._trash_panel_redraw(); app.update()
except Exception as _od_exc:   # noqa: BLE001 -- the check reports it
    _od_err = repr(_od_exc)
_od_canvas = app._active_panel_canvas
_od_rows = getattr(_od_canvas, '_row_stack', None)
_od_rows = _od_rows.groups[0] if _od_rows is not None else None


def _od_texts(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, tk.Label):
            out.append(str(c.cget('text')))
        out.extend(_od_texts(c))
    return out


_od_shown = [t for t in (_od_texts(_od_rows) if _od_rows is not None else [])
             if t in ('Odd number', 'Odd list', 'Plain date')]
check(f'a deleted_at that is not text still lets Recently deleted draw every '
      f'row ({_od_err}, {sorted(_od_shown)})',
      _od_err is None and sorted(_od_shown) == ['Odd list', 'Odd number', 'Plain date'])
# The day a note was deleted is shown as every date in the app is: day first.
_od_when = [t for t in (_od_texts(_od_rows) if _od_rows is not None else [])
            if t.startswith('deleted ')]
check(f'a Trash row says when it was deleted day first ({_od_when})',
      any(t.startswith('deleted 01.03.2026') for t in _od_when))
app.trash = []; NO.save_trash(app.trash)
# The Categories list: its redraw is the one each row is handed.
_lk_cat_redraws = []
_lk_real_cat_row = app._build_category_row
app._build_category_row = lambda parent, name, redraw: (
    _lk_cat_redraws.append(redraw), _lk_real_cat_row(parent, name, redraw))[1]
app.toggle_settings_panel('categories'); app.update()
del app._build_category_row
_lk_clean, _lk_said = (_qa_leaves_nothing_behind(app, _lk_cat_redraws[-1], 30)
                       if _lk_cat_redraws
                       else (False, 'no redraw was handed to a row'))
check(f'redrawing the Categories list leaves no Tcl command behind '
      f'({_lk_said})', _lk_clean)
# The Templates list, the same shape: redrawn at every save, delete and
# rename of a template.
_lk_tpl_saved = list(app.templates)
app.templates = [NO.normalize_template({'name': 'Leak tpl %d' % i, 'body': 'x'})
                 for i in range(3)]
app.toggle_settings_panel('templates'); app.update()
_lk_tpl_redraw = getattr(app, '_refresh_templates_panel', None)
_lk_clean, _lk_said = (_qa_leaves_nothing_behind(app, _lk_tpl_redraw, 30)
                       if _lk_tpl_redraw is not None
                       else (False, 'the panel has no redraw'))
check(f'redrawing the Templates list leaves no Tcl command behind '
      f'({_lk_said})', _lk_clean)
app.templates = _lk_tpl_saved
app.hide_settings_page(); app.update()

# 107: the wheel over an empty Trash panel must reach the page beneath
# it. A fully-shown list has nothing of its own to scroll, and trapping
# the wheel there is a scroll that silently does nothing.
app.trash = []
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
_b5_page = getattr(app, 'settings_canvas', None)
_b5_moved = {'n': 0}


def _b5_panel_canvas():
    """The empty panel's OWN scrolling canvas.

    Handing the router None instead skips the entire branch this case is
    about, and a mutant that trapped the wheel on every panel then sailed
    through. The whole question is what happens when the canvas exists
    and has nothing left to scroll.
    """
    found = []

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, tk.Canvas):
                found.append(child)
            walk(child)
    walk(app.settings_trash_panel)
    return found[0] if found else None


_b5_empty_canvas = _b5_panel_canvas()
check('an empty trash panel still has a canvas to route the wheel from '
      '(plan 107)', _b5_empty_canvas is not None)
if _b5_page is not None and _b5_empty_canvas is not None:
    _b5_real_scroll = _b5_page.yview_scroll

    def _b5_count(*a, **k):
        _b5_moved['n'] += 1
        return _b5_real_scroll(*a, **k)

    _b5_page.yview_scroll = _b5_count
    app._panel_or_page_wheel(_b5_empty_canvas,
                             _types6.SimpleNamespace(delta=-120))
    _b5_page.yview_scroll = _b5_real_scroll
check('the wheel over an empty trash panel scrolls the page (plan 107)',
      _b5_moved['n'] >= 1)

# And the other half of the same promise: a panel that CAN scroll keeps
# the wheel to itself, rather than sliding the page under the user.
app.trash = [{'id': 3000 + i, 'title': 'Old %d' % i, 'body': 'x',
              'category': 'General',
              'deleted_at': '2026-01-%02d 00:00:00' % ((i % 28) + 1)}
             for i in range(60)]
app.toggle_settings_panel('trash'); app.update()
_b5_inner = None
for _w in app.settings_trash_panel.winfo_children():
    for _c in _w.winfo_children():
        if isinstance(_c, tk.Canvas):
            _b5_inner = _c
            break
    if _b5_inner is not None:
        break
if _b5_inner is not None:
    _b5_moved['n'] = 0
    _b5_panel_moved = {'n': 0}
    _b5_real_panel = _b5_inner.yview_scroll

    def _b5_panel_count(*a, **k):
        _b5_panel_moved['n'] += 1
        return _b5_real_panel(*a, **k)

    _b5_inner.yview_scroll = _b5_panel_count
    if _b5_page is not None:
        _b5_page.yview_scroll = _b5_count
    app._panel_or_page_wheel(_b5_inner, _types6.SimpleNamespace(delta=-120))
    _b5_inner.yview_scroll = _b5_real_panel
    if _b5_page is not None:
        _b5_page.yview_scroll = _b5_real_scroll
    check('...while a panel with more to show keeps the wheel (plan 107)',
          _b5_panel_moved['n'] >= 1 and _b5_moved['n'] == 0)
app.hide_settings_page(); app.update()

# 110: deleting a category whose notes are on screen, grouped by that
# very category. The notes must land somewhere real and the grouping
# must agree with where they landed.
app.trash = []
NO.CATEGORY_COLORS['Temporary'] = '#889922'
app.notes = [NO.normalize_note({'id': 4100 + i, 'title': 'In temporary %d' % i,
                                'body': 'x', 'category': 'Temporary'})
             for i in range(3)]
app.save_notes()
# The Trash holds the name too: a series deleted earlier, one day of it
# filed under the category. Left alone, restoring it brought the category
# back at the next launch, announced as "gone missing from the settings".
app.trash = [dict(NO.normalize_note({
    'id': 4200, 'title': 'Old series', 'body': 'x', 'category': 'Temporary',
    'date': '2026-09-01', 'recurrence': {'freq': 'weekly'},
    'overrides': {'2026-09-08': {'body': 'moved', 'category': 'Temporary'}}}),
    deleted_at='2026-09-30 10:00:00')]
NO.save_trash(app.trash)
app.group_by_category.set(True)
app.refresh_note_list(); app.update()
app._themed_dialog = lambda *a, **k: 'move'      # keep the notes
app.show_settings_page(); app.update()
app.toggle_settings_panel('categories'); app.update()
app._delete_category('Temporary', lambda: None)
app.update()
check('deleting a category takes it off the list (plan 110)',
      'Temporary' not in NO.CATEGORY_COLORS)
check('...and its notes are kept, filed under General (plan 110)',
      all(n['category'] == 'General' for n in app.notes if n['id'] >= 4100))
check('...and the Trash lets go of the name too, day by day',
      app.trash[0]['category'] == 'General'
      and app.trash[0]['overrides']['2026-09-08']['category'] == 'General')
# An entry trashed before that -- by an older version, still naming a
# category that no longer exists -- comes back filed somewhere real.
_old_series6 = dict(NO.normalize_note({
    'id': 4201, 'title': 'Older series', 'body': 'x', 'date': '2026-09-01',
    'recurrence': {'freq': 'weekly'}}), deleted_at='2026-09-30 10:00:00')
_old_series6['overrides'] = {'2026-09-08': {'body': 'moved',
                                            'category': 'Temporary'}}
app.trash.append(_old_series6)
app._restore_from_trash(_old_series6); app.update()
check('...so a day filed under a deleted category comes back under General',
      app.notes[-1]['overrides']['2026-09-08']['category'] == 'General')
app.notes = [n for n in app.notes if n.get('title') != 'Older series']
app.save_notes()
app.trash = []; NO.save_trash(app.trash)
app.hide_settings_page()
app.refresh_note_list(); app.update()
check('...and the grouped list shows them where they now are (plan 110)',
      all((app._note_cards.get(n['id']) or {}).get('note', {}).get('category')
          == 'General' for n in app.notes if n['id'] >= 4100))
app.group_by_category.set(False)
app.refresh_note_list(); app.update()

# 121: a backup that mentions a category this device no longer has.
# The note must arrive filed somewhere real rather than in a category
# that does not exist.
_b5_incoming = NO.normalize_note({'id': 999, 'title': 'From backup',
                                  'body': 'x', 'category': 'VanishedCategory'})
check('a note naming a category this device lost is filed under General '
      '(plan 121)', _b5_incoming['category'] == 'General')
check('...and the note itself arrives whole, not refused',
      _b5_incoming['title'] == 'From backup')

# 118: an export started while the editor holds unsaved work. The export
# must not take the half-typed text, and must not lose it either.
app.notes = [NO.normalize_note({'id': 4200, 'title': 'Saved', 'body': 'the saved body',
                                'category': 'General'})]
app.save_notes()
app.load_note(app.notes[0]); app.update()
app.body_text.insert('end', ' plus something not sent')
_b5_on_disk_before = _json6.load(_io6.open('notes_data.json', encoding='utf-8'))
check('what is on disk before the export is the SAVED text (plan 118)',
      'not sent' not in _b5_on_disk_before[0]['body'])
app._flush_autosave()
app.update()
_b5_on_disk_after = _json6.load(_io6.open('notes_data.json', encoding='utf-8'))
check('...and the edit is not lost -- the autosave around it keeps it '
      '(plan 118)', 'not sent' in _b5_on_disk_after[0]['body'])

# 125: clicking quickly through many notes. Nothing may be lost, and no
# note may end up showing another note's words.
app.notes = [NO.normalize_note({'id': 4300 + i, 'title': 'Rapid %02d' % i,
                                'body': 'the body of note %02d' % i,
                                'category': 'General'})
             for i in range(12)]
app.save_notes()
app.refresh_note_list(); app.update()
_b5_wrong = []
for _b5_note in list(app.notes):
    app.open_note_in_tab(_b5_note)
    app.update()
    if app.body_text.get('1.0', 'end-1c').strip() != _b5_note['body']:
        _b5_wrong.append(_b5_note['id'])
check('switching through twelve notes never shows another one\'s text '
      '(plan 125)', not _b5_wrong)
_b5_final = _json6.load(_io6.open('notes_data.json', encoding='utf-8'))
check('...and all twelve are still there afterwards (plan 125)',
      len([n for n in _b5_final if n['id'] >= 4300]) == 12)
check('...each with the text it started with',
      all(n['body'] == 'the body of note %02d' % (n['id'] - 4300)
          for n in _b5_final if n['id'] >= 4300))

app.notes = list(_b5_saved_notes)
app.trash = list(_b5_saved_trash)
app.save_notes()
app.new_note(); app.update()


# ---------------------------------------------------------------------
# Settings x Calendar: coming back must not show a month built before
# anything happened in there.
#
# render_calendar() now defers a rebuild while the calendar is off
# screen, which is safe only because every route back to it catches the
# work up first. Three of those routes go through the tab-changed
# handler. This one does not: leaving Settings re-packs the notebook
# with the SAME tab still selected, so no tab-change event ever fires --
# and Settings is exactly where notes are restored, purged and
# recategorised. The gap was found by listing the routes rather than by
# trusting that a mechanism existed.
# ---------------------------------------------------------------------
_cal_day = '2026-08-14'


def _calendar_says(text):
    """Is `text` drawn anywhere in the month grid on screen right now? The
    month is text on one canvas, so it is asked of the drawing."""
    return any(text in t for t in app._cal_texts())


app.hide_settings_page(); app.update()
app.notes = []
app.trash = [{'id': 880, 'title': 'Marker9', 'body': 'x',
              'category': 'General', 'date': _cal_day,
              'deleted_at': '2026-08-01 10:00:00'}]
app.save_notes()
NO.save_trash(app.trash)
app.new_note()
app.notebook.select(app.TAB_CALENDAR)
app.cal_year, app.cal_month = 2026, 8
app.render_calendar()
app.update()
check('a trashed note is not on the calendar to begin with',
      not _calendar_says('Marker9'))

# Into Settings -- which leaves the Calendar tab selected underneath --
# and put the note back from there.
app.show_settings_page()
app.toggle_settings_panel('trash')
app.update()
_restore = None
for _w in (app.settings_trash_panel,):
    def _find(widget):
        global _restore
        if isinstance(widget, tk.Button) and 'Restore' in str(widget.cget('text')):
            _restore = _restore or widget
        for kid in widget.winfo_children():
            _find(kid)
    _find(_w)
check('the Restore button is there in Settings', _restore is not None)
if _restore is not None:
    _restore.invoke()
    app.update()
check('restoring from Settings puts the note back in the notebook',
      any(n.get('title') == 'Marker9' for n in app.notes))

app.hide_settings_page()
app.update()
app.update_idletasks()
app.update()
check('the calendar is up to date the moment Settings is left',
      _calendar_says('Marker9'))

app.notes = []
app.trash = []
app.save_notes()
NO.save_trash(app.trash)
app.notebook.select(app.TAB_NOTES)
app.new_note(); app.update()

# ---------------------------------------------------------------------
# Opening Settings and choosing a section in one breath shows ONE section.
#
# Choosing a section hides the others first, and asked each whether it
# was on the screen. A section Settings has only just packed is not, until
# Tk next draws, so it was left in place and two sections stacked on the
# page -- which is how a reference photograph once came out with Recently
# deleted under a nav reading Templates. It is asked whether it has its
# place now, and the answer does not depend on the drawing.
# ---------------------------------------------------------------------
app.show_settings_page(); app.update()
app.toggle_settings_panel('appearance'); app.update()
app.hide_settings_page(); app.update()
app.show_settings_page()                   # packs Appearance again...
app.toggle_settings_panel('trash')         # ...and at once asks for another
app.update()
_one_placed = [key for key, _label, _b, _e in app.SETTINGS_SECTIONS
               if getattr(app, 'settings_%s_panel' % key, None) is not None
               and app._is_placed(getattr(app, 'settings_%s_panel' % key))]
check(f'opening Settings and choosing a section at once shows that one '
      f'section only ({_one_placed})', _one_placed == ['trash'])
app.hide_settings_page(); app.update()


# ---------------------------------------------------------------------
# Grouping x the surgical card removal.
#
# A delete now takes one card off instead of rebuilding the list, and a
# category header carries a count that has to come down with it. The
# counts are kept from the note IDS each header was built with, NOT from
# the cards under it -- because a COLLAPSED group has a header and no
# cards at all, and counting what is drawn would read it as empty and
# throw its header away. That is the case worth a check.
# ---------------------------------------------------------------------
app.hide_settings_page(); app.update()
app.notebook.select(app.TAB_NOTES)
app.search_var.set('')
if hasattr(app, 'filter_var'):
    app.filter_var.set('All')
app.notes = [
    NO.normalize_note({'id': 601, 'title': 'Grp1', 'body': 'b',
                       'category': 'Work'}),
    NO.normalize_note({'id': 602, 'title': 'Grp2', 'body': 'b',
                       'category': 'Work'}),
    NO.normalize_note({'id': 603, 'title': 'Grp3', 'body': 'b',
                       'category': 'Personal'}),
]
app.save_notes()
app.new_note()
app.collapsed_groups.clear()
app.group_by_category.set(True)
app._on_toggle_group_by_category()
app.update()


def _settle():
    """Stop anything that would rebuild the list on a timer of its own.

    The sidebar search debounces with after(180, refresh_note_list), and
    a full rebuild puts every header back correctly -- which would repair
    a broken surgical update before a check could see it. That is not
    hypothetical: the mutant for the collapsed-group count died when its
    suite ran alone and survived when it ran under load, because the
    timer landed on the other side of the assertion. A check whose answer
    depends on machine speed is measuring the machine.
    """
    app._flush_autosave()
    if getattr(app, '_search_debounce_job', None) is not None:
        app.after_cancel(app._search_debounce_job)
        app._search_debounce_job = None
    app.update()


def _header_text(cat):
    head = app._header_view(cat)
    return None if head is None else str(head['label'])


check('a grouped list builds a header per category',
      _header_text('Work') == 'Work (2)'
      and _header_text('Personal') == 'Personal (1)')

_settle()
app._delete_note(app.find_note(602), None)
_settle()
check('deleting from a group brings its header count down',
      _header_text('Work') == 'Work (1)')
check('...and leaves the other group alone',
      _header_text('Personal') == 'Personal (1)')

_settle()
app._delete_note(app.find_note(603), None)
_settle()
check('emptying a group takes its header away with the last note',
      'Personal' not in app._group_headers)
check('...and the surviving group is untouched',
      _header_text('Work') == 'Work (1)')

# The collapsed case: a header with no cards under it at all.
app.notes = [
    NO.normalize_note({'id': 611, 'title': 'Col1', 'body': 'b',
                       'category': 'Work'}),
    NO.normalize_note({'id': 612, 'title': 'Col2', 'body': 'b',
                       'category': 'Work'}),
    NO.normalize_note({'id': 613, 'title': 'Keep', 'body': 'b',
                       'category': 'Personal'}),
]
app.save_notes()
app.new_note()
app.collapsed_groups.add('Work')
app.refresh_note_list()
app.update()
check('a collapsed group draws its header and none of its cards',
      _header_text('Work') == 'Work (2)'
      and 611 not in app._note_cards
      and 612 not in app._note_cards)
_settle()
app._delete_note(app.find_note(611), None)
_settle()
check('deleting inside a COLLAPSED group still counts it down',
      _header_text('Work') == 'Work (1)')
check('...and does not mistake "no cards drawn" for "no notes left"',
      'Work' in app._group_headers)

app.collapsed_groups.discard('Work')
app.group_by_category.set(False)
app._on_toggle_group_by_category()
app.update()

# ---------------------------------------------------------------------
# Statistics stays live while Settings is open, and is never arrived at
# stale -- the two halves of the promise it kept by redrawing on every
# list refresh, now that it redraws only when Settings is actually open.
# ---------------------------------------------------------------------
app.notes = [NO.normalize_note({'id': 620 + i, 'title': 'Stat%d' % i,
                                'body': 'b', 'category': 'General'})
             for i in range(5)]
app.save_notes()
app.new_note()
app.refresh_note_list()
app.update()


def _stats_total():
    """The "Total notes" tile, read as the number it shows. Searching every
    text in the panel for a digit also found it in the date of "Using Note
    Organizer since 04.10.2026": red on the fourth of the month, and the
    "2" it waited for was always there, in the year."""
    return stats_pairs().get('Total notes')


app.show_settings_page()
app.toggle_settings_panel('statistics')
app.update()
check(f'arriving at Statistics shows the count as it is now '
      f'({_stats_total()})', _stats_total() == 5)
# Deleted from under an open Settings page: the panel must follow.
app._delete_note(app.find_note(620), None)
app.update()
check(f'a delete while Statistics is open updates it ({_stats_total()})',
      _stats_total() == 4)
app.hide_settings_page()
app.update()

# Deletes with Settings CLOSED are where the redraw is skipped -- so
# this is the half that could go stale, and does not.
app._delete_note(app.find_note(621), None)
app._delete_note(app.find_note(622), None)
app.update()
app.show_settings_page()
app.toggle_settings_panel('statistics')
app.update()
check(f'Statistics is current on the next visit, not left behind '
      f'({_stats_total()})', _stats_total() == 2)
app.hide_settings_page()
app.update()

app.notes = []
app.trash = []
app.save_notes()
NO.save_trash(app.trash)
app.new_note(); app.update()

# ---- THE DUPLICATES CLEAN-UP MERGES ON YES, AND TELLS THE EDITOR ----
# It merged the files BEFORE asking (so "No" still gave the kept copy new
# files, one more per retry), never saved what the editor held (typing in
# the copy it trashed was in no file), and never told the editor, whose
# next save wrote the kept copy's old file list back.
class _DupVar6:
    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v


def _dup_setup6():
    fname = '20260930100000000000_dupmerge.txt'
    os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
    with open(os.path.join(NO.ATTACHMENTS_DIR, fname), 'w') as fh:
        fh.write('m')
    kept = NO.normalize_note({'id': 1, 'title': 'Dup', 'body': 'same'})
    gone = NO.normalize_note({'id': 2, 'title': 'Dup', 'body': 'same',
                              'attachments': [{'name': 'm.txt',
                                               'stored_as': fname}]})
    app.new_note(); app.update()
    app.notes = [kept, gone]
    app.trash = []
    app.save_notes(); NO.save_trash(app.trash)
    return kept, gone, [(_DupVar6(False), kept, [kept, gone]),
                        (_DupVar6(True), gone, [kept, gone])]


_dup_yes6 = app.ask_yes_no
_kept6, _gone6, _dv6 = _dup_setup6()
_files_before6 = sorted(os.listdir(NO.ATTACHMENTS_DIR))
app.ask_yes_no = lambda *a, **k: False
app._cleanup_selected_duplicates(_dv6, None, refresh=lambda: None)
app.ask_yes_no = _dup_yes6
check('answering No to the duplicates clean-up merges nothing',
      _kept6['attachments'] == []
      and sorted(os.listdir(NO.ATTACHMENTS_DIR)) == _files_before6)

_kept6, _gone6, _dv6 = _dup_setup6()
app.open_note_in_tab(_kept6); app.update()
app.ask_yes_no = lambda *a, **k: True
app._cleanup_selected_duplicates(_dv6, None, refresh=lambda: None)
app.ask_yes_no = _dup_yes6
app.update()
check('...Yes gives the kept copy the merged file, in the editor too',
      len(app.current_attachments) == 1)
app._flush_autosave(); app.update()
check('...so its next save keeps the file instead of writing the old list back',
      len(app.find_note(1)['attachments']) == 1)

_kept6, _gone6, _dv6 = _dup_setup6()
app.open_note_in_tab(_gone6); app.update()
app.body_text.insert('end', '\naction: Ana sends the figures')
app.ask_yes_no = lambda *a, **k: True
app._cleanup_selected_duplicates(_dv6, None, refresh=lambda: None)
app.ask_yes_no = _dup_yes6
app.update()
check('...and the copy open in the editor goes to the Trash with its typing',
      any('Ana sends the figures' in e.get('body', '') for e in app.trash))
check('...leaving a fresh editor, not the trashed copy',
      app.selected_note_id is None)
app.notes = []; app.trash = []
app.save_notes(); NO.save_trash(app.trash)
app.new_note(); app.update()

# ---- DELETING A CATEGORY NEVER DELETES A DAY'S OWN TEXT ----
# "Delete the notes too (restorable for N days)" trashed the notes filed
# under the category and then deleted, outright, every day of a series
# that was filed there on its own: the day's title and text were in
# neither file. The question had counted that series among the notes.
NO.CATEGORY_COLORS['Home6d'] = '#22aa66'
# The real question this time: an earlier section answers it with a stub.
app.__dict__.pop('_ask_category_deletion', None)
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {
                           'title': 'Standup at home', 'body': 'DAY TEXT',
                           'category': 'Home6d'}}}),
    NO.normalize_note({'id': 2, 'title': 'Groceries', 'body': 'milk',
                       'category': 'Home6d'})]
app.trash = []
app.save_notes(); NO.save_trash(app.trash)
_cd_asked = []
_cd_real_dlg = app._themed_dialog
app._themed_dialog = lambda *a, **k: (
    _cd_asked.append((a[0], a[1], [b[0] for b in k.get('buttons') or []])),
    'delete_notes')[1]
app._delete_category('Home6d', lambda: None); app.update()
app._themed_dialog = _cd_real_dlg
_cd_day = ((app.find_note(1) or {}).get('overrides') or {}).get('2026-09-14', {})
check("deleting a category with its notes keeps a series' own day filed there, "
      f"re-filed under General ({_cd_day})",
      _cd_day.get('body') == 'DAY TEXT' and _cd_day.get('category') == 'General')
check('...while the note filed there goes to the Trash, restorable',
      [e.get('title') for e in app.trash] == ['Groceries']
      and app.find_note(2) is None)
check(f'...and the question counts only that note, naming the day apart '
      f'({_cd_asked and _cd_asked[0][1]!r})',
      len(_cd_asked) == 1 and '1 note(s)' in _cd_asked[0][1]
      and 'have a day filed under' in _cd_asked[0][1])
# Held by a day alone, there is no note to trash, so nothing offers to.
NO.CATEGORY_COLORS['Away6d'] = '#aa6622'
app.find_note(1)['overrides']['2026-09-21'] = {'body': 'away', 'category': 'Away6d'}
app.save_notes()
_cd_asked.clear()
app._themed_dialog = lambda *a, **k: (
    _cd_asked.append((a[0], a[1], [b[0] for b in k.get('buttons') or []])),
    'move')[1]
app._delete_category('Away6d', lambda: None); app.update()
app._themed_dialog = _cd_real_dlg
check(f'a category only a day is filed under offers no "delete the notes" '
      f'({_cd_asked and _cd_asked[0][2]})',
      len(_cd_asked) == 1
      and not any('Delete the notes' in b for b in _cd_asked[0][2])
      and 'Away6d' not in NO.CATEGORY_COLORS
      and app.find_note(1)['overrides']['2026-09-21'].get('category') == 'General')
# Counted after the open note is saved: that save can file it under the
# category being deleted, and a count taken before it named "-1
# repeating note(s)".
NO.CATEGORY_COLORS['Late6d'] = '#6622aa'
app.notes = [NO.normalize_note({'id': 1, 'title': 'Filed just now', 'body': 'x'}),
             NO.normalize_note({'id': 2, 'title': 'Filed before', 'body': 'y',
                                'category': 'Late6d'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.category_var.set('Late6d')
_cd_asked.clear()
app._themed_dialog = lambda *a, **k: (
    _cd_asked.append((a[0], a[1], [b[0] for b in k.get('buttons') or []])),
    None)[1]
app._delete_category('Late6d', lambda: None); app.update()
app._themed_dialog = _cd_real_dlg
check(f'...and it counts the notes as they are once the open note is saved '
      f'({_cd_asked and _cd_asked[0][1]!r})',
      len(_cd_asked) == 1 and '2 note(s)' in _cd_asked[0][1]
      and 'repeating' not in _cd_asked[0][1]
      and app.find_note(1)['category'] == 'Late6d')
app.new_note(); app.update()
NO.CATEGORY_COLORS.pop('Late6d', None); NO.persist_categories()
app.notes = []; app.trash = []
app.save_notes(); NO.save_trash(app.trash)
# Yes trashes the notes the question counted, and only them. Read after
# the answer, a note filed under the category while the question waited
# (a timer's question took its grab, and a click went through) went to
# the Trash too -- one more than the question said. It goes to General.
NO.CATEGORY_COLORS['Wait6d'] = '#2266aa'
app.notes = [NO.normalize_note({'id': 1, 'title': 'Counted', 'body': 'x',
                                'category': 'Wait6d'}),
             NO.normalize_note({'id': 2, 'title': 'Filed while asking',
                                'body': 'y'})]
app.save_notes()
_cd_asked.clear()


def _cd_filed_while_asking(*a, **k):
    _cd_asked.append((a[0], a[1], [b[0] for b in k.get('buttons') or []]))
    app.find_note(2)['category'] = 'Wait6d'
    return 'delete_notes'


app._themed_dialog = _cd_filed_while_asking
app._delete_category('Wait6d', lambda: None); app.update()
app._themed_dialog = _cd_real_dlg
_cd_late = (app.find_note(2) or {}).get('category')
check(f'Yes to deleting a category\'s notes trashes the notes its question '
      f'counted, and only them -- one filed there while it waited goes to '
      f'General ({[e.get("title") for e in app.trash]}, {_cd_late}, '
      f'{_cd_asked and _cd_asked[0][1]!r})',
      [e.get('title') for e in app.trash] == ['Counted']
      and _cd_late == 'General'
      and len(_cd_asked) == 1 and '1 note(s)' in _cd_asked[0][1])
app.notes = []; app.trash = []
app.save_notes(); NO.save_trash(app.trash)

# ---- A CATEGORY RENAME REACHES THE RESCUE COPY ----
# "↩ Restore previous" after an update puts back the category and the
# per-day edits the update replaced. A rename rewrote every other holder
# of the name but not those: the restore filed the note under General and
# its day under the dead name, which the next launch re-created. And a
# Trash entry holding the name only there was never rewritten at all.
NO.CATEGORY_COLORS['Work6r'] = '#3366cc'
_rn_note = NO.normalize_note({'id': 1, 'title': 'Plan', 'body': 'new text',
                              'category': 'Work6r', 'date': '2026-09-07',
                              'recurrence': {'freq': 'weekly'}})
_rn_note['_prev'] = {'title': 'Plan', 'body': 'old text', 'formatting': [],
                     'paragraphs': [], 'comments': '', 'category': 'Work6r',
                     'overrides': {'2026-09-14': {'title': 'Plan, day',
                                                  'category': 'Work6r'}}}
_rn_entry = dict(NO.normalize_note({'id': 9, 'title': 'Old', 'body': 'x'}),
                 deleted_at='2026-09-20 10:00:00')
_rn_entry['_prev'] = {'title': 'Old', 'body': 'y', 'formatting': [],
                      'paragraphs': [], 'comments': '', 'category': 'Work6r'}
app.notes = [_rn_note]
app.trash = [_rn_entry]
app.save_notes(); NO.save_trash(app.trash)
# The Settings rename's own steps (do_rename).
NO.CATEGORY_COLORS['Office6r'] = NO.CATEGORY_COLORS.pop('Work6r')
app.rename_category_everywhere('Work6r', 'Office6r')
NO.persist_categories(); app.save_notes()
_rn_prev = app.find_note(1)['_prev']
check(f"a rename reaches a note's rescue copy and its days "
      f"({_rn_prev.get('category')}, "
      f"{_rn_prev['overrides']['2026-09-14'].get('category')})",
      _rn_prev.get('category') == 'Office6r'
      and _rn_prev['overrides']['2026-09-14'].get('category') == 'Office6r')
_rn_disk = [e for e in NO.load_trash() if e.get('title') == 'Old']
check('...and a Trash entry holding the name only in its rescue copy, on disk',
      len(_rn_disk) == 1
      and (_rn_disk[0].get('_prev') or {}).get('category') == 'Office6r')
app.open_note_in_tab(app.find_note(1)); app.update()
_rn_yes = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
app.restore_previous_version(); app.update()
app.ask_yes_no = _rn_yes
_rn_back = app.find_note(1)
check(f'...so Restore previous files the note and its day under the new name '
      f'({_rn_back.get("category")}, '
      f'{(_rn_back.get("overrides") or {}).get("2026-09-14", {}).get("category")})',
      _rn_back.get('category') == 'Office6r'
      and (_rn_back.get('overrides') or {}).get('2026-09-14', {}).get('category')
      == 'Office6r')
# Whatever left a dead name in a rescue copy, the restore files the day
# the way the note itself is filed: under General.
app.new_note(); app.update()
_rn_note = NO.normalize_note({'id': 2, 'title': 'Gone', 'body': 'now',
                              'date': '2026-09-07',
                              'recurrence': {'freq': 'weekly'}})
_rn_note['_prev'] = {'title': 'Gone', 'body': 'then', 'formatting': [],
                     'paragraphs': [], 'comments': '',
                     'overrides': {'2026-09-14': {'body': 'that day',
                                                  'category': 'NoSuchCat6r'}}}
app.notes = [_rn_note]; app.save_notes()
app.open_note_in_tab(app.find_note(2)); app.update()
app.ask_yes_no = lambda *a, **k: True
app.restore_previous_version(); app.update()
app.ask_yes_no = _rn_yes
check('...and a day restored under a category that is gone comes back under General',
      (app.find_note(2).get('overrides') or {}).get('2026-09-14', {}).get('category')
      == 'General')
# Restore previous from a day the restored version had deleted: the editor
# leaves the day for the whole note. It stayed on the date, and what was
# typed there was saved to a day no screen showed and no search found
# (the phone's round 23).
app.new_note(); app.update()
_rg_note = NO.normalize_note({'id': 5, 'title': 'Team meeting',
                              'body': 'Agenda', 'date': '2026-11-03',
                              'recurrence': {'freq': 'weekly',
                                             'weekdays': [1]}})
_rg_note['_prev'] = {'title': 'Team meeting', 'body': 'Agenda',
                     'formatting': [], 'paragraphs': [], 'comments': '',
                     'exceptions': ['2026-11-17']}
app.notes = [_rg_note]; app.save_notes()
app.open_note_in_tab(app.find_note(5), occurrence_date='2026-11-17')
app.update()
_rg_on_day = app.current_occurrence_date
app.ask_yes_no = lambda *a, **k: True
app.restore_previous_version(); app.update()
app.ask_yes_no = _rn_yes
app.body_text.insert('end', '\nCall the supplier')
app._flush_autosave(); app.update()
_rg_after = app.find_note(5) or {}
check(f'Restore previous from a day the restored version deleted leaves the '
      f'day for the whole note ({_rg_on_day} -> '
      f'{app.current_occurrence_date}, days of its own: '
      f'{sorted(_rg_after.get("overrides") or {})})',
      _rg_on_day == '2026-11-17' and app.current_occurrence_date is None
      and '2026-11-17' in (_rg_after.get('exceptions') or [])
      and '2026-11-17' not in (_rg_after.get('overrides') or {})
      and 'Call the supplier' in _rg_after.get('body', ''))
# A day showing the series' words shows the series' lines' looks; a day with
# text of its own shows none: put on by line number, they centred the wrong
# lines (the phone's twenty-fifth round).
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 6, 'title': 'Plan', 'body': 'Agenda\nsecond',
                                'date': '2026-11-02', 'recurrence': {'freq': 'weekly'},
                                'paragraphs': [{'line': 0, 'align': 'center'}],
                                'overrides': {'2026-11-16': {'body': 'own words\nhere'}}})]
app.save_notes()
app.open_note_in_tab(app.find_note(6), occurrence_date='2026-11-09'); app.update()
_pl_series_day = app._extract_paragraphs(app.body_text)
app.open_note_in_tab(app.find_note(6), occurrence_date='2026-11-16'); app.update()
_pl_own_day = app._extract_paragraphs(app.body_text)
check(f"a day showing the series' words shows its lines' looks, a day of its own text none "
      f"({_pl_series_day}; {_pl_own_day})",
      any(p.get('line') == 0 and p.get('align') == 'center' for p in _pl_series_day)
      and not any(p.get('align') for p in _pl_own_day)
      and any(p.get('line') == 0 and p.get('align') == 'center'
              for p in app.find_note(6).get('paragraphs') or []))
# A change made behind a day opened from the calendar -- an import's Update,
# a category change -- reads the note back and keeps "Back to Calendar": the
# reopening cleared it (the audit's round 24).
app.open_note_in_tab(app.find_note(6), occurrence_date='2026-11-09'); app.update()
app._pending_calendar_return = {'year': 2026, 'month': 11, 'date_str': '2026-11-09', 'origin': 'edit'}
app._update_calendar_return_button()
app.find_note(6)['title'] = 'Plan, renamed behind'
app._editor_follows_external_change({6}); app.update()
check(f'a change made behind a day opened from the calendar keeps its way back '
      f'({app._pending_calendar_return}, {app.current_occurrence_date})',
      (app._pending_calendar_return or {}).get('date_str') == '2026-11-09'
      and app.current_occurrence_date == '2026-11-09'
      and app.title_entry.get() == 'Plan, renamed behind')
app._pending_calendar_return = None
app._update_calendar_return_button()
# The note the question named is the note restored, and the editor is
# filled only while it still holds that note. Moved on to another note
# while the question waited, the editor took the rescue copy's text into
# THAT note, which its next save kept.
app.new_note(); app.update()
_rv_a = NO.normalize_note({'id': 3, 'title': 'Asked about', 'body': 'new'})
_rv_a['_prev'] = {'title': 'Asked about', 'body': 'old words',
                  'formatting': [], 'paragraphs': [], 'comments': ''}
app.notes = [_rv_a, NO.normalize_note({'id': 4, 'title': 'Opened meanwhile',
                                       'body': 'its own words'})]
app.save_notes()
app.open_note_in_tab(app.find_note(3)); app.update()


def _rv_moved_on(*a, **k):
    app.open_note_in_tab(app.find_note(4)); app.update()
    return True


app.ask_yes_no = _rv_moved_on
app.restore_previous_version(); app.update()
app.ask_yes_no = _rn_yes
app._flush_autosave(); app.update()
_rv_kept = (app.find_note(4) or {}).get('body', '')
check(f'Restore previous, answered after the editor moved to another note, '
      f'restores the note it asked about and leaves the open one alone '
      f'({(app.find_note(3) or {}).get("body")!r}, {_rv_kept!r}, '
      f'editor on {app.selected_note_id})',
      (app.find_note(3) or {}).get('body', '').startswith('old words')
      and _rv_kept.startswith('its own words')
      and app.selected_note_id == 4
      and 'old words' not in app.body_text.get('1.0', 'end-1c'))
app.new_note(); app.update()
NO.CATEGORY_COLORS.pop('Office6r', None); NO.CATEGORY_COLORS.pop('Home6d', None)
NO.persist_categories()
app.notes = []; app.trash = []
app.save_notes(); NO.save_trash(app.trash)


# ---- EVERY CONTROL IN SIGHT ----
# A row given less width than it asks loses what was placed last, and says
# nothing. Under CI's fonts the editor's "Save as template" lost its words
# at both ends (168 px of 177), and Settings' dropdowns and buttons were left
# what a setting's description did not take: the trash's "30 days" 18 px of
# 74, its arrow gone. Asked of the real pages first -- these fail only under
# a wider font than this machine's, and CI has one -- then of the two
# layouts that answer it, with a wider font simulated in pixels, so they
# fail here too when the answer is taken away.
def _fit_wait(top, cap=3.0):
    """Pump until every control under *top* is in sight -- the state the
    layout promises; mapping is asynchronous under Xvfb -- or *cap* seconds
    pass, and say what is still out of sight."""
    end = time.time() + cap
    while True:
        app.update()
        lost = _qa_out_of_sight(top)
        if not lost or time.time() > end:
            return lost
        time.sleep(0.02)


_fit_geo = app.geometry()
app.notes = [NO.normalize_note({'id': 61, 'title': 'Fit', 'body': 'b',
                                'category': 'General', 'comments': 'c'})]
app.save_notes(); app.refresh_note_list()
for _fit_size in ('1100x850', '640x600'):
    app.geometry(_fit_size)
    app.notebook.select(app.TAB_NOTES)
    app.open_note_in_tab(app.find_note(61))
    _fit_lost = _fit_wait(app)
    app.notebook.select(app.TAB_CALENDAR)
    _fit_lost += [f'calendar: {l}' for l in _fit_wait(app)]
    app.show_settings_page()
    for _fit_key, _fit_label, _fit_b, _fit_e in app.SETTINGS_SECTIONS:
        app.toggle_settings_panel(_fit_key)
        _fit_lost += [f'{_fit_key}: {l}' for l in _fit_wait(app)]
    app.hide_settings_page()
    app.notebook.select(app.TAB_NOTES); app.update()
    check(f'at {_fit_size}, every button, label and tick box on the notes page, the '
          f'calendar and every Settings section is wholly in sight ({_fit_lost})',
          _fit_lost == [])

# A Settings row places its control before its words: built narrow, with a
# description long enough to need wrapping, its button keeps its width and
# the words wrap beside it. That is seen failing under CI's fonts only: here
# the words happen to wrap before the row deals out its width, whichever is
# packed first. So the rule itself is asked as well -- the control comes
# first in the row's packing order -- which fails on any machine.
app.show_settings_page(); app.update()
_fit_host = tk.Frame(app.settings_page, width=420, height=260)
_fit_host.pack_propagate(False)
_fit_host.place(x=0, y=0)
_fit_ctl = app._card_row(
    _fit_host, 'Keep deleted notes for',
    'How long the trash holds a note before removing it for good -- and the '
    'rest of a description long enough to need three lines in a card this '
    'narrow, as a longer one or a wider font would.', first=True)
_fit_btn = app._text_button(_fit_ctl, 'Export', lambda: None)
_fit_btn.pack()
_fit_lost = _fit_wait(_fit_host)
_fit_order = _fit_ctl.master.pack_slaves()
check(f"a Settings row packs its control before its words, keeps the control's "
      f"width and wraps its words beside it ({_fit_lost}; {_fit_btn.winfo_width()} "
      f"of {_fit_btn.winfo_reqwidth()}; first packed: {_fit_order[:1]})",
      _fit_lost == [] and _fit_btn.winfo_width() + 1 >= _fit_btn.winfo_reqwidth()
      and _fit_order[:1] == [_fit_ctl])
_fit_host.destroy()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES); app.update()

# The editor's action buttons: three columns while there is room for three of
# the widest, else fewer -- and Restore previous under them, wherever that now
# is. The widest made 60 px wider stands for a wider font.
app.geometry('1100x850')
app.open_note_in_tab(app.find_note(61))
app.find_note(61)['_prev'] = {'body': 'older words'}
app._update_restore_button()
_fit_row = app._action_row
_fit_lost = _fit_wait(_fit_row)
check(f'at an ordinary window the six action buttons are two rows of three, all in '
      f'sight ({app._action_cols}; {_fit_lost})',
      _fit_lost == [] and app._action_cols == 3)
_fit_wide = app._action_buttons[4]
# As it was set, to put back: "3m" under Linux's Tk, a number here.
_fit_padx = _fit_wide.cget('padx')
_fit_wide.configure(padx=_fit_wide.winfo_pixels(_fit_padx) + 30)
app.geometry('640x600')
_fit_lost = _fit_wait(_fit_row)
_fit_bottom = max(b.winfo_y() + b.winfo_height() for b in app._action_buttons)
check(f'a row with no room for three of its widest button deals them into fewer '
      f'columns, all in sight, Restore previous under them ({app._action_cols} '
      f'columns; {_fit_lost}; Restore at {app.restore_prev_btn.winfo_y()}, the '
      f'buttons end at {_fit_bottom})',
      _fit_lost == [] and app._action_cols < 3
      and app.restore_prev_btn.winfo_y() >= _fit_bottom)
_fit_wide.configure(padx=_fit_padx)
app.geometry('1100x850')
_fit_lost = _fit_wait(_fit_row)
check(f'...and given room again, three columns ({app._action_cols}; {_fit_lost})',
      _fit_lost == [] and app._action_cols == 3)
app.find_note(61).pop('_prev', None)
app._update_restore_button()
app.geometry(_fit_geo)
app.new_note(); app.update()
app.notes = []
app.save_notes(); app.refresh_note_list(); app.update()


# ---- A SCREEN SCALED TO 150% AND 200% ----
# Declared to Windows as drawing at the screen's own scale -- the "Sharp text"
# setting, on by default -- the app is given fonts half as big again at 150%,
# while every size it writes in pixels stays as it was unless it grows that
# size itself (NoteOrganizer.px). Before it did, a 150% screen cut "Keyboard
# shortcuts" in the Settings menu, two statistics captions and two theme
# names, and 200% cut thirteen things on every page. Simulated as Windows
# sets it: Tk's own scaling, before anything is built -- which runs the same
# under CI's virtual display as on a laptop.
_sc_tk_init = tk.Tk.__init__


def _sc_build(scale):
    """A second app, built as a screen at *scale* builds it.

    Such a screen is a large one: Windows offers no 150% on a 1024x768
    panel, which is what CI's Windows runner has. Held to that screen, the
    window had no room for the sidebar's last buttons -- a verdict about the
    runner, not the app. So the app is built with room for its whole window,
    as on a screen that really runs at this scale, and Tk is let make it
    bigger than the runner's (under X, Tk holds a window to the screen
    itself). Holding the window to a small screen is asked on its own below."""
    def _scaled(self, *a, **k):
        _sc_tk_init(self, *a, **k)
        self.tk.call('tk', 'scaling', scale * 96 / 72)
    kept_room = NO.NoteOrganizer._screen_room
    tk.Tk.__init__ = _scaled
    NO.NoteOrganizer._screen_room = lambda self: (100000, 100000)
    try:
        sc = NO.NoteOrganizer()
    finally:
        tk.Tk.__init__ = _sc_tk_init
        NO.NoteOrganizer._screen_room = kept_room
    sc.maxsize(100000, 100000)
    sc._poll_active_dirty = lambda: None
    sc.show_info = lambda *a, **k: True
    sc.show_warning = lambda *a, **k: True
    sc.update()
    return sc


def _sc_fit_wait(sc, top, cap=3.0):
    """_fit_wait for the scaled app: its own events, its own controls."""
    end = time.time() + cap
    while True:
        sc.update()
        if not top.winfo_exists():
            return ['it closed before it could be looked at']
        lost = _qa_out_of_sight(top)
        if not lost or time.time() > end:
            return lost
        time.sleep(0.02)


check(f'this app, at the size the suite runs it, is drawn at 100% exactly '
      f'({app._ui_scale})', app._ui_scale == 1.0)
# CI's virtual display reports 100 dots per inch, not 96: unsnapped, every
# pixel the suite measures there moved by 4%. A screen reporting fewer than
# 96 keeps the sizes it always had.
_sc_app = _sc_build(100 / 96)
_sc_odd = _sc_app._ui_scale
_sc_app.destroy()
_sc_app = _sc_build(0.75)
_sc_low = _sc_app._ui_scale
_sc_app.destroy()
check(f'a screen reporting 100 dots per inch is drawn at 100% ({_sc_odd}), and one '
      f'reporting 72 is not drawn smaller ({_sc_low})',
      _sc_odd == 1.0 and _sc_low == 1.0)

for _sc_scale in (1.5, 2.0):
    _sc_pct = f'{round(_sc_scale * 100)}%'
    _sc = _sc_build(_sc_scale)

    def _sc_px(n, s=_sc_scale):
        return int(round(n * s))

    _sc_sizes = {n: (getattr(_sc, n), _sc_px(getattr(type(_sc), n)))
                 for n in _sc._SIZES_AT_100}
    check(f'at {_sc_pct} the app reads its screen as {_sc._ui_scale}, and every size '
          f'it keeps at 100% is set again at that scale '
          f'({ {n: v for n, v in _sc_sizes.items() if v[0] != v[1]} })',
          _sc._ui_scale == _sc_scale
          and all(got == want for got, want in _sc_sizes.values()))
    check(f'...the note list beside it is as wide again as its words '
          f'({_sc.sidebar.cget("width")}; the page holds at least '
          f'{_sc._main_min_width})',
          int(_sc.sidebar.cget('width')) == _sc_px(NO.SIDEBAR_WIDTH)
          and _sc._main_min_width == _sc_px(NO.SIDEBAR_WIDTH + NO.EDITOR_MIN_WIDTH))

    # The window: 900x600 and its 640x600 floor at this scale -- but never
    # bigger than the screen can show, which a 1920x1080 laptop at 175% is.
    _sc_opened = tuple(int(n) for n in _sc.geometry().split('+')[0].split('x'))
    _sc._screen_room = lambda: (1000, 700)
    _sc_small = (_sc._fit_to_screen(900, 600), _sc._fit_to_screen(640, 600))
    del _sc._screen_room
    check(f'...its window opens at 900x600 grown to {_sc_opened}, with its smallest '
          f'size grown the same way ({_sc.minsize()}), and never past the screen '
          f'({_sc_small} on a screen with room for 1000x700)',
          _sc_opened == (_sc_px(900), _sc_px(600))
          and _sc.minsize() == (_sc_px(640), _sc_px(600))
          and _sc_small == ((1000, 700), (min(_sc_px(640), 1000), 700)))

    # Every control in sight, on the pages and popups that hold the sizes
    # above. The checklist's long item wraps; the table holds a tick box.
    _sc.notes = [
        NO.normalize_note({
            'id': 71, 'title': 'Scaled', 'category': 'General', 'date': '2026-10-16',
            'body': 'Words.\n| Day | Done |\n| --- | --- |\n| Monday | [x] |',
            'checklist': [{'text': 'An item long enough to need its own wrap in '
                                   'a checklist row', 'done': True}],
            'comments': 'c'}),
        NO.normalize_note({'id': 72, 'title': 'Stand-up', 'category': 'Work',
                           'date': '2026-10-05', 'body': 'agenda',
                           'recurrence': {'freq': 'weekly', 'weekdays': [0]}}),
    ]
    _sc.save_notes(); _sc.refresh_note_list()
    _sc_lost = []
    for _sc_where, _sc_go in (
            ('the note', lambda: _sc.open_note_in_tab(_sc.find_note(71))),
            ('the series', lambda: _sc.open_note_in_tab(_sc.find_note(72))),
            ('one day of it', lambda: _sc.open_note_in_tab(
                _sc.find_note(72), occurrence_date='2026-10-12')),
            ('selecting', _sc._toggle_selection_mode),
            ('selecting done', _sc._toggle_selection_mode),
            ('the calendar', lambda: _sc.notebook.select(_sc.TAB_CALENDAR))):
        _sc_go()
        _sc_lost += [f'{_sc_where}: {l}' for l in _sc_fit_wait(_sc, _sc)]
    _sc.notebook.select(_sc.TAB_NOTES)
    _sc.open_note_in_tab(_sc.find_note(71))
    # The tab's own deferred redraw closes whatever popup is open -- as a
    # person's click elsewhere would -- so the picker opens once it is done.
    _sc_fit_wait(_sc, _sc, cap=1.0)
    _sc._show_emoji_picker(_sc.body_text)
    _sc_lost += [f'emoji: {l}' for l in _sc_fit_wait(_sc, _sc._mini_popup)]
    _sc._dismiss_mini_popup()
    _sc.show_settings_page()
    for _sc_key, _l, _b, _e in _sc.SETTINGS_SECTIONS:
        _sc.toggle_settings_panel(_sc_key)
        _sc_lost += [f'{_sc_key}: {l}' for l in _sc_fit_wait(_sc, _sc)]
    check(f'...and every button, label and tick box on the notes page, a series, '
          f'one of its days, the selection bar, the calendar, the emoji picker and '
          f'every Settings section is wholly in sight ({_sc_lost})', _sc_lost == [])

    # What is drawn rather than written: Tk grows a canvas's coordinates on
    # request, never its lines' thickness, and a box sized for the screen
    # with its drawing left at 100% is a small mark in a large hole.
    _sc_glyphs = [c.bbox('glyph') for c in _sc._settings_nav_icons.values()]
    _sc_glyph_w = min(b[2] - b[0] for b in _sc_glyphs if b)
    _sc_c = tk.Canvas(_sc)
    _sc_line = _sc_c.create_line(0, 0, 10, 0, width=2)
    _sc._scale_drawing(_sc_c)
    _sc_moved = (_sc_c.coords(_sc_line), float(_sc_c.itemcget(_sc_line, 'width')))
    _sc_c.destroy()
    _sc_empty, _sc_ticked = _sc._paint_tick_images()
    _sc_mark = [x for x in range(_sc_ticked.width()) for y in range(_sc_ticked.height())
                if '#%02x%02x%02x' % tuple(_sc_ticked.get(x, y)) == _sc.CARD_CHECK_MARK]
    check(f'...a drawing grows with its lines ({_sc_moved}), the Settings menu\'s '
          f'glyphs fill their larger box (narrowest {_sc_glyph_w}), and the drawn '
          f'tick box and its tick grow together ({_sc_ticked.width()} wide, the tick '
          f'reaching {max(_sc_mark) if _sc_mark else None})',
          _sc_moved[0] == [0.0, 0.0, 10 * _sc_scale, 0.0]
          and _sc_moved[1] == 2 * _sc_scale
          and _sc_glyph_w >= 10 * _sc_scale
          and _sc_ticked.width() == _sc_px(13) + _sc_px(4)
          and _sc_mark and max(_sc_mark) >= 9 * _sc_scale)

    # The calendar's titles grow a step in a wide window. Wide is a width at
    # 100%, so a 150% screen showing a 100%-sized window is not wide.
    _sc.winfo_width = lambda s=_sc_scale: int(1000 * s)
    _sc_narrow = _sc._cal_note_font_size()
    _sc.winfo_width = lambda s=_sc_scale: int(1200 * s)
    _sc_wide = _sc._cal_note_font_size()
    del _sc.winfo_width
    check(f'...and the calendar\'s titles step up in a wide window, as wide at '
          f'this scale ({_sc_narrow} at 1000, {_sc_wide} at 1200)',
          (_sc_narrow, _sc_wide) == (9, 11))
    _sc.hide_settings_page()
    _sc.notes = []
    _sc.save_notes()
    _sc._cancel_pending_autosave()
    _sc.destroy()
app.update()

# The setting, and the one moment it is read. _main is run with the window
# taken out: the app class, the folder's lock and the data's setup stood in
# for, so what is asked is only whether it declares the drawing mode, before
# the first window, exactly when Sharp text is on -- and when nothing, or
# nonsense, is stored, since on is what it means to be new.
_mg_calls = []


class _MgApp:
    def protocol(self, *a):
        pass

    def mainloop(self):
        pass

    def on_app_close(self):
        pass

    def on_session_end(self):
        pass


import tkinter.messagebox as _mg_box
_mg_kept = (NO.NoteOrganizer, NO._draw_sharp_on_scaled_screens, NO.initialise,
            NO.single_instance.acquire, _mg_box.showerror)
NO.NoteOrganizer = _MgApp
NO._draw_sharp_on_scaled_screens = lambda: _mg_calls.append('declared') or True
NO.initialise = lambda **k: None
NO.single_instance.acquire = lambda path: True
# _main's last resort is a blocking error box: a stand-in that went wrong
# must fail this check, not hang the script waiting for a click.
_mg_box.showerror = lambda *a, **k: _mg_calls.append('crashed')
_mg_seen = {}
try:
    for _mg_stored in (True, False, None, 'yes'):
        NO.save_setting(NO.SHARP_TEXT_SETTING, _mg_stored)
        _mg_calls.clear()
        NO._main()
        _mg_seen[repr(_mg_stored)] = list(_mg_calls)
finally:
    (NO.NoteOrganizer, NO._draw_sharp_on_scaled_screens, NO.initialise,
     NO.single_instance.acquire, _mg_box.showerror) = _mg_kept
    NO.save_setting(NO.SHARP_TEXT_SETTING, True)
check(f'the app declares its drawing mode at start when Sharp text is on, or '
      f'when nothing usable is stored, and not when it is off ({_mg_seen})',
      _mg_seen == {'True': ['declared'], 'False': [], 'None': ['declared'],
                   "'yes'": ['declared']})

# Settings -> Appearance carries the row on Windows only: nowhere else does
# the system stretch a program's picture, so there is nothing to choose.
app.show_settings_page(); app.toggle_settings_panel('appearance'); app.update()
_st_rows = [w for w in find_all(app.settings_page, tk.Label)
            if w.cget('text') == 'Sharp text']
if sys.platform.startswith('win'):
    app._set_sharp_text('Off')
    _st_off = NO.get_setting(NO.SHARP_TEXT_SETTING, True, expect=bool)
    _st_said = app.toast_lbl.cget('text')
    app._set_sharp_text('On')
    _st_on = NO.get_setting(NO.SHARP_TEXT_SETTING, False, expect=bool)
    check(f'on Windows, Settings -> Appearance offers Sharp text, and choosing Off '
          f'and On is kept for the next start and says when it shows '
          f'({len(_st_rows)} row; {_st_off}, {_st_on}; "{_st_said}")',
          len(_st_rows) == 1 and _st_off is False and _st_on is True
          and 'next time you open' in _st_said)
    # The real declaration, in a process of its own that opens no window:
    # the one this suite runs in has windows already, and Windows decides a
    # program's drawing mode only once.
    import subprocess
    _st_probe = subprocess.run(
        [sys.executable, '-c',
         'import ctypes, note_organizer as NO\n'
         'ok = NO._draw_sharp_on_scaled_screens()\n'
         'u = ctypes.windll.user32\n'
         'u.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p\n'
         'u.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]\n'
         'print(ok, u.GetAwarenessFromDpiAwarenessContext('
         'u.GetThreadDpiAwarenessContext()))'],
        cwd=os.getcwd(), capture_output=True, text=True, timeout=120)
    check(f'...and a process that declares it is drawn at its screen\'s scale by '
          f'Windows ({_st_probe.stdout.strip()!r} {_st_probe.stderr.strip()[-200:]!r})',
          _st_probe.stdout.split() == ['True', '1'])
else:
    check(f'off Windows there is no Sharp text row ({len(_st_rows)}), and the '
          f'declaration does nothing and says so',
          _st_rows == [] and NO._draw_sharp_on_scaled_screens() is False)
app.hide_settings_page(); app.notebook.select(app.TAB_NOTES); app.update()


# ---- SPELLING ----
# Misspelled words underlined in the note and its comments, judged by
# Windows' own dictionaries (core/winspell.py), shown by the quiet rules of
# core/spelling.py. The machine's dictionaries are pinned away for every
# test (pin_the_desktop): here the app is given a stand-in that knows
# exactly which words are wrong, so these checks answer the same on Windows,
# on Linux and on CI. What they ask is the editor's side: where the line
# goes, what it leaves alone, the menu, and that nothing of it is ever
# stored, copied or taken for an edit.
from noteorganizer.core import spelling as _sp_rules


class _SpDictionary:
    """A stand-in for one of Windows' dictionaries."""

    def __init__(self, wrong, tag="en-US"):
        self.tag = tag
        self.wrong = set(wrong)
        self.asked = []
        self.added = []

    def errors(self, text):
        self.asked.append(text)
        return [(_sp_rules.utf16_units(text[:m.start()]), _sp_rules.utf16_units(m.group()))
                for m in re.finditer(r"[^\W\d_]+", text) if m.group() in self.wrong]

    def suggest(self, word, limit=5):
        return {"boldd": ["bold"], "recieve": ["receive"]}.get(word, [])[:limit]

    def add(self, word):
        self.added.append(word)
        self.wrong.discard(word)
        return True


def _sp_settle(cap=4.0):
    """Pump until no spelling look is still due -- the state the editor
    promises after a pause -- or *cap* seconds pass."""
    end = time.time() + cap
    while time.time() < end:
        app.update()
        if all(getattr(w, "_spell_job", None) is None for w in app._spell_widgets):
            app.update()
            return True
        time.sleep(0.02)
    return False


def _sp_lines(widget):
    """The words underlined in *widget*, in order."""
    r = widget.tag_ranges(app.SPELL_TAG)
    return [widget.get(r[i], r[i + 1]) for i in range(0, len(r), 2)]


# German stands for any language the computer has no dictionary for.
_sp_de = ("Morgen früh gehen wir auf den Markt und kaufen frisches "
          "Gemüse für die Suppe am Sonntag.")
_sp_dict = _SpDictionary(
    {"recieve", "teh", "tommorow", "boldd", "meetting", "Remmember", "recipt", "PDF",
     "Anothr"} | set(re.findall(r"[^\W\d_]+", _sp_de)) - {"am", "die", "den", "Markt"})
app._spellers_found = [_sp_dict]
NO.save_setting(_sp_rules.SPELLING_SETTING, True)
_sp_body = ("I recieve teh letters every Tuesday, and the PDF is on www.example.com at 10:30.\n"
            "Party \U0001F389 tommorow at noon.\n" + _sp_de + "\n"
            "| Day | Plan |\n| --- | --- |\n| Monday | meetting |\n"
            "A boldd word here.")
_sp_at = _sp_body.index("boldd")
app.notes = [NO.normalize_note({
    'id': 81, 'title': 'Spelling', 'category': 'General', 'body': _sp_body,
    'formatting': [{'start': _sp_at, 'end': _sp_at + 5, 'style': 'bold'}],
    'comments': 'Remmember the recipt.'})]
app.save_notes(); app.refresh_note_list()
app.open_note_in_tab(app.find_note(81))
_sp_settle()
_sp_b = app.body_text
check(f'misspelled words in the note and its comments are underlined -- the one '
      f'after an emoji exactly -- while an abbreviation, a link, a time, a paragraph '
      f'in another language and a table row are left alone '
      f'({_sp_lines(_sp_b)}; {_sp_lines(app.comments_text)})',
      _sp_lines(_sp_b) == ['recieve', 'teh', 'tommorow', 'boldd']
      and _sp_lines(app.comments_text) == ['Remmember', 'recipt'])
check(f'...and underlining them changes nothing the note holds: it does not read '
      f'as unsaved, and no spelling is among its formatting '
      f'({sorted({s["style"] for s in app._extract_formatting(_sp_b)})})',
      app.editor_state_matches_saved(app.capture_editor_state())
      and [s['style'] for s in app._extract_formatting(_sp_b)] == ['bold'])
# What the copy hands the clipboard, caught on the way: off Windows the real
# writer takes no HTML and returns False, and this check read nothing on Linux.
_sp_written = {}
_sp_real_write = NO.clipboard.write
NO.clipboard.write = lambda text, html=None: bool(_sp_written.update(html=html)) or True
try:
    _sp_b.tag_add('sel', '1.0', 'end-1c')
    app._copy_formatted()
finally:
    NO.clipboard.write = _sp_real_write
    _sp_b.tag_remove('sel', '1.0', 'end')
_sp_html = _sp_written.get('html') or ''
check(f'...nor in what a copy puts on the clipboard (underline in the copied HTML: '
      f'{"underline" in _sp_html.lower() or "<u>" in _sp_html.lower()})',
      bool(_sp_html) and 'underline' not in _sp_html.lower()
      and '<u>' not in _sp_html.lower())

# The word being typed waits until the caret leaves it. A generated key goes
# to the window that has the focus, so the note has it first.
_take_focus(_sp_b)
_sp_b.mark_set('insert', 'end-1c')
for _sp_ch in ' Anothr':
    _sp_b.insert('insert', _sp_ch)
    _sp_b.event_generate('<KeyRelease>', keysym='space' if _sp_ch == ' ' else _sp_ch)
_sp_settle()
_sp_typing = 'Anothr' in _sp_lines(_sp_b)
_sp_b.insert('insert', ' ')
_sp_b.event_generate('<KeyRelease>', keysym='space')
_sp_settle()
_sp_left = 'Anothr' in _sp_lines(_sp_b)
check(f'a word is not underlined while it is being typed, and is once the caret '
      f'moves on ({_sp_typing}, then {_sp_left})', not _sp_typing and _sp_left)
# The comments box's own autosave binding, made after the spelling's, once
# replaced it there: comments were looked at only when a note opened.
_sp_c = app.comments_text
_take_focus(_sp_c)
_sp_c.mark_set('insert', 'end-1c')
# Words enough that three unknown ones in four do not read as another
# language (core/spelling.is_foreign) -- which a short line would.
for _sp_ch in ' Please buy Anothr soon ':
    _sp_c.insert('insert', _sp_ch)
    _sp_c.event_generate('<KeyRelease>', keysym='space' if _sp_ch == ' ' else _sp_ch)
_sp_settle()
check(f'...and the comments box is looked at as it is typed in, too '
      f'({_sp_lines(_sp_c)})', 'Anothr' in _sp_lines(_sp_c))

# The right-click menu: suggestions first, then Ignore and Add to Windows
# dictionary, and none of it when the menu opens anywhere else.
_sp_menu = next(c for c in _sp_b.winfo_children() if c.winfo_class() == 'Menu')
import types


def _sp_menu_at(index):
    _sp_b.see(index)
    app.update()
    x, y, _w, h = _sp_b.bbox(index)
    event = types.SimpleNamespace(x=x + 2, y=y + h // 2)
    app._spell_menu(_sp_b, _sp_menu, event)
    return [('---' if _sp_menu.type(k) == 'separator' else _sp_menu.entrycget(k, 'label'))
            for k in range(_sp_menu.index('end') + 1)]


_sp_bold_at = _sp_b.search('boldd', '1.0')
_sp_on_word = _sp_menu_at(_sp_bold_at)
_sp_elsewhere = _sp_menu_at(_sp_b.search('letters', '1.0'))
check(f'right-clicking an underlined word puts its suggestions, Ignore and Add to '
      f'Windows dictionary first ({_sp_on_word[:4]}), and right-clicking anywhere '
      f'else shows the menu as it always was ({_sp_elsewhere[:2]})',
      _sp_on_word[:4] == ['bold', 'Ignore “boldd”', 'Add to Windows dictionary', '---']
      and _sp_elsewhere[:2] == ['Cut', 'Copy'])
_sp_menu_at(_sp_bold_at)
_sp_menu.invoke(0)
_sp_settle()
_sp_line = _sp_b.get(f'{_sp_bold_at} linestart', f'{_sp_bold_at} lineend')
_sp_bold = [s for s in app._extract_formatting(_sp_b) if s['style'] == 'bold']
_sp_taken = (_sp_line, _sp_b.get('1.0', 'end-1c')[_sp_bold[0]['start']:_sp_bold[0]['end']]
             if _sp_bold else None)
app._body_undo_redo('undo')
_sp_settle()
_sp_bold = [s for s in app._extract_formatting(_sp_b) if s['style'] == 'bold']
_sp_back = (_sp_b.get(f'{_sp_bold_at} linestart', f'{_sp_bold_at} lineend'),
            _sp_b.get('1.0', 'end-1c')[_sp_bold[0]['start']:_sp_bold[0]['end']]
            if _sp_bold else None)
check(f'taking a suggestion replaces the word in its own formatting, and one '
      f'Ctrl+Z puts the misspelling back, bold and all ({_sp_taken}; {_sp_back})',
      _sp_taken == ('A bold word here. Anothr ', 'bold')
      and _sp_back == ('A boldd word here. Anothr ', 'boldd'))

# Ignore: kept on this computer, whatever case it was typed in.
app._spell_ignore('Teh')
_sp_settle()
_sp_kept = NO.get_setting(_sp_rules.SPELLING_IGNORED_SETTING, [], expect=list)
app._spell_ignored_words = None          # read back from settings.json
app._spell_schedule_all()
_sp_settle()
check(f'Ignore stops underlining the word in any case, and is kept in settings for '
      f'the next start ({_sp_kept}; {_sp_lines(_sp_b)})',
      'teh' in _sp_kept and 'teh' not in _sp_lines(_sp_b))
app._spell_add('tommorow')
_sp_settle()
check(f'Add to Windows dictionary hands the word to the dictionary, its line goes, '
      f'and the toast says other programs know it too '
      f'({_sp_dict.added}; {_sp_lines(_sp_b)}; "{app.toast_lbl.cget("text")}")',
      _sp_dict.added == ['tommorow'] and 'tommorow' not in _sp_lines(_sp_b)
      and 'other programs know it too' in app.toast_lbl.cget('text'))

# The theme's red, and Settings' switch.
_sp_theme = app.theme_name
app.set_theme('light' if _sp_theme in NO.DARK_THEMES else 'dark')
try:
    _sp_red = _sp_b.tag_cget(app.SPELL_TAG, 'underlinefg')
except tk.TclError:
    _sp_red = app.colors['danger_text']   # a Tk without underline colours
_sp_want = app.colors['danger_text']
app.set_theme(_sp_theme)
check(f'a theme switch gives the underline the new theme\'s red ({_sp_red} / {_sp_want})',
      str(_sp_red).lower() == _sp_want.lower())
app._set_spelling('Off')
_sp_settle()
_sp_off = (_sp_lines(_sp_b), _sp_lines(app.comments_text),
           NO.get_setting(_sp_rules.SPELLING_SETTING, True, expect=bool))
app._set_spelling('On')
_sp_settle()
check(f'Spelling turned Off in Settings takes every line away at once and is kept; '
      f'On brings them back ({_sp_off}; {_sp_lines(_sp_b)})',
      _sp_off == ([], [], False) and 'recieve' in _sp_lines(_sp_b))
NO.save_setting(_sp_rules.SPELLING_SETTING, None)
_sp_new = app._spell_on()
NO.save_setting(_sp_rules.SPELLING_SETTING, True)
check(f'...and someone new, with nothing stored, has it on ({_sp_new})', _sp_new is True)

# A long note is read in slices, and a long line in pieces: the editor is
# never held up for the whole of it at once.
_sp_dict.asked.clear()
_sp_long = "\n".join(f"Line {n} with a recieve in it" for n in range(300))
_sp_b.delete('1.0', 'end')
_sp_b.insert('1.0', _sp_long)
app._spell_run(_sp_b)
_sp_first = len(_sp_dict.asked)
# ...and once the last slice has run, no look is still due: its timer's id
# stayed behind, and every wait for the look ran to its cap (round 9).
_sp_done = _sp_settle(cap=10)
check(f'a long note is read a slice at a time ({_sp_first} lines in the first, '
      f'{app.SPELL_SLICE} allowed), and all of it in the end '
      f'({len(_sp_lines(_sp_b))} of 300 underlined), the look then said done ({_sp_done})',
      _sp_first <= app.SPELL_SLICE and len(_sp_lines(_sp_b)) == 300 and _sp_done)
_sp_dict.asked.clear()
_sp_b.delete('1.0', 'end')
_sp_b.insert('1.0', ('word ' * 2500) + 'recieve')
app._spell_run(_sp_b)
_sp_settle()
check(f'a line longer than {_sp_rules.PIECE_UNITS} units is asked about in pieces '
      f'no longer than that ({[len(a) for a in _sp_dict.asked]}), and its word at the '
      f'end is still found ({_sp_lines(_sp_b)})',
      len(_sp_dict.asked) > 1
      and all(_sp_rules.utf16_units(a) <= _sp_rules.PIECE_UNITS for a in _sp_dict.asked)
      and _sp_lines(_sp_b) == ['recieve'])

# The real dictionaries, on Windows: off Windows there are none, and the
# switch has nothing to underline with.
from noteorganizer.core import winspell as _sp_win
if sys.platform.startswith('win') and _sp_win.languages():
    _sp_real = [s for s in (_sp_win.speller(t) for t in _sp_rules.pick_languages(
        _sp_win.languages(), _sp_win.preferred_languages())) if s]
    _sp_found = _sp_real[0].errors('I recieve it') if _sp_real else []
    check(f"Windows' own dictionary is reached and finds a misspelling where it is "
          f"({[s.tag for s in _sp_real]}; {_sp_found})", _sp_found == [(2, 7)])
elif sys.platform.startswith('win'):
    print("INFO this Windows has no spelling dictionary; the real one is asked on a machine that does")
else:
    check('off Windows there is no dictionary to reach, and nothing is underlined '
          'with the real one', not _sp_win.available() and _sp_win.languages() == [])
app._spellers_found = []
app._spell_schedule_all()
_sp_settle()
app.new_note(); app.update()
app.notes = []
app.save_notes(); app.refresh_note_list(); app.update()

# ---- KEYBOARD: what Tab lands on is scrolled into sight ----
# Tk's Tab moves the keyboard and never the view, and the editor, Settings
# and the Trash list are frames drawn on canvases: at the app's opening size
# Tab walked onto Save and Delete below the fold, and onto sixty Trash
# controls nobody could see, with the view standing still.
def _kv_settle(n=6):
    for _ in range(n):
        app.update()
        time.sleep(0.02)


def _kv_in_view(w, canvas):
    top = w.winfo_rooty() - canvas.winfo_rooty()
    return 0 <= top and top + w.winfo_height() <= canvas.winfo_height()


if getattr(app, '_settings_open', False):
    app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.geometry('900x600')
app.new_note()
_kv_settle(10)
_kv_ec = app.editor_canvas
_kv_save = find_widget(app.editor, tk.Button, '💾 Save')
_kv_ec.yview_moveto(0)
_kv_settle()
_kv_from = _kv_save.tk_focusPrev() if _kv_save is not None else None
check(f'fixture: at 900x600 the editor\'s Save lies below the fold, and so does '
      f'the control before it ({_kv_ec.yview()})',
      _kv_from is not None and not _kv_in_view(_kv_save, _kv_ec)
      and not _kv_in_view(_kv_from, _kv_ec) and _take_focus(_kv_from))
_kv_from.event_generate('<Tab>')
_kv_settle()
check(f'Tab onto Save, below the fold, scrolls the editor to show it '
      f'({_kv_ec.yview()})', _kv_in_view(_kv_save, _kv_ec))
_kv_view = _kv_ec.yview()
if _take_focus(_kv_save):
    _kv_save.event_generate('<Shift-Tab>')
    _kv_settle()
check(f'...and Shift+Tab back onto a control already in sight leaves the view '
      f'where it was ({_kv_view} -> {_kv_ec.yview()})',
      _kv_ec.yview() == _kv_view and _kv_in_view(_kv_from, _kv_ec))
_kv_ec.yview_moveto(1.0)
_kv_settle()
_kv_after_title = app.title_entry.tk_focusNext()
check('fixture: scrolled to the bottom, the title box is out of sight',
      not _kv_in_view(app.title_entry, _kv_ec) and _take_focus(_kv_after_title))
_kv_after_title.event_generate('<Shift-Tab>')
_kv_settle()
check(f'Shift+Tab onto the title, above the fold, scrolls back up to it '
      f'({_kv_ec.yview()})', _kv_in_view(app.title_entry, _kv_ec))

# Recently deleted: a list on a canvas, on a page on a canvas. Both move.
app.trash = [{'id': 700 + i, 'uid': f'kv-{i}', 'title': f'Sight{i:02d}',
              'body': 'x', 'category': 'General',
              'deleted_at': f'2026-10-{1 + i % 25:02d} 10:00:00'} for i in range(30)]
NO.save_trash(app.trash)
app.geometry('1000x650')
app.show_settings_page()
app.toggle_settings_panel('trash')
_kv_settle(20)
_kv_list = app._active_panel_canvas
_kv_page = app.settings_canvas
_kv_rows = [w for w in _kv_list._row_stack.rows()
            if getattr(w, '_trash_buttons', None)]
_kv_first = (next(c for c in _kv_rows[0].winfo_children()
                  if isinstance(c, tk.Checkbutton)) if _kv_rows else None)
def _kv_keyboard():
    """Where the keyboard is, by Tk's record for the window."""
    try:
        return app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
    except (KeyError, tk.TclError):
        return None


_kv_hidden, _kv_landed = [], 0
if _kv_first is not None and _take_focus(_kv_first):
    for _kv_i in range(70):
        _kv_held = _kv_keyboard()
        if _kv_held is None:
            break
        _kv_held.event_generate('<Tab>')
        _kv_settle(2)
        _kv_held = _kv_keyboard()
        if _kv_held is not None and str(_kv_held).startswith(str(_kv_list)):
            _kv_landed += 1
            if not (_kv_in_view(_kv_held, _kv_list)
                    and _kv_in_view(_kv_held, _kv_page)):
                _kv_hidden.append(str(_kv_held.cget('text')) or 'tick')
check(f'fixture: Tab walked deep into a Trash list longer than its box '
      f'({_kv_landed} landings, the list at {_kv_list.yview()})',
      _kv_landed >= 60 and _kv_list.yview()[0] > 0)
check(f'every Trash control Tab lands on is in sight, in the list and on the '
      f'page ({len(_kv_hidden)} out of sight: {_kv_hidden[:6]})', not _kv_hidden)
app.hide_settings_page()
app.trash = []
NO.save_trash(app.trash)
app.geometry('1100x850')
_kv_settle()

# ---- KEYBOARD: a Tk button its own press destroys hands the keyboard on ----
# Round 2 of the final audit: every "Show N more" goes as it draws the next
# page, and the keyboard fell to the window -- about a hundred Tabs back to
# the rows just drawn. Tk's own buttons take Space through their class
# binding, which never reached _keyboard_stays; nor did a template
# checklist's tick box, whose press draws its list again.
_kr_asked = []
_kr_real_focus_set = tk.Misc.focus_set


def _kr_record(self):
    _kr_asked.append(self)
    return _kr_real_focus_set(self)


def _kr_all(w):
    for c in w.winfo_children():
        yield c
        yield from _kr_all(c)


def _kr_press(widget, top, is_new, click_after=None):
    """Space on *widget*, the keyboard forced there first; then the first
    control under *top* the press drew that *is_new* accepts, and the
    focus_set calls the press made. With *click_after*, a left press on it
    straight after the key, as a click elsewhere would come."""
    if widget is None or not _take_focus(widget):
        return None, []
    before = {str(w) for w in _kr_all(top)}
    del _kr_asked[:]
    widget.event_generate('<space>')
    if click_after is not None:
        click_after.event_generate('<ButtonPress-1>', x=2, y=2)
        click_after.event_generate('<ButtonRelease-1>', x=2, y=2)
    _kv_settle(20)      # Tk runs a Button's command 100 ms after the key
    new = next((w for w in _kr_all(top)
                if str(w) not in before and is_new(w)), None)
    return new, list(_kr_asked)


def _kr_more(top):
    return next((w for w in _kr_all(top) if isinstance(w, tk.Button)
                 and str(w.cget('text')).startswith('Show ')
                 and w.winfo_viewable()), None)


_kr_box = lambda w: isinstance(w, tk.Checkbutton)  # noqa: E731
app.notes = ([NO.normalize_note({'id': 7300 + i, 'title': f'Twin {i // 2:02d}',
                                 'body': f'same {i // 2}'}) for i in range(44)]
             + [NO.normalize_note({'id': 7400 + i, 'title': f'Dated {i:03d}',
                                   'body': 'd', 'date': f'2026-{1 + i // 28:02d}-'
                                                        f'{1 + i % 28:02d}'})
                for i in range(110)])
app.save_notes()
app.refresh_note_list()
app.trash = [{'id': 7600 + i, 'uid': f'kr-{i}', 'title': f'MoreGone{i:02d}',
              'body': 'x', 'category': 'General',
              'deleted_at': f'2026-10-{1 + i % 25:02d} 11:{i:02d}:00'}
             for i in range(30)]
NO.save_trash(app.trash)
app.templates = [{'name': 'KR template', 'title': '', 'body': '', 'comments': '',
                  'category': 'General',
                  'checklist': [{'text': 'one', 'done': False},
                                {'text': 'two', 'done': False}]}]
app.geometry('1000x650')
tk.Misc.focus_set = _kr_record
try:
    app.show_settings_page()
    app.toggle_settings_panel('trash')
    _kv_settle(20)
    _kr_list, _kr_page = app._active_panel_canvas, app.settings_canvas
    _kr_new, _kr_did = _kr_press(_kr_more(app.settings_page), app.settings_page, _kr_box)
    check(f'Space on the Trash\'s "Show 5 more" puts the keyboard on the first '
          f'row it drew, in sight ({_kr_new}, asked {_kr_did[-1:]})',
          _kr_new is not None and _kr_did[-1:] == [_kr_new]
          and _kv_in_view(_kr_new, _kr_list) and _kv_in_view(_kr_new, _kr_page))
    # The counter a closing popup reads: a left click is a click too.
    _kr_heading = find_widget(app.settings_page, tk.Label, 'Recently deleted')
    _kr_was = app._pointer_presses
    if _kr_heading is not None:
        _kr_heading.event_generate('<ButtonPress-1>', x=2, y=2)
        _kr_heading.event_generate('<ButtonRelease-1>', x=2, y=2)
        _kv_settle(2)
    check(f'a left click is counted as a click ({_kr_was} -> {app._pointer_presses})',
          _kr_heading is not None and app._pointer_presses == _kr_was + 1)
    app.toggle_settings_panel('duplicates')
    _kv_settle(20)
    _kr_list = app._active_panel_canvas
    # A click straight after the key put the keyboard where it wanted.
    _kr_heading = find_widget(app.settings_page, tk.Label, 'Duplicates')
    _kr_new, _kr_did = _kr_press(_kr_more(app.settings_page), app.settings_page,
                                 _kr_box, click_after=_kr_heading)
    check(f'...and a click straight after Space on "Show more" keeps the keyboard '
          f'out of the list ({_kr_did})', _kr_new is not None and not any(
              str(w).startswith(str(_kr_list)) for w in _kr_did))
    app.toggle_settings_panel('duplicates')
    _kv_settle(20)
    _kr_list = app._active_panel_canvas
    _kr_new, _kr_did = _kr_press(_kr_more(app.settings_page), app.settings_page, _kr_box)
    check(f'Space on Duplicates\' "Show 2 more groups" puts the keyboard on the '
          f'first copy it drew, in sight ({_kr_new}, asked {_kr_did[-1:]})',
          _kr_new is not None and _kr_did[-1:] == [_kr_new]
          and _kv_in_view(_kr_new, _kr_list))
    app.toggle_settings_panel('templates')
    _kv_settle(20)
    app._edit_template(app.templates[0], redraw=lambda: None)
    _kv_settle(10)
    _kr_ed = app._mini_popup
    _kr_tick = next((w for w in _kr_all(_kr_ed) if isinstance(w, tk.Checkbutton)), None)
    _kr_new, _kr_did = _kr_press(_kr_tick, _kr_ed, _kr_box)
    # The first item's box is the first box drawn again.
    check(f'Space on a template checklist\'s tick box, which draws the list again, '
          f'leaves the keyboard on that item\'s new box ({_kr_new}, asked {_kr_did[-1:]})',
          _kr_tick is not None and _kr_new is not None and _kr_did[-1:] == [_kr_new])
    app._dismiss_mini_popup()
    _kv_settle()
    app.hide_settings_page()
    app.toggle_share_panel()
    _kv_settle(20)
    _kr_share = app._share_checklist_canvas
    _kr_new, _kr_did = _kr_press(_kr_more(_kr_share), _kr_share, _kr_box)
    check(f'Space on the Share list\'s "Show 54 more" puts the keyboard on the '
          f'first box it drew, in sight ({_kr_new}, asked {_kr_did[-1:]})',
          _kr_new is not None and _kr_did[-1:] == [_kr_new]
          and _kv_in_view(_kr_new, _kr_share))
    app.toggle_share_panel()
    app.notebook.select(app.TAB_CALENDAR)
    _kv_settle(10)
    app._show_calendar_history()
    _kv_settle(20)
    _kr_rows = app._history_rows
    _kr_new, _kr_did = _kr_press(_kr_more(_kr_rows), _kr_rows,
                                 lambda w: getattr(w, '_key_press', None) is not None)
    check(f'Space on History\'s "Show more" puts the keyboard on the first row it '
          f'drew, in sight ({_kr_new}, asked {_kr_did[-1:]})',
          _kr_new is not None and _kr_did[-1:] == [_kr_new]
          and _kv_in_view(_kr_new, app.cal_scroll_canvas))
    app._hide_calendar_history()
finally:
    tk.Misc.focus_set = _kr_real_focus_set
if getattr(app, '_settings_open', False):
    app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.notes = []
app.save_notes()
app.refresh_note_list()
app.trash, app.templates = [], []
NO.save_trash(app.trash)
app.geometry('1100x850')
_kv_settle()

# Text size, the app's own setting for reading, from the keyboard alone: it
# was a frame and two labels Tab never stopped on.
app.show_settings_page()
app.toggle_settings_panel('appearance')
_kv_settle(20)


def _ks_dropdown_showing(text):
    found = []

    def walk(w):
        for c in w.winfo_children():
            if (isinstance(c, tk.Frame) and getattr(c, '_key_press', None)
                    and any(isinstance(k, tk.Label) and str(k.cget('text')) == text
                            for k in c.winfo_children())):
                found.append(c)
            walk(c)
    walk(app.settings_content)
    return found[0] if found else None


_ks_size = app.editor_font_size
_ks_dd = _ks_dropdown_showing(str(_ks_size))
_ks_chain, _ks_at = [], str(app._settings_nav_buttons['appearance'])
for _ in range(40):
    _ks_at = str(app.tk.call('tk_focusNext', _ks_at))
    _ks_chain.append(_ks_at)
check(f'Tab from Appearance in the menu reaches the Text size dropdown '
      f'({len(_ks_chain)} stops looked at)',
      _ks_dd is not None and str(_ks_dd) in _ks_chain)
_ks_pop, _ks_rows = None, []
if _ks_dd is not None and _take_focus(_ks_dd):
    _ks_dd.event_generate('<space>')
    _kv_settle()
    _ks_pop = app._mini_popup
    _ks_rows = [c for c in (_ks_pop.winfo_children()[0].winfo_children()
                            if _ks_pop is not None and _ks_pop.winfo_exists() else [])
                if getattr(c, '_key_press', None)]
_ks_next = next((i + 1 for i, r in enumerate(_ks_rows)
                 if r._key_current and i + 1 < len(_ks_rows)), None)
if _ks_next is not None and _take_focus(_ks_rows[_ks_next]):
    _ks_rows[_ks_next].event_generate('<Return>')
    _kv_settle()
check(f'Space opens it and Return on the next size chooses it '
      f'({_ks_size} -> {app.editor_font_size})',
      _ks_next is not None
      and app.editor_font_size == NO.FONT_SIZES[NO.FONT_SIZES.index(_ks_size) + 1])
app._set_editor_font(size=_ks_size)
app.hide_settings_page()
_kv_settle()

# ---- KEYBOARD: every control a click acts on, Tab reaches ----
# Canvases, labels and frames of labels bound only to the mouse were out of
# Tab's reach: a category's rename, colour and delete, a template's edit,
# the themes, Light/Dark, the alignment, the sidebar's arrow. Asked of every
# page: a widget a click acts on is a Tab stop, inside one, or names the
# Tab stop that does the same (_key_route). The tooltip's own click, which
# only hides the tip, acts on nothing.
_kb_hide = str(getattr(app, '_hide_tooltip_command', '')) or None


def _kb_tab_chain():
    seen, at = [], str(app)
    for _ in range(800):
        at = str(app.tk.call('tk_focusNext', at))
        if not at or at in seen:
            break
        seen.append(at)
    return set(seen)


def _kb_clicked(w):
    own = [str(w.bind(s)).strip() for s in ('<Button-1>', '<ButtonPress-1>',
                                             '<ButtonRelease-1>') if w.bind(s)]
    acts = [o for o in own if o.lstrip('+').strip() != _kb_hide]
    return (bool(acts) or isinstance(w, (tk.Button, tk.Checkbutton, tk.Radiobutton))
            or str(w.cget('cursor')) == 'hand2')


def _kb_unreachable(top):
    chain = _kb_tab_chain()
    out = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Toplevel) or not c.winfo_viewable():
                continue
            if _kb_clicked(c):
                route = getattr(c, '_key_route', None)
                anc, ok = c, route is not None and str(route) in chain
                while anc is not None and not ok:
                    # The tab strip is a Tab stop, and no key of its own
                    # reaches into a page: an attachment's name passed as
                    # "inside" it while the keyboard could not open it.
                    ok = str(anc) in chain and (
                        anc is c or anc.winfo_class() != 'TNotebook')
                    anc = anc.master
                if not ok:
                    text = str(c.cget('text'))[:20] if 'text' in c.keys() else ''
                    out.append(f"{c.winfo_class()} {text!r}"
                               f"{' ' + c._icon_kind if hasattr(c, '_icon_kind') else ''}")
            walk(c)
    walk(top)
    return sorted(set(out))


NO.CATEGORY_COLORS.setdefault('Work', '#7c5cff')
app.templates = [{'name': 'KbTemplate', 'title': 'x', 'body': 'y', 'category': 'General'}]
app.notes = [{'id': 801, 'title': 'KbNote', 'body': 'x', 'category': 'Work',
              'date': '2026-10-02', 'created': '2026-01-01 00:00',
              'updated': '2026-01-01 00:00', 'checklist': [],
              'attachments': [{'filename': 'kb.pdf',
                               'stored_as': '20261002120000000000_kb.pdf'},
                              {'filename': 'kb.png',
                               'stored_as': '20261002120000000000_kb.png'}]}]
with open(os.path.join(NO.ATTACHMENTS_DIR, '20261002120000000000_kb.pdf'), 'wb') as f:
    f.write(b'%PDF-1.4')
import PIL.Image as _kb_Image
_kb_Image.new('RGB', (40, 30), (200, 40, 40)).save(
    os.path.join(NO.ATTACHMENTS_DIR, '20261002120000000000_kb.png'))
app.trash = [{'id': 802, 'uid': 'kb-t', 'title': 'KbGone', 'body': 'x', 'category': 'General',
              'deleted_at': '2026-10-20 10:00:00'}]
app.save_notes(); NO.save_trash(app.trash)
app.refresh_note_list()
app.notebook.select(app.TAB_NOTES)
app.open_note_in_tab(app.notes[0])
_kv_settle(10)
_kb_where = {'the notes page': _kb_unreachable(app)}
# An attachment opens from the keyboard as a click opens it: its name was a
# label bound to the mouse alone, and only the remove ✕ beside it was a Tab
# stop. A picture's preview takes the keyboard on its Close, Escape shuts
# it, and the keyboard goes back to the row.
_ka_names = [w for w in app.attachments_frame.winfo_children()
             for w in w.winfo_children() for w in w.winfo_children()
             if isinstance(w, tk.Label) and getattr(w, '_key_press', None)]
_ka_opened = []
_ka_real_start = getattr(NO.os, 'startfile', None)
NO.os.startfile = lambda p, *a, **k: _ka_opened.append(os.path.basename(p))
_ka_preview = _ka_on_close = _ka_shut = _ka_back = False


def _ka_holder():
    try:
        return app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
    except (KeyError, tk.TclError):
        return None


try:
    if len(_ka_names) == 2 and _take_focus(_ka_names[0]):
        _ka_names[0].event_generate('<space>')
        _kv_settle()
    if len(_ka_names) == 2 and _take_focus(_ka_names[1]):
        _ka_names[1].event_generate('<Return>')
        _kv_settle()
        _ka_pop = app._mini_popup
        _ka_preview = _ka_pop is not None and bool(_ka_pop.winfo_exists())
        _ka_held = _ka_holder()
        _ka_on_close = (_ka_preview and isinstance(_ka_held, tk.Button)
                        and str(_ka_held).startswith(str(_ka_pop) + '.')
                        and 'Close' in str(_ka_held.cget('text')))
        (_ka_held or app).event_generate('<Escape>')
        _kv_settle()
        _ka_shut = app._mini_popup is None
        _ka_back = _ka_holder() is _ka_names[1]
except tk.TclError as _ka_exc:
    print(f'  (attachment keys raised {_ka_exc!r})')
finally:
    app._dismiss_mini_popup()
    if _ka_real_start is None:
        del NO.os.startfile
    else:
        NO.os.startfile = _ka_real_start
check(f"Space on an attachment's name opens the file, as a click does "
      f"({len(_ka_names)} names are Tab stops; opened {_ka_opened})",
      len(_ka_names) == 2 and _ka_opened == ['20261002120000000000_kb.pdf'])
check(f"...Return on a picture's shows it with the keyboard on Close ({_ka_preview}, "
      f"{_ka_on_close}), Escape shuts it ({_ka_shut}), and the keyboard goes back "
      f"to the row ({_ka_back})",
      _ka_preview and _ka_on_close and _ka_shut and _ka_back)
# A click's preview takes the keyboard too, and Tab stays on its two buttons:
# a frame over the window, it left the caret in the note under it and Tab
# walked there, so keys typed at a picture edited a note nobody could see.
_kp_inside, _kp_pop, _kp_typed, _kp_open, _kp_back = [], None, None, False, False
_kp_in_body = False
try:
    _kp_in_body = _take_focus(app.body_text)
    app.body_text.tag_add('sel', '1.0', 'end-1c')
    _qa_click(_ka_names[1])
    _kv_settle()
    _kp_pop = app._mini_popup
    # Generated on the window, so Tk sends each key where the keyboard is.
    for _kp_key in ('<KeyPress-Delete>', '<KeyPress-BackSpace>', '<KeyPress-x>'):
        app.event_generate(_kp_key)
        _kv_settle(2)
    _kp_typed = app.body_text.get('1.0', 'end-1c')
    for _kp_key in ['<Tab>'] * 3 + ['<Shift-Tab>'] * 3:
        app.event_generate(_kp_key)
        _kv_settle(2)
        _kp_h = _ka_holder()
        _kp_inside.append(_kp_h is not None and _kp_pop is not None
                          and str(_kp_h).startswith(str(_kp_pop) + '.'))
    _kp_open = _kp_pop is not None and app._mini_popup is _kp_pop
    app.event_generate('<Escape>')
    _kv_settle()
    _kp_back = _ka_holder() is app.body_text
finally:
    app._dismiss_mini_popup()
app._flush_autosave()
_kp_saved = (app.find_note(801) or {}).get('body')
check(f"a picture's preview opened by a click takes the keyboard, so keys "
      f"typed at it leave the note alone ({_kp_in_body}, body {_kp_typed!r}, "
      f"saved {_kp_saved!r}), and Escape gives it back ({_kp_back})",
      _kp_in_body and _kp_pop is not None and _kp_typed == 'x'
      and _kp_saved == 'x' and _kp_back)
check(f"...and Tab and Shift+Tab walk its two buttons only ({_kp_inside}, "
      f"still open {_kp_open})", len(_kp_inside) == 6 and all(_kp_inside)
      and _kp_open)
# Round 6: Enter presses the preview's button the keyboard is on, as Space
# does and as a question's answers take it -- a Tk button answers Space alone,
# and Enter on Close did nothing. And Open externally opens the picture: a
# name reused below it in the same function made it open the overlay's name.
# The keypad's Enter is asked where Tk can make one: Tk on Windows has no
# keycode for KP_Enter (qa9's questions say the same).
_kr_seen, _kr_opened = {}, []
_kr_keys = [('<Return>', 0), ('<Return>', 1)]
if not sys.platform.startswith('win'):
    _kr_keys.insert(1, ('<KP_Enter>', 0))
app._open_externally = lambda path, *a, **k: _kr_opened.append(os.path.basename(path))
try:
    for _kr_key, _kr_steps in _kr_keys:
        _take_focus(app.body_text)
        _qa_click(_ka_names[1])
        _kv_settle()
        _kr_pop = app._mini_popup
        for _ in range(_kr_steps):                      # Tab to Open externally
            app.event_generate('<Tab>')
            _kv_settle(2)
        _kr_held = _ka_holder()
        _kr_on = (str(_kr_held.cget('text'))
                  if isinstance(_kr_held, tk.Button) and _kr_pop is not None
                  and str(_kr_held).startswith(str(_kr_pop) + '.') else None)
        if _kr_on is not None:
            _kr_held.event_generate(_kr_key)
            _kv_settle()
        _kr_seen[f'{_kr_key} on {_kr_on}'] = (app._mini_popup is None,
                                              _ka_holder() is app.body_text)
finally:
    del app._open_externally
    app._dismiss_mini_popup()
    _kv_settle()
check(f"Enter (and the keypad's, off Windows) presses the preview's Close, and its "
      f"Open externally opens the picture ((closed, keyboard back in the note): "
      f"{_kr_seen}; opened {_kr_opened})",
      _kr_seen == {f'{k} on {"Open externally" if s else "✕ Close"}': (True, True)
                   for k, s in _kr_keys}
      and _kr_opened == ['20261002120000000000_kb.png'])
# Round 7: Enter held on a picture's name presses it once. The preview gave
# its Close the keyboard, Close took the next repeat and shut it, the name got
# the keyboard back and the next one, and the preview opened and shut over and
# over. A held key repeats as presses alone on Windows, as a release and a
# press at one time on X11: both are sent, with times, as a held key's come.
# And let go of, Enter presses again.
_kh_built, _kh_seen = [], {}
_kh_real_build = app._build_image_preview
app._build_image_preview = lambda *a, **k: (_kh_built.append(1),
                                            _kh_real_build(*a, **k))[1]
# Its keys carry times, as a keyboard's do, and are this check's own: kept
# out of the run's REAL KEYS (_qa_support), which would say someone typed.
import _qa_support as _kh_support
_kh_keys_kept = _kh_support.REAL_KEYS
_kh_support.REAL_KEYS = [('the held-Enter check', 'its own keys')]


def _kh_key(kind, when):
    (_ka_holder() or app).event_generate(f'<Key{kind}-Return>', time=when)
    _kv_settle(2)


def _kh_on():
    held, pop = _ka_holder(), app._mini_popup
    if pop is not None and held is not None and str(held).startswith(str(pop) + '.'):
        return str(held.cget('text'))
    return 'the name' if held is _ka_names[1] else str(held)[-24:]


try:
    for _kh_shape, _kh_t in (('presses alone', 100_000), ('release and press', 200_000)):
        del _kh_built[:]
        _take_focus(_ka_names[1])
        _kh_key('Press', _kh_t)
        for _kh_i in range(10):
            _kh_when = _kh_t + 500 + 33 * _kh_i
            if _kh_shape == 'release and press':
                _kh_key('Release', _kh_when)
            _kh_key('Press', _kh_when)
        _kh_key('Release', _kh_t + 900)
        _kh_seen[f'held on the name, {_kh_shape}'] = (len(_kh_built), _kh_on())
        _kh_key('Press', _kh_t + 1500)                 # pressed again: Close
        for _kh_i in range(10):
            _kh_when = _kh_t + 2000 + 33 * _kh_i
            if _kh_shape == 'release and press':
                _kh_key('Release', _kh_when)
            _kh_key('Press', _kh_when)
        _kh_key('Release', _kh_t + 2400)
        _kh_seen[f'held on Close, {_kh_shape}'] = (len(_kh_built), _kh_on(),
                                                   app._mini_popup is None)
finally:
    app._build_image_preview = _kh_real_build
    app._dismiss_mini_popup()
    _kv_settle()
    _kh_support.REAL_KEYS = _kh_keys_kept
check(f"Enter held on a picture's name opens its preview once, and held on its "
      f"Close shuts it once ((previews built, the keyboard on): {_kh_seen})",
      _kh_seen == {f'held on the name, {s}': (1, '✕ Close') for s in
                   ('presses alone', 'release and press')}
      | {f'held on Close, {s}': (1, 'the name', True) for s in
         ('presses alone', 'release and press')})
# Round 5: Ctrl+F and Ctrl+N gave the keyboard to a box under the preview,
# left open over it, and the keys went into a note nobody could see. The
# shortcut closes it, as a click outside does. Ctrl+N last: it clears the note.
_ks_seen = {}
try:
    for _ks_key, _ks_box in (('<Control-f>', lambda: getattr(app, '_find_entry', None)),
                             ('<Control-n>', lambda: app.title_entry)):
        _take_focus(app.body_text)
        _qa_click(_ka_names[1])
        _kv_settle()
        _ks_pop, _ks_held = app._mini_popup, _ka_holder()
        _ks_ready = (_ks_pop is not None and _ks_held is not None
                     and str(_ks_held).startswith(str(_ks_pop) + '.'))
        app.event_generate(_ks_key)
        _kv_settle()
        _ks_seen[_ks_key] = (_ks_ready, app._mini_popup is None,
                             _ka_holder() is _ks_box())
        app._close_find()
        _kv_settle()
finally:
    app._dismiss_mini_popup()
app.open_note_in_tab(app.find_note(801))
_kv_settle(6)
check(f"Ctrl+F and Ctrl+N close a picture's preview before they give the keyboard "
      f"to the box under it ((preview had it, closed, in the box): {_ks_seen})",
      len(_ks_seen) == 2 and all(v == (True, True, True) for v in _ks_seen.values()))
app.notebook.select(app.TAB_CALENDAR)
app.cal_year, app.cal_month = 2026, 10
app.render_calendar()
_kv_settle(10)
app.open_day_popup('2026-10-02')
_kv_settle(10)
_kb_where['the calendar, a day open'] = _kb_unreachable(app)
app._toggle_calendar_history()
_kv_settle(10)
_kb_where['the History register'] = _kb_unreachable(app)
app._toggle_calendar_history()
app.notebook.select(app.TAB_NOTES)
app.show_settings_page()
for _kb_key, _kb_label, _b, _e in app.SETTINGS_SECTIONS:
    app.toggle_settings_panel(_kb_key)
    _kv_settle(6)
    _kb_where['Settings, ' + _kb_label] = _kb_unreachable(app.settings_page)
_kb_missing = {k: v for k, v in _kb_where.items() if v}
check(f'every control a click acts on, on every page, is a Tab stop or inside one '
      f'({len(_kb_where)} pages; out of reach: {_kb_missing})', not _kb_missing)

# The drawn ones press from the keyboard too, and the keyboard stays where
# a press that redraws the list put it back.
app.toggle_settings_panel('categories')
_kv_settle(10)


def _kb_icons(kind):
    found = []

    def walk(w):
        for c in w.winfo_children():
            if getattr(c, '_icon_kind', None) == kind and getattr(c, '_key_press', None):
                found.append(c)
            walk(c)
    walk(app.settings_content)
    return found


_kb_renamed = []
_kb_real_rename = app._show_inline_rename
app._show_inline_rename = lambda anchor, current, on_save: _kb_renamed.append(current)
try:
    _kb_pencil = _kb_icons('pencil')
    if _kb_pencil and _take_focus(_kb_pencil[0]):
        _kb_pencil[0].event_generate('<space>')
        _kv_settle()
finally:
    del app._show_inline_rename
_kb_first = [k for k in NO.CATEGORY_COLORS if k != NO.PROTECTED_CATEGORY][:1]
check(f'Space on a category\'s pencil renames it, as a click does ({_kb_renamed})',
      _kb_first and _kb_renamed == _kb_first)
app.toggle_settings_panel('appearance')
_kv_settle(10)
_kb_theme = app.theme_name
_kb_ring = False


def _kb_theme_tiles():
    found = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Frame) and getattr(c, '_key_press', None):
                found.append(c)
            walk(c)
    walk(app.theme_picker_frame)
    return found


_kb_tiles = _kb_theme_tiles()
_kb_target = _kb_tiles[1] if len(_kb_tiles) > 1 else None
if _kb_target is not None and _take_focus(_kb_target):
    _kv_settle(2)       # its <FocusIn>, which Tk may hand over after the focus
    _kb_ring = str(_kb_target.cget('bg')).lower() == app._focus_ring().lower()
    _kb_target.event_generate('<Return>')
    _kv_settle(10)
_kb_after = _kb_theme_tiles()
_kb_held = None
try:
    _kb_held = app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
except (KeyError, tk.TclError):
    pass
check(f'a theme tile is a Tab stop ringed in the keyboard\'s colour, and Return '
      f'chooses it ({_kb_ring}, {_kb_theme} -> {app.theme_name})',
      _kb_target is not None and _kb_ring and app.theme_name != _kb_theme)
check(f'...and the keyboard is on that tile, drawn again in the new theme '
      f'({_kb_held}; {[getattr(w, "_theme_name", None) for w in _kb_after[:2]]})',
      len(_kb_after) > 1 and _kb_held is _kb_after[1])
app.set_theme(_kb_theme)
_kv_settle(6)
_kb_mode = app.theme_name in NO.DARK_THEMES
_kb_switch = app._settings_mode_buttons['light' if _kb_mode else 'dark']
if _take_focus(_kb_switch):
    _kb_switch.event_generate('<space>')
    _kv_settle(6)
check('Space on the Light/Dark switch flips the theme',
      (app.theme_name in NO.DARK_THEMES) != _kb_mode)
app.set_theme(_kb_theme)
app.hide_settings_page()
app.notes = []; app.trash = []; app.templates = []
app.save_notes(); NO.save_trash(app.trash)
app.refresh_note_list()
_kv_settle()

# ---- KEYBOARD: the way out of the note, and what Text size promises ----
# In the note body Tab types a tab, so the one way out is Tk's Ctrl+Tab --
# and the page saying "Everything the keyboard can do" never named it.
_kw_groups = dict((g[0], [c for c, _d in g[1]]) for g in app.SHORTCUT_GROUPS)
check(f'the shortcuts page names, under Anywhere, the way out of the note and '
      f'Escape ({_kw_groups.get("Anywhere")})',
      'Ctrl+Tab  /  Ctrl+Shift+Tab' in _kw_groups.get('Anywhere', [])
      and 'Escape' in _kw_groups.get('Anywhere', []))
app.notebook.select(app.TAB_NOTES)
app.new_note()
_kv_settle()
_kw_next = app.body_text.tk_focusNext()
if _take_focus(app.body_text):
    app.body_text.event_generate('<Control-Tab>')
    _kv_settle()
_kw_held = None
try:
    _kw_held = app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
except (KeyError, tk.TclError):
    pass
check(f'...and Ctrl+Tab does leave the note, for the control after it ({_kw_held})',
      _kw_held is _kw_next and app.body_text.get('1.0', 'end-1c') == '')
# Text size makes the notes bigger, not the rest of the app: its words say so.
def _walk_all(w):
    for c in w.winfo_children():
        yield c
        yield from _walk_all(c)


app.show_settings_page()
app.toggle_settings_panel('appearance')
_kv_settle(6)
_kw_hint = [str(w.cget('text')) for w in _walk_all(app.settings_content)
            if isinstance(w, tk.Label) and str(w.cget('text')).startswith('Bigger text')]
check(f'the Text size row promises bigger text in every note, not everywhere '
      f'({_kw_hint})', _kw_hint == ['Bigger text in every note, without '
                                    'reformatting a single one.'])
app.hide_settings_page()
_kv_settle()

# ---- KEYBOARD: the Settings page scrolled from the keyboard ----
# Round 2 of the final audit: Keyboard shortcuts is labels alone, nothing to
# Tab to, and four fifths of it lay below the fold with no key to reach it --
# the page telling keyboard users how to use the keyboard.
app.geometry('1100x750')
app.show_settings_page()
app.toggle_settings_panel('shortcuts')
_kv_settle(10)
_kp_page = app.settings_canvas
_kp_nav = app._settings_nav_buttons.get('shortcuts')


def _kp_key(widget, key):
    """*key* on *widget*, the keyboard forced there first; the page's top."""
    if widget is not None and _take_focus(widget):
        widget.event_generate(key)
        _kv_settle(2)
    return _kp_page.yview()


_kp_page.yview_moveto(0)
_kv_settle(2)
check(f'fixture: most of Keyboard shortcuts lies below the fold ({_kp_page.yview()})',
      _kp_page.yview()[1] < 0.6)
_kp_down = _kp_key(_kp_nav, '<Next>')[0]
_kp_end = _kp_key(_kp_nav, '<End>')[1]
_kp_home = _kp_key(_kp_nav, '<Home>')[0]
_kp_arrow = _kp_key(_kp_nav, '<Down>')[0]
check(f'with the keyboard on its menu entry, Page Down, End, Home and Down '
      f'scroll the page ({_kp_down:.2f}, {_kp_end:.2f}, {_kp_home:.2f}, '
      f'{_kp_arrow:.2f})',
      _kp_down > 0.1 and _kp_end > 0.999 and _kp_home == 0.0
      and 0.0 < _kp_arrow < _kp_down)
_kp_groups = ' '.join(c for t, rows in app.SHORTCUT_GROUPS
                      if t.startswith('Settings') for c, _d in rows)
check(f'...and the page names them, in a Settings group ({_kp_groups!r})',
      'Page Up' in _kp_groups and 'Page Down' in _kp_groups)
# In a box being typed in, End is the box's own. No section that runs past
# the window holds one, so a box is put on this one for the question.
_kp_box = tk.Entry(app.settings_shortcuts_panel)
_kp_box.insert(0, 'typed')
_kp_box.pack(before=app.settings_shortcuts_panel.winfo_children()[0])
_kp_page.yview_moveto(0)
_kv_settle(4)
_kp_still = _kp_key(_kp_box, '<End>')[0]
check(f'...but in a text box on the page, End stays the box\'s own (the page '
      f'at {_kp_still}, the caret at {_kp_box.index("insert")})',
      _kp_still == 0.0 and _kp_box.index('insert') == 5)
_kp_box.destroy()
app.hide_settings_page()
app.geometry('1100x850')
_kv_settle()


# ---- KEYBOARD: a Tk button whose own press hides it ----
# Round 3 of the final audit: Tk's buttons hand the keyboard on after a press
# that destroys them, and one that only HID itself kept it -- on a control no
# longer on screen, no ring anywhere, Tab starting again from the window's
# top. Share and Import's Close, the Trash's bulk delete, Settings and
# Back to Notes.
def _kh_space(button):
    """Space on *button*, the keyboard forced there first: where it is after."""
    if button is None:
        return 'no button'
    app._bring_into_sight(button)
    _kv_settle(4)
    if not _take_focus(button):
        return (f'not taken (viewable {button.winfo_viewable()}, keyboard on '
                f'{app.tk.call("focus", "-lastfor", app)})')
    button.event_generate('<space>')
    _kv_settle(15)
    try:
        held = app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
        if held is button or not held.winfo_viewable():
            return f'hidden {held.winfo_class()}'
    except (KeyError, tk.TclError):
        return 'nowhere'
    return 'in sight'


_kh_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
_kh = {}
try:
    app.geometry('1100x850')
    app.notebook.select(app.TAB_NOTES)
    app.notes = [NO.normalize_note({'id': 901, 'title': 'KhOne', 'body': 'x',
                                    'date': '2026-10-02'}),
                 NO.normalize_note({'id': 902, 'title': 'KhTwo', 'body': 'y'})]
    app.trash = [{'id': 903 + _i, 'uid': f'kh-{_i}', 'title': f'KhGone{_i}',
                  'body': 'x', 'category': 'General',
                  'deleted_at': '2026-10-20 10:00:00'} for _i in range(3)]
    app.save_notes(); NO.save_trash(app.trash)
    app.refresh_note_list()
    _kv_settle(6)
    app.toggle_share_panel()
    _kv_settle(6)
    _kh['Share Close'] = _kh_space(find_btn_qa6(app.share_panel, 'Close'))
    app.toggle_import_panel()
    _kv_settle(6)
    _kh['Import Close'] = _kh_space(find_btn_qa6(app.import_panel, 'Close'))
    # The day's ✕ goes the same road. It was walked in a fresh app; here, this
    # far into the script, its button would not take the keyboard to begin
    # with (not viewable), for a reason the round did not find.
    _kh['⚙ Settings'] = _kh_space(find_btn_qa6(app.sidebar, '⚙ Settings'))
    app.toggle_settings_panel('trash')
    _kv_settle(10)

    def _kh_rows(w):
        for c in w.winfo_children():
            if getattr(c, '_trash_buttons', None):
                yield c
            else:
                yield from _kh_rows(c)

    for _kh_row in list(_kh_rows(app.settings_trash_panel))[:2]:
        next(c for c in _kh_row.winfo_children()
             if isinstance(c, tk.Checkbutton)).invoke()
    _kv_settle(6)
    _kh['the Trash\'s bulk delete'] = _kh_space(
        find_btn_qa6(app.settings_trash_panel, 'Delete 2 selected permanently'))
    _kh['Back to Notes'] = _kh_space(find_btn_qa6(app.settings_page, 'Back to Notes'))
finally:
    app.ask_yes_no = _kh_real_ask
    if getattr(app, '_settings_open', False):
        app.hide_settings_page()
    if app._is_placed(app.share_panel) or app._is_placed(app.import_panel):
        app.share_panel.pack_forget(); app.import_panel.pack_forget()
check(f'a Tk button whose own press hides it hands the keyboard to a control '
      f'in sight ({_kh})',
      len(_kh) == 5 and all(v == 'in sight' for v in _kh.values()))
check('...and the Trash\'s bulk delete did delete the two ticked',
      len(app.trash) == 1)
app.notes = []; app.trash = []
app.save_notes(); NO.save_trash(app.trash)
app.refresh_note_list()
_kv_settle()

# ---- KEYBOARD: Settings opened by a click, from the note ----
# Round 3 of the final audit: a click on ⚙ Settings takes no keyboard, which
# stayed in the note body, out of sight. Page Down moved its caret instead of
# the page, and Tab, letters and Backspace edited the note, which was saved.
def _ks_holder():
    try:
        return app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
    except (KeyError, tk.TclError):
        return None


app.geometry('1100x750')
app.notebook.select(app.TAB_NOTES)
app.notes = [NO.normalize_note({'id': 911, 'title': 'KsNote',
                                'body': 'milk\neggs\nbread'})]
app.save_notes()
app.refresh_note_list()
app.open_note_in_tab(app.notes[0])
_kv_settle(6)
_ks_in_body = _take_focus(app.body_text)
app.body_text.mark_set('insert', 'end-1c')
find_btn_qa6(app.sidebar, '⚙ Settings').invoke()      # a click: no keyboard
_kv_settle(6)
_ks_on_page = str(getattr(_ks_holder(), '_w', '')).startswith(str(app.settings_page) + '.')
app.toggle_settings_panel('shortcuts')
_kv_settle(10)
app.settings_canvas.yview_moveto(0)
_kv_settle(2)
_ks_top = app.settings_canvas.yview()[0]
# Generated on the window, so Tk sends each key where the keyboard is.
for _ks_key in ('<Next>', '<Tab>', '<KeyPress-x>', '<KeyPress-BackSpace>'):
    app.event_generate(_ks_key)
    _kv_settle(2)
_ks_scrolled = app.settings_canvas.yview()[0]
_ks_body = app.body_text.get('1.0', 'end-1c')
find_btn_qa6(app.settings_page, 'Back to Notes').invoke()
_kv_settle(6)
_ks_back = _ks_holder() is app.body_text
app._flush_autosave()
_ks_saved = (app.find_note(911) or {}).get('body')
check(f'a click on Settings from the note brings the keyboard onto the page '
      f'({_ks_in_body}, {_ks_on_page}): Page Down scrolls it ({_ks_top:.2f} -> '
      f'{_ks_scrolled:.2f}) and no key reaches the hidden note ({_ks_body!r}, '
      f'saved {_ks_saved!r})',
      _ks_in_body and _ks_on_page and _ks_scrolled > _ks_top
      and _ks_body == 'milk\neggs\nbread' and _ks_saved == 'milk\neggs\nbread')
check(f'...and a click on Back to Notes gives the keyboard back to the note '
      f'({_ks_holder()})', _ks_back)
# A box out of sight is no box being typed in: whatever left the keyboard in
# one, Page Down still reads the page on.
_take_focus(app.body_text)
app._keyboard_to = lambda target: None    # as if nothing had moved it
app._keyboard_off_part = lambda held: None    # the put-away watcher neither
try:
    app.show_settings_page()
finally:
    del app._keyboard_to
app.toggle_settings_panel('shortcuts')
_kv_settle(10)
app.settings_canvas.yview_moveto(0)
_kv_settle(2)
_ks_left = _ks_holder() is app.body_text
app.event_generate('<Next>')
_kv_settle(2)
_ks_paged = app.settings_canvas.yview()[0]
del app._keyboard_off_part
app.hide_settings_page()
_kv_settle(4)
check(f'...and with the keyboard left in the hidden note, Page Down still '
      f'scrolls the page ({_ks_left}, {_ks_paged:.2f})',
      _ks_left and _ks_paged > 0)
# The same for the note list, put away by a click on its arrow.
_ks_list = _take_focus(app.canvas)
_qa_click(app.sidebar_toggle)
_kv_settle(6)
_ks_arrow = _ks_holder() is app.sidebar_toggle and bool(app.sidebar_toggle.winfo_viewable())
if app._sidebar_hidden:
    app.toggle_sidebar()
_kv_settle(4)
check(f'a click on the sidebar\'s arrow with the keyboard on the note list '
      f'brings it to the arrow ({_ks_list}, {_ks_holder()})', _ks_list and _ks_arrow)
app.notes = []
app.save_notes()
app.refresh_note_list()
_kv_settle()

# ---- THE TEMPLATE EDITOR'S TABLE PREVIEW SHORTENS A LONG CELL BY HALVES ----
# Round 3 of the final audit: a cell wider than its column was shortened a
# letter at a time, the rest measured whole at each step, on every key typed
# in the body: 2 s a key at 12 rows of 1,200 characters, minutes for one long
# cell. Counted in measures asked of Tk, never in time.
import tkinter.font as _tp_font
_tp_cell = 'lorem ipsum ' * 500
_tp_body = tk.Text(app)
_tp_body.insert('1.0', '| Item | Notes |\n| --- | --- |\n| one | ' + _tp_cell + ' |')
_tp_canvas = tk.Canvas(app)
_tp_calls = [0]
_tp_real_measure = _tp_font.Font.measure


def _tp_count(self, *a, **k):
    _tp_calls[0] += 1
    return _tp_real_measure(self, *a, **k)


_tp_font.Font.measure = _tp_count
try:
    app._measure_text_cache = {}        # the first drawing: nothing remembered
    app._draw_template_table_preview(_tp_canvas, _tp_body)
    _tp_first = _tp_calls[0]
    app._draw_template_table_preview(_tp_canvas, _tp_body)
    _tp_again = _tp_calls[0] - _tp_first
finally:
    _tp_font.Font.measure = _tp_real_measure
_tp_shown = [_tp_canvas.itemcget(i, 'text') for i in _tp_canvas.find_all()
             if _tp_canvas.type(i) == 'text'
             and _tp_canvas.itemcget(i, 'text').startswith('lorem')]
_tp_body.destroy(); _tp_canvas.destroy()
check(f'the template preview shortens a {len(_tp_cell):,}-character cell in a few '
      f'dozen measures, not one per letter ({_tp_first}, then {_tp_again} drawn '
      f'again; shows {_tp_shown[0][:16] if _tp_shown else None!r}...)',
      _tp_first <= 80 and _tp_again <= 4 and len(_tp_shown) == 1
      and _tp_shown[0].endswith('…') and len(_tp_shown[0]) < 100
      and _tp_cell.startswith(_tp_shown[0][:-1]))

# ---- THE TEMPLATE EDITOR'S BOXES HAVE LIMITS OF THEIR OWN ----
# Round 3 of the final audit: the checklist's box took a paste of any length,
# one item drawn as one label as tall as its text, and so did the template's
# name and title. Each keeps a limit now, as the note's own title box does.
def _tl_entries(w):
    for c in w.winfo_children():
        if isinstance(c, tk.Entry):
            yield c
        yield from _tl_entries(c)


_tl_told = []
_tl_real_status, _tl_real_read = app.set_status, NO.clipboard.read_text
app.set_status = lambda text, *a, **k: _tl_told.append(text)
_tl_kept = {}
try:
    app._edit_template(None, lambda: None)
    app.update()
    _tl_pop = app._mini_popup
    _tl_boxes = list(_tl_entries(_tl_pop)) if _tl_pop is not None else []
    for _tl_box, _tl_limit in zip(_tl_boxes[:3], (app.TITLE_MAX_LEN, app.TITLE_MAX_LEN,
                                                   NO.MAX_CHECKLIST_ITEM_CHARS)):
        _tl_box.delete(0, 'end')
        NO.clipboard.read_text = lambda n=_tl_limit + 1: 'q' * n
        _tl_box.event_generate('<<Paste>>')           # a paste past the limit
        _tl_whole = _tl_box.get()                     # shortened to fit
        _tl_box.delete(0, 'end')
        _tl_box.insert(0, 'q' * _tl_limit)            # one at the limit
        _tl_box.insert('end', 'q')                    # and a key past it
        _tl_kept[_tl_limit, len(_tl_kept)] = (len(_tl_whole), len(_tl_box.get()))
    app.update()
finally:
    app.set_status, NO.clipboard.read_text = _tl_real_status, _tl_real_read
    app._dismiss_mini_popup()
    app.update()
check(f'the template editor\'s name, title and checklist boxes shorten a paste '
      f'past their limits, refuse a key past them, and say so ({_tl_kept}; '
      f'{_tl_told[:4]})',
      len(_tl_kept) == 3
      and all(v == (k[0], k[0]) for k, v in _tl_kept.items())
      and {f'Pasted text shortened: {what} can be up to {n:,} characters'
           for what, n in (('a template name', app.TITLE_MAX_LEN),
                           ('a note title', app.TITLE_MAX_LEN),
                           ('a checklist item', NO.MAX_CHECKLIST_ITEM_CHARS))
           } <= set(_tl_told)
      and 'A checklist item can be up to 2,000 characters' in _tl_told)

# ...and a template's item already longer keeps every word, its row drawn cut,
# as a note's row is (qa1): a backup's 60,000 characters stood one label past
# what X can draw.
_tl_label = None
try:
    app._edit_template({'name': 'Long item', 'checklist': [
        {'text': 'w ' * 30000, 'done': False}]}, lambda: None)
    app.update()
    _tl_texts = []

    def _tl_labels(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                _tl_texts.append(c.cget('text'))
            _tl_labels(c)

    if app._mini_popup is not None:
        _tl_labels(app._mini_popup)
    _tl_label = max(_tl_texts, key=len, default='')
finally:
    app._dismiss_mini_popup()
    app.update()
check(f'the template editor draws a checklist item past the limit cut '
      f'({len(_tl_label or "")} characters drawn)',
      _tl_label is not None and _tl_label.endswith('…')
      and len(_tl_label) <= NO.MAX_CHECKLIST_ITEM_CHARS + 1)

# ---- A NAME KEPT WHOLE IS DRAWN ON ONE LINE, CUT ----
# Round 4 of the final audit: Save as template's name box took a pasted page,
# and the picker and Settings > Templates drew a name whole -- 300 letters made
# the picker wider than the screen, 5,000 passed X's limit and ended the app
# at every visit. Names stay whole in the file; boxes keep the limit, and
# rows and buttons draw one line, cut. Long enough to show it, short enough
# that drawing them whole under a mutant does not end the process.
_nm_long = 'Weekly meeting minutes ' * 13              # 299 characters
_nm_lines = 'line\n' * 40


def _tl_widgets(w, cls):
    for c in w.winfo_children():
        if isinstance(c, cls):
            yield c
        yield from _tl_widgets(c, cls)


app.notes = [NO.normalize_note({'id': 951, 'title': 'NmNote', 'body': 'b'})]
app.save_notes()
app.refresh_note_list()
app.open_note_in_tab(app.notes[0])
_kv_settle(6)
_nm_box = None
_nm_told = []
_nm_real_status, _nm_real_read = app.set_status, NO.clipboard.read_text
try:
    app.save_current_as_template()
    app.update()
    _nm_box = next(_tl_entries(app._mini_popup), None)
    if _nm_box is not None:
        _nm_box.delete(0, 'end')
        NO.clipboard.read_text = lambda: 'p' * 5000
        app.set_status = lambda text, *a, **k: _nm_told.append(text)
        _nm_box.event_generate('<<Paste>>')           # a page pasted: shortened
        _nm_box_len = len(_nm_box.get())
finally:
    app.set_status, NO.clipboard.read_text = _nm_real_status, _nm_real_read
    app._dismiss_mini_popup()
    app.update()
check(f"Save as template's name box shortens a paste to the note title's "
      f"{app.TITLE_MAX_LEN} ({_nm_box_len if _nm_box else None} kept; {_nm_told[:1]})",
      _nm_box is not None and _nm_box_len == app.TITLE_MAX_LEN
      and _nm_told[:1] == ['Pasted text shortened: a template name can be up '
                           f'to {app.TITLE_MAX_LEN} characters'])

# Round 6: opened from Settings, where the note's page and its status line
# stand hidden, the template editor cut a paste without a word on screen; it
# says so on a line of its own. And a paste is weighed with each line break
# one character, as Tk's own paste puts it in: Windows' clipboard keeps CR LF,
# so ten lines that fitted were cut and kept their CRs. The clipboard reads
# here as the app reads Windows' (CR LF), Tk's own as Tk translates it.
_lw_seen = {}
_lw_real_read = NO.clipboard.read_text


def _lw_paste(box, lines):
    NO.clipboard.read_text = lambda: '\r\n'.join(lines)
    app.clipboard_clear()
    app.clipboard_append('\n'.join(lines))
    box.delete(0, 'end')
    box.event_generate('<<Paste>>')
    _kv_settle(2)
    return box.get()


try:
    app.show_settings_page()
    app.toggle_settings_panel('templates')
    _kv_settle(6)
    app._edit_template(None, lambda: None)
    _kv_settle(6)
    _lw_pop = app._mini_popup
    _lw_boxes = list(_tl_entries(_lw_pop))
    _lw_seen['status line in sight'] = bool(app.status_lbl.winfo_viewable())
    _lw_paste(_lw_boxes[0], ['Weekly review ' * 25])
    _lw_seen['said in the editor'] = [
        str(w.cget('text')) for w in _tl_widgets(_lw_pop, tk.Label)
        if app._is_placed(w) and 'can be up to' in str(w.cget('text'))]
    _lw_ten = _lw_paste(_lw_boxes[2], ['w' * 199] * 10)          # 1,999 in all
    _lw_seen['ten lines that fit'] = (len(_lw_ten), _lw_ten.count('\r'))
    _lw_eleven = _lw_paste(_lw_boxes[2], ['w' * 199] * 11)       # 2,199
    _lw_seen['eleven lines, shortened'] = (len(_lw_eleven), _lw_eleven.count('\r'),
                                           _lw_eleven.count('\n'))
finally:
    NO.clipboard.read_text = _lw_real_read
    app._dismiss_mini_popup()
    app.hide_settings_page()
    app.notebook.select(app.TAB_NOTES)
    _kv_settle(4)
check(f"the template editor, opened from Settings, says in itself that a paste "
      f"was shortened, and weighs a line break as one character ({_lw_seen})",
      _lw_seen.get('status line in sight') is False
      and _lw_seen.get('said in the editor') == [
          'Pasted text shortened: a template name can be up to '
          f'{app.TITLE_MAX_LEN} characters']
      and _lw_seen.get('ten lines that fit') == (1999, 0)
      and _lw_seen.get('eleven lines, shortened') == (NO.MAX_CHECKLIST_ITEM_CHARS, 0, 10))

# Round 7: on the note's page the status line stands at the foot of the
# scrolled editor -- mapped, and far below the view at the window's own
# sizes -- and a paste cut to fit the checklist's Add box or the title was
# said there, where nobody saw it. Out of sight, it is said in a banner over
# the window; in sight, on the line alone.
_ns_seen = {}
_ns_geo = app.geometry()
_ns_real_read = NO.clipboard.read_text
# The banners the paste raised, as asked for: an autosave's "Note created"
# can stand on the banner a moment later, and is no answer about the paste.
_ns_banners = []
app._show_toast = lambda text, *a, **k: (
    _ns_banners.append((text, k.get('kind'))),
    NO.NoteOrganizer._show_toast(app, text, *a, **k))[1]


def _ns_paste(box, text, read_text=True):
    if read_text:
        NO.clipboard.read_text = lambda: text
    app.clipboard_clear()
    app.clipboard_append(text)
    box.delete(0, 'end')
    del _ns_banners[:]
    box.event_generate('<<Paste>>')
    _kv_settle(3)
    kept = len(box.get())
    if box is app.title_entry:
        box.delete(0, 'end')            # no note is made of it meanwhile
    return kept, [t for t, kind in _ns_banners if kind == 'info']


try:
    app.geometry('900x600'); _kv_settle(6)
    app.notebook.select(app.TAB_NOTES)
    app.new_note(); _kv_settle(4)
    if not app._checklist_open:
        app.toggle_checklist_section()
    _kv_settle(6)
    app.editor_canvas.yview_moveto(0); _kv_settle(4)
    _ns_seen['status line in sight'] = app._in_sight(app.status_lbl)
    _ns_seen['Add box'] = _ns_paste(app.checklist_add_entry, 'x' * 2500)
    _ns_seen['title'] = _ns_paste(app.title_entry, 'T' * 300, read_text=False)
    app.editor_canvas.yview_moveto(1.0); _kv_settle(4)
    _ns_seen['status line in sight, scrolled down'] = app._in_sight(app.status_lbl)
    _ns_seen['Add box, the line in sight'] = _ns_paste(app.checklist_add_entry, 'x' * 2500)
finally:
    del app._show_toast
    NO.clipboard.read_text = _ns_real_read
    app.checklist_add_entry.delete(0, 'end')
    app.title_entry.delete(0, 'end')
    app._hide_toast()
    app.geometry(_ns_geo); _kv_settle(6)
check(f"the note's page says a paste cut to fit where it is seen: in a banner "
      f"while its status line is scrolled away, on the line alone in sight ({_ns_seen})",
      _ns_seen.get('status line in sight') is False
      and _ns_seen.get('Add box') == (
          2000, ['Pasted text shortened: a checklist item can be up to 2,000 characters'])
      and _ns_seen.get('title') == (200, ['Pasted title shortened to 200 characters'])
      and _ns_seen.get('status line in sight, scrolled down') is True
      and _ns_seen.get('Add box, the line in sight') == (2000, []))

# Round 8: while an Undo was on offer the banner stayed quiet "because the
# words stay on the line" -- the line out of sight -- so a paste cut to fit
# was said nowhere seen for the offer's eight seconds. The words stand on a
# banner of their own beneath it, the offer untouched.
_wb_seen = {}
_wb_geo = app.geometry()
_wb_real_read = NO.clipboard.read_text
_wb_undone = []


def _wb_state():
    words = getattr(app, '_words_frame', None)
    shown = words is not None and words.winfo_manager() == 'place'
    app.update_idletasks()
    return {'offer': (str(app.toast_lbl.cget('text')), app._toast_action is not None,
                      app.toast_action_lbl.winfo_manager() == 'pack'),
            'words': str(app._words_lbl.cget('text')) if shown else None,
            'beneath': (shown and words.winfo_y()
                        >= app.toast_frame.winfo_y() + app.toast_frame.winfo_height())}


try:
    app.geometry('900x600'); _kv_settle(6)
    app.notebook.select(app.TAB_NOTES)
    app.new_note(); _kv_settle(4)
    if not app._checklist_open:
        app.toggle_checklist_section()
    _kv_settle(6)
    app.editor_canvas.yview_moveto(0); _kv_settle(4)
    _wb_seen['status line in sight'] = app._in_sight(app.status_lbl)
    app._show_toast('Removed “milk”', action=lambda: _wb_undone.append(1))
    _wb_seen['an Undo on offer'] = app._offer_on_banner()
    NO.clipboard.read_text = lambda: 'x' * 2500
    app.checklist_add_entry.delete(0, 'end')
    app.checklist_add_entry.event_generate('<<Paste>>')
    _kv_settle(3)
    _wb_seen['Add box'] = (len(app.checklist_add_entry.get()), _wb_state())
    app.clipboard_clear()
    app.clipboard_append('T' * 300)
    app.title_entry.delete(0, 'end')
    app.title_entry.event_generate('<<Paste>>')
    _kv_settle(3)
    _wb_seen['title'] = (len(app.title_entry.get()), _wb_state())
    app.title_entry.delete(0, 'end')     # no note is made of it meanwhile
    app._run_toast_action()
    _wb_seen['the Undo still taken'] = _wb_undone == [1]
    # The offer gone, its words still beneath: the autosave's reassurance
    # waits for them as it waits for words on the banner.
    app._show_toast('Note updated', yield_to_action=True)
    _wb_seen['Note updated after the Undo'] = app.toast_frame.winfo_manager() == 'place'
    # ...and the next words go on the banner, the older ones beneath gone.
    app.checklist_add_entry.delete(0, 'end')
    app.checklist_add_entry.event_generate('<<Paste>>')
    _kv_settle(3)
    _wb_seen['no offer'] = _wb_state()
finally:
    NO.clipboard.read_text = _wb_real_read
    app.checklist_add_entry.delete(0, 'end')
    app._hide_toast()
    app._hide_words_beneath()
    app.geometry(_wb_geo); _kv_settle(6)
_wb_offer = ('✓  Removed “milk”', True, True)
check(f"a paste cut to fit while an Undo is on offer is said on a banner beneath it, "
      f"the offer untouched ({_wb_seen})",
      _wb_seen.get('status line in sight') is False
      and _wb_seen.get('an Undo on offer') is True
      and _wb_seen.get('Add box') == (2000, {
          'offer': _wb_offer, 'beneath': True,
          'words': 'i  Pasted text shortened: a checklist item can be up to 2,000 characters'})
      and _wb_seen.get('title') == (200, {
          'offer': _wb_offer, 'beneath': True,
          'words': 'i  Pasted title shortened to 200 characters'})
      and _wb_seen.get('the Undo still taken') is True
      and _wb_seen.get('Note updated after the Undo') is False
      and _wb_seen.get('no offer') == {
          'offer': ('i  Pasted text shortened: a checklist item can be up to 2,000 '
                    'characters', False, False),
          'beneath': False, 'words': None})

# ...and the autosave the title's paste sets off, half a second later, wrote
# "Note updated" over that banner and "Auto-saved" over the line (round 8):
# reassurance yields to the words, on the banner and on the line in sight.
_wa_seen = {}
_wa_geo = app.geometry()
_wa_kept_notes = list(app.notes)
_wa_paste = ' and ' + 'more words ' * 30


def _wa_run(in_sight):
    app.new_note(); _kv_settle(2)        # the last run's note left, as it stands
    note = NO.normalize_note({'id': 4801, 'title': 'Groceries', 'body': 'b'})
    app.notes = [note]; app.save_notes()
    app.open_note_in_tab(note); _kv_settle(4)
    app.editor_canvas.yview_moveto(1.0 if in_sight else 0); _kv_settle(4)
    app._hide_toast()
    app._hide_words_beneath()
    app._box_words_until = 0
    seen = {'status line in sight': app._in_sight(app.status_lbl)}
    app.title_entry.icursor('end')
    app.clipboard_clear()
    app.clipboard_append(_wa_paste)
    app.title_entry.event_generate('<<Paste>>')
    app._autosave_now()                 # what Ctrl+V's release sets off
    with open(NO.DATA_FILE, encoding='utf-8') as fh:
        stored = next((n for n in _json6a.load(fh) if n.get('id') == 4801), {})
    seen['saved'] = len(stored.get('title') or '')
    seen['banner'] = (str(app.toast_lbl.cget('text'))
                      if app.toast_frame.winfo_manager() == 'place' else None)
    seen['line'] = str(app.status_lbl.cget('text'))
    return seen


try:
    app.geometry('900x600'); _kv_settle(6)
    app.notebook.select(app.TAB_NOTES)
    _wa_seen['out of sight'] = _wa_run(False)
    _wa_seen['in sight'] = _wa_run(True)
finally:
    app._hide_toast()
    app.new_note(); _kv_settle(2)
    app.notes = _wa_kept_notes; app.save_notes()
    app.refresh_note_list()
    app.geometry(_wa_geo); _kv_settle(6)
_wa_words = 'Pasted title shortened to 200 characters'
check(f"the autosave a title's paste sets off writes over neither the banner nor the "
      f"line that say it was shortened ({_wa_seen})",
      _wa_seen.get('out of sight') == {'status line in sight': False, 'saved': 200,
                                       'banner': 'i  ' + _wa_words, 'line': _wa_words}
      and _wa_seen.get('in sight', {}).get('status line in sight') is True
      and _wa_seen['in sight'].get('saved') == 200
      and _wa_seen['in sight'].get('line') == _wa_words)

# ...and a title is weighed as it goes in, on one line: a line copied with its
# line break, or Windows' CR LF, was "shortened" by the space it lost.
_tw_told, _tw_kept = [], {}
_tw_real_status = app.set_status
try:
    app.new_note(); _kv_settle(4)
    app.set_status = lambda text, *a, **k: _tw_told.append(text)
    # (what the title held, where the caret was, what was pasted)
    for _tw_was, _tw_at, _tw_paste in (
            ('', 0, 'Shopping list\n'), ('', 0, 'Shopping list\r\n'),
            ('', 0, 'Shopping  list'),
            # ...and a paste's own spaces at its edges stay: str.split() took
            # them, and two words ran together (round 8).
            ('Buy milk', 4, 'fresh '), ('Buy milk', 3, ' fresh'),
            ('Groceries', 9, ' and more\r\n')):
        app.title_entry.delete(0, 'end')
        app.title_entry.insert(0, _tw_was)
        app.title_entry.icursor(_tw_at)
        app.clipboard_clear()
        app.clipboard_append(_tw_paste)
        app.title_entry.event_generate('<<Paste>>')
        _kv_settle(2)
        _tw_kept[_tw_paste] = app.title_entry.get()
finally:
    app.set_status = _tw_real_status
    app.title_entry.delete(0, 'end')
check(f"a title pasted with its line break, or a double space, is not said to be "
      f"shortened, and a paste keeps the spaces at its edges ({_tw_kept}; said {_tw_told})",
      _tw_kept == {'Shopping list\n': 'Shopping list', 'Shopping list\r\n': 'Shopping list',
                   'Shopping  list': 'Shopping  list', 'fresh ': 'Buy fresh milk',
                   ' fresh': 'Buy fresh milk', ' and more\r\n': 'Groceries and more'}
      and not [t for t in _tw_told if 'shortened' in t])

# ...and the join takes time in proportion to the paste: "\s*" around a break
# tried every place in a run of spaces, and 40,000 with no break in them froze
# the window 5 s (round 9). Timed in this run against the same run ending in
# a break, the quickest of three each; the sizes are fixed, never read from
# the app.
_tl_took = {'run': [], 'run ending in a break': []}
_tl_kept, _tl_told = {}, []
_tl_real_status = app.set_status
try:
    app.new_note(); _kv_settle(4)
    app.set_status = lambda text, *a, **k: _tl_told.append(text)
    for _tl_i in range(3):
        for _tl_name, _tl_paste in (('run', 'Plan' + ' ' * 30000 + 'end'),
                                    ('run ending in a break', 'Plan' + ' ' * 30000 + '\nend')):
            app.title_entry.delete(0, 'end')
            app.clipboard_clear()
            app.clipboard_append(_tl_paste)
            _tl_t0 = time.perf_counter()
            app.title_entry.event_generate('<<Paste>>')
            _tl_took[_tl_name].append(time.perf_counter() - _tl_t0)
            _tl_kept[_tl_name] = app.title_entry.get()
            _kv_settle(1)
finally:
    app.set_status = _tl_real_status
    app.title_entry.delete(0, 'end')
    app._hide_toast()
_tl_run, _tl_break = min(_tl_took['run']), min(_tl_took['run ending in a break'])
check(f"a title paste of 30,000 spaces with no break in them takes what the same run "
      f"ending in a break takes ({_tl_run * 1000:.1f} ms against {_tl_break * 1000:.1f} ms)",
      _tl_kept == {'run': 'Plan' + ' ' * 196, 'run ending in a break': 'Plan end'}
      and _tl_run < 4 * _tl_break + 0.3)

# ...reads no more of the clipboard than any paste reads (_cap_paste); and at
# the cap, a paste whose only overflow is its own trailing space is not
# called shortened (round 9). Words left out still are.
_tc_kept, _tc_told = {}, {}
_tc_real_status = app.set_status
try:
    app.new_note(); _kv_settle(4)
    for _tc_name, _tc_was, _tc_paste in (
            ('past the ceiling', '', 'Plan' + '\n' * 100_000 + 'tail'),
            ('trailing space', 'x' * 195, 'fresh '),
            ('words left out', 'x' * 195, 'fresh milk')):
        _tc_told[_tc_name] = []
        app.set_status = lambda text, *a, _n=_tc_name, **k: _tc_told[_n].append(text)
        app.title_entry.delete(0, 'end')
        app.title_entry.insert(0, _tc_was)
        app.title_entry.icursor('end')
        app.clipboard_clear()
        app.clipboard_append(_tc_paste)
        app.title_entry.event_generate('<<Paste>>')
        _kv_settle(1)
        _tc_kept[_tc_name] = app.title_entry.get()
finally:
    app.set_status = _tc_real_status
    app.title_entry.delete(0, 'end')
    app._hide_toast()
_tc_short = {name: any('shortened' in t for t in told) for name, told in _tc_told.items()}
check(f"a title paste reads no further than the ceiling every paste keeps, and says "
      f"it was cut ({_tc_kept.get('past the ceiling')!r}, "
      f"said {_tc_told.get('past the ceiling')})",
      _tc_kept.get('past the ceiling') == 'Plan' and _tc_short.get('past the ceiling'))
check(f"at the title's cap, a paste that loses only its own trailing space is not "
      f"called shortened, and one that loses words is ({_tc_short})",
      _tc_kept.get('trailing space') == 'x' * 195 + 'fresh'
      and _tc_kept.get('words left out') == 'x' * 195 + 'fresh'
      and _tc_short == {'past the ceiling': True, 'trailing space': False,
                        'words left out': True})

# A title already past the cap -- a share code's, a backup's -- shortens: every
# Backspace and Delete was refused as too long, and a paste over a selection
# deleted it and then found no room, so the selected words went (round 10).
_ol_seen, _ol_told = {}, []
_ol_real_status = app.set_status
app._autosave_now = lambda: None            # no note is made of it meanwhile
try:
    app.new_note(); _kv_settle(4)
    app.set_status = lambda text, *a, **k: _ol_told.append(text)
    app.title_entry.delete(0, 'end')
    app._insert_title('L' * 250)
    app.title_entry.delete(249)                       # what Backspace asks
    _ol_seen['a letter taken off the end'] = len(app.title_entry.get())
    app.title_entry.selection_range(239, 249)
    app.title_entry.delete('sel.first', 'sel.last')   # Delete over a selection
    _ol_seen['ten selected, deleted'] = len(app.title_entry.get())
    app.title_entry.insert('end', 'z')                # still past the cap: refused
    _ol_seen['a key, still past the cap'] = len(app.title_entry.get())
    app.title_entry.selection_range(200, 239)
    app.title_entry.icursor(239)
    app.clipboard_clear()
    app.clipboard_append('abc')
    _qa_fire(app.title_entry, '<<Paste>>')            # still past the cap without them
    _kv_settle(2)
    _ol_seen['a paste over too few'] = (len(app.title_entry.get()),
                                        app.title_entry.selection_present())
    app.title_entry.selection_range(190, 239)
    app.title_entry.icursor(239)
    _qa_fire(app.title_entry, '<<Paste>>')            # room for ten once they go
    _kv_settle(2)
    _ol_seen['a paste over enough'] = app.title_entry.get()[185:]
finally:
    app.set_status = _ol_real_status
    del app._autosave_now
    app._cancel_pending_autosave()
    app.title_entry.delete(0, 'end')
    app._hide_toast()
check(f"a title past the cap shortens by Backspace and Delete, and a paste over a "
      f"selection with no room for it keeps the selection ({_ol_seen}; said {_ol_told})",
      _ol_seen == {'a letter taken off the end': 249, 'ten selected, deleted': 239,
                   'a key, still past the cap': 239, 'a paste over too few': (239, True),
                   'a paste over enough': 'LLLLLabc'}
      and 'A note title can be up to 200 characters' in _ol_told)

# ...and a middle-click is a paste too -- Tk binds it on Windows as well -- and
# it went past every rule a paste keeps: the selection's line breaks into the
# title, a checklist item past its limit refused whole, a hint left in front
# of the words (round 10).
_mc_seen, _mc_told = {}, []
_mc_real_status = app.set_status
_mc_source = tk.Text(app)


def _mc_paste(box, primary, x=None):
    _mc_source.delete('1.0', 'end')
    _mc_source.insert('1.0', primary)
    _mc_source.tag_add('sel', '1.0', 'end-1c')
    app.tk.eval('set ::tk::Priv(mouseMoved) 0')
    _qa_fire(box, '<<PasteSelection>>', x=box.winfo_width() - 4 if x is None else x, y=4)
    _kv_settle(2)
    return box.get()


app._autosave_now = lambda: None
try:
    app.new_note(); _kv_settle(4)
    if not app._checklist_open:
        app.toggle_checklist_section()
    _kv_settle(4)
    app.set_status = lambda text, *a, **k: _mc_told.append(text)
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'Shopping ')
    _mc_seen['title, three lines'] = _mc_paste(app.title_entry, 'milk\neggs\nbread')
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'x' * 195)
    _mc_got = _mc_paste(app.title_entry, 'fresh milk')     # where the pointer is
    _mc_seen['title, at its cap'] = (len(_mc_got), _mc_got.replace('x', ''))
    app.title_entry.delete(0, 'end')
    app.tk.eval('set ::tk::Priv(mouseMoved) 1')
    _qa_fire(app.title_entry, '<<PasteSelection>>', x=4, y=4)
    _kv_settle(2)
    _mc_seen['title, a drag that scrolled'] = app.title_entry.get()
    app.tk.eval('set ::tk::Priv(mouseMoved) 0')
    app.checklist_add_entry.delete(0, 'end')
    _mc_seen['Add box, past its limit'] = len(_mc_paste(app.checklist_add_entry, 'x' * 2500))
    app.checklist_add_entry.delete(0, 'end')
    _mc_seen['Add box, a few words'] = _mc_paste(app.checklist_add_entry, 'eggs')
    app.checklist_add_entry.delete(0, 'end')
    for _mc_hint in ('Note title...', 'Search notes...'):
        _mc_box = next(e for e, h in app._placeholders if h == _mc_hint)
        app.focus_set()
        _mc_box.delete(0, 'end')
        _mc_box.insert(0, _mc_hint)
        _mc_seen[_mc_hint] = _mc_paste(_mc_box, 'Pasted', x=4)
        _mc_box.delete(0, 'end')
finally:
    app.set_status = _mc_real_status
    del app._autosave_now
    app._cancel_pending_autosave()
    _mc_source.destroy()
    app.title_entry.delete(0, 'end')
    app.checklist_add_entry.delete(0, 'end')
    app._clear_search()
    app._hide_toast()
    _kv_settle(2)
check(f"a middle-click into the title or the checklist's Add box keeps the rules a "
      f"paste keeps, and lands in a hint's place ({_mc_seen}; said {_mc_told})",
      _mc_seen == {'title, three lines': 'Shopping milk eggs bread',
                   'title, at its cap': (200, 'fresh'), 'title, a drag that scrolled': '',
                   'Add box, past its limit': 2000, 'Add box, a few words': 'eggs',
                   'Note title...': 'Pasted', 'Search notes...': 'Pasted'}
      and 'Pasted title shortened to 200 characters' in _mc_told
      and 'Pasted text shortened: a checklist item can be up to 2,000 characters'
      in _mc_told)

# ...and a limited box's paste over a selection keeps it when nothing fits: a
# value past its limit, from a backup's template, lost the selection (round 10).
_lb_box = tk.Entry(app)
_lb_box.insert(0, 'v' * 15)
app._limit_entry(_lb_box, 10, 'A test value')
_lb_told = []
_lb_real_status = app.set_status
try:
    app.set_status = lambda text, *a, **k: _lb_told.append(text)
    _lb_box.selection_range(12, 15)
    _lb_box.icursor(15)
    app.clipboard_clear()
    app.clipboard_append('abc')
    _qa_fire(_lb_box, '<<Paste>>')
    _kv_settle(2)
    _lb_kept = (len(_lb_box.get()), _lb_box.selection_present())
finally:
    app.set_status = _lb_real_status
    _lb_box.destroy()
    app._hide_toast()
check(f"a limited box's paste over a selection that leaves no room keeps the "
      f"selection, and says why ({_lb_kept}; said {_lb_told})",
      _lb_kept == (15, True) and 'A test value can be up to 10 characters' in _lb_told)

# ...and says "shortened" only when words were left out, as the title does: a
# paste whose only overflow was its own trailing space was said to be cut.
_ls_seen = {}
_ls_real_status = app.set_status
try:
    for _ls_paste in ('ab ', 'abc'):
        _ls_box = tk.Entry(app)
        _ls_box.insert(0, 'v' * 8)
        app._limit_entry(_ls_box, 10, 'A test value')
        _ls_told = []
        app.set_status = lambda text, *a, **k: _ls_told.append(text)
        _ls_box.icursor('end')
        app.clipboard_clear()
        app.clipboard_append(_ls_paste)
        _qa_fire(_ls_box, '<<Paste>>')
        _kv_settle(2)
        _ls_seen[_ls_paste] = (_ls_box.get(), _ls_told)
        _ls_box.destroy()
finally:
    app.set_status = _ls_real_status
    app._hide_toast()
check(f"a limited box says a paste was shortened only when words were left out, not "
      f"its own trailing space ({_ls_seen})",
      _ls_seen.get('ab ') == ('v' * 8 + 'ab', [])
      and _ls_seen.get('abc', ('', []))[0] == 'v' * 8 + 'ab'
      and 'Pasted text shortened: a test value can be up to 10 characters'
      in _ls_seen.get('abc', ('', []))[1])

# ...and an edit no key made in the title, the comments or the date -- the menu's
# Cut -- is saved, and the title's count follows it: only a key's release set
# either off, and a right-click Cut was saved when the note was left (round 10).
_nk_seen = {}
app._autosave_now = lambda: None
try:
    app.new_note(); _kv_settle(4)
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'x' * 180)
    app._refresh_title_count()
    _kv_settle(1)
    for _nk_name, _nk_box, _nk_select in (
            ('title', app.title_entry, lambda b: b.selection_range(0, 30)),
            ('comments', app.comments_text, lambda b: (
                b.insert('1.0', 'some words'), b.tag_add('sel', '1.0', '1.4'))),
            ('date', app.date_entry, lambda b: (
                b.delete(0, 'end'), b.insert(0, '17.10.2026'), b.selection_range(0, 3)))):
        _nk_select(_nk_box)
        app._cancel_pending_autosave()
        _qa_fire(_nk_box, '<<Cut>>')
        app.update_idletasks()
        _nk_seen[_nk_name] = getattr(app, '_autosave_job', None) is not None
    _nk_seen['title count'] = (len(app.title_entry.get()),
                               bool(app.title_count_lbl.winfo_manager()))
finally:
    del app._autosave_now
    app._cancel_pending_autosave()
    app.title_entry.delete(0, 'end')
    app.comments_text.delete('1.0', 'end')
    app.date_entry.delete(0, 'end')
    app.new_note(); _kv_settle(2)
check(f"a right-click Cut in the title, the comments or the date sets off the autosave, "
      f"and the title's count follows it ({_nk_seen})",
      _nk_seen == {'title': True, 'comments': True, 'date': True,
                   'title count': (150, False)})

# ...and the ceiling every paste keeps weighs a line break as one character,
# as the note keeps it: Windows' clipboard holds CR LF, and 1,500 lines of 65
# letters -- 98,999 characters in the note -- weighed 100,498, and the body
# and the comments lost their ends with "Only the first 100,000 characters".
_cr_seen, _cr_told = {}, []
_cr_real = (NO.clipboard.read_text, NO.clipboard.read_html, app.show_info)
_cr_lines = ['%04d ' % i + 'w' * 60 for i in range(1500)]
try:
    app.new_note(); _kv_settle(4)
    # As the app reads Windows' clipboard (CR LF), and Tk's own as Tk
    # translates it: a paste that fits is Tk's to make.
    NO.clipboard.read_text = lambda: '\r\n'.join(_cr_lines)
    NO.clipboard.read_html = lambda: None
    app.clipboard_clear()
    app.clipboard_append('\n'.join(_cr_lines))
    app.show_info = lambda title, *a, **k: _cr_told.append(title)
    for _cr_name, _cr_box in (('body', app.body_text), ('comments', app.comments_text)):
        _cr_box.delete('1.0', 'end')
        _take_focus(_cr_box)
        _cr_box.event_generate('<<Paste>>')
        _kv_settle(3)
        _cr_kept = _cr_box.get('1.0', 'end-1c')
        _cr_seen[_cr_name] = (len(_cr_kept), _cr_kept.count('\r'),
                              _cr_kept.endswith(_cr_lines[-1]))
        _cr_box.delete('1.0', 'end')
finally:
    NO.clipboard.read_text, NO.clipboard.read_html, app.show_info = _cr_real
    _kv_settle(2)
check(f"a paste of 1,500 lines kept in CR LF fits the ceiling as the note keeps "
      f"it, whole, with nothing said ({_cr_seen}; said {_cr_told})",
      _cr_seen == {'body': (98_999, 0, True), 'comments': (98_999, 0, True)}
      and _cr_told == [])
_nm_kept = list(app.templates)
app.templates = [{'name': _nm_long, 'body': 'x'}, {'name': _nm_lines, 'body': 'y'}]
_nm_picker = _nm_buttons = None
try:
    app.show_template_picker()
    app.update()
    _nm_pop = app._mini_popup
    _nm_picker = _nm_pop.winfo_reqwidth()
    _nm_buttons = [str(b.cget('text')) for b in _tl_widgets(_nm_pop, tk.Button)
                   if '🧩' in str(b.cget('text'))]
finally:
    app._dismiss_mini_popup()
    app.update()
check(f"the template picker draws a long name cut, on one line, and stays "
      f"narrower than the window ({_nm_picker} px; "
      f"{[len(t) for t in _nm_buttons or []]} characters)",
      _nm_picker is not None and _nm_picker < app.winfo_width()
      and len(_nm_buttons) == 2
      and all('\n' not in t and t.endswith('…') for t in _nm_buttons))
app.show_settings_page()
app.toggle_settings_panel('templates')
_kv_settle(10)
_nm_rows = [c for c in _tl_widgets(app.settings_page, tk.Label)
            if str(c.cget('text')).startswith(('Weekly', 'line'))]
_nm_line_h = app._cal_font(('Segoe UI', 10, 'bold'))[1]
check(f"...and so does Settings > Templates "
      f"({[(len(str(r.cget('text'))), r.winfo_reqheight()) for r in _nm_rows]}), "
      f"each name still whole in the file",
      len(_nm_rows) == 2
      and all('\n' not in str(r.cget('text'))
              and r.winfo_reqheight() < 3 * _nm_line_h for r in _nm_rows)
      and [t['name'] for t in app.templates] == [_nm_long, _nm_lines])
app.hide_settings_page()
app.templates = _nm_kept
_kv_settle(4)
# A question is as tall as its message, and quoted a title kept whole: one of
# 300,000 letters or 3,000 lines passed X's limit. It shows the start and the
# end, the question kept. The probe's own message passes the limits without
# passing X's, so a mutant drawing it whole fails here instead of ending.
from noteorganizer.ui.dialogs import (message_shown as _nm_message_shown,
                                      MESSAGE_SHOWN_CHARS as _nm_chars)
_nm_msg = 'Delete “' + 'word ' * 4000 + '”?\n' + 'more\n' * 400 + 'Really delete it?'
_nm_seen = {}


def _nm_read_and_answer():
    _nm_stack = getattr(app, '_asking_dialogs', None) or []
    if _nm_stack:
        _nm_labels = list(_tl_widgets(_nm_stack[-1]['border'], tk.Label))
        _nm_seen['text'] = max((str(l.cget('text')) for l in _nm_labels), key=len)
        _nm_stack[-1]['buttons'][0].invoke()


app.after(300, _nm_read_and_answer)
# The class's own question, and its own wait: earlier checks left stubs of
# both on the app.
_nm_wait = app.__dict__.pop('wait_variable', None)
try:
    NO.NoteOrganizer._themed_dialog(app, 'A long one', _nm_msg,
                                    buttons=[('No', False), ('Yes', True)])
finally:
    if _nm_wait is not None:
        app.wait_variable = _nm_wait
_kv_settle(4)
_nm_text = _nm_seen.get('text', '')
check(f"a question's message past the limits shows its start and its end, the "
      f"question kept ({len(_nm_text)} of {len(_nm_msg)} characters, "
      f"{_nm_text.count(chr(10)) + 1} lines)",
      len(_nm_text) <= _nm_chars + 3 and _nm_text.count('\n') <= 301
      and _nm_text.startswith('Delete “word') and _nm_text.endswith('Really delete it?')
      and len(_nm_message_shown('w' * 300000)) <= _nm_chars + 3)
app.set_status('Saved “' + 'line\n' * 300 + '”')
check(f"the status line quotes a name of many lines on one line "
      f"({app.status_lbl.cget('text')[:30]!r}...)",
      '\n' not in str(app.status_lbl.cget('text')))
app.set_status('')

# ---- A ROW'S BUTTONS KEEP THEIR ROOM ----
# Round 4: Tk's packer serves widgets in the order they were packed, and a
# name packed before its row's buttons took the room they needed: in
# Settings > Templates a 50-letter name pushed the pencil out, 80 the bin
# too, and the same in Categories (80 letters allowed) and the statistics.
def _rb_inside(w, row):
    return (w is not None and w.winfo_ismapped() and w.winfo_width() > 5
            and w.winfo_x() + w.winfo_width() <= row.winfo_width())


# As long as a category may be, in wide letters: an ordinary 64 left the row
# room enough on Windows' narrower font, and the check passed with the fix out.
_rb_cat = ('Quarterly ' + 'W' * 80)[:80]
_rb_kept_tpl = list(app.templates)
app.templates = [{'name': 'Onboarding checklist for new staff in the north office, '
                          'with every form they need on day one', 'body': 'x'}]
NO.CATEGORY_COLORS[_rb_cat] = '#5b8def'
app.notes = [NO.normalize_note({'id': 961, 'title': 'RbNote', 'body': 'b',
                                'category': _rb_cat})]
app.save_notes()
_rb_seen, _rb_where, _rb_room = {}, None, None
# The name drawn whole must want more than its row, or the check proves nothing.
_rb_need = app._cal_font(('Segoe UI', 10, 'bold'))[0].measure(_rb_cat)
try:
    app.show_settings_page()
    # The names drawn as they fit: their first letters always show.
    for _rb_section, _rb_word in (('templates', 'Onbo'), ('categories', 'Quar')):
        app.toggle_settings_panel(_rb_section)
        _kv_settle(10)
        _rb_panel = getattr(app, 'settings_%s_panel' % _rb_section)
        for _rb_icon in _tl_widgets(_rb_panel, tk.Widget):
            _rb_kind = getattr(_rb_icon, '_icon_kind', None)
            _rb_row = _rb_icon.master
            _rb_name = ' '.join(str(c.cget('text')) for c in _rb_row.winfo_children()
                                if isinstance(c, tk.Label))
            if _rb_kind in ('pencil', 'trash') and _rb_word in _rb_name:
                _rb_seen[_rb_section, _rb_kind] = _rb_inside(_rb_icon, _rb_row)
                if _rb_section == 'categories':
                    _rb_room = _rb_row.winfo_width()
    app.toggle_settings_panel('statistics')
    _kv_settle(10)
    _rb_pill = next((l.master for l in _tl_widgets(app.settings_statistics_panel, tk.Label)
                     if str(l.cget('text')).startswith('Quar')), None)
    _rb_count = next((l for l in (_rb_pill.winfo_children() if _rb_pill else ())
                      if isinstance(l, tk.Label) and str(l.cget('text')).isdigit()), None)
    _rb_seen['statistics', 'count'] = _rb_inside(_rb_count, _rb_pill)
    _rb_where = ((_rb_count.winfo_ismapped(), _rb_count.winfo_x(), _rb_count.winfo_width(),
                  _rb_pill.winfo_width()) if _rb_count is not None else
                 [str(l.cget('text'))[:14] for l in _tl_widgets(
                     app.settings_statistics_panel, tk.Label)][:60])
finally:
    app.hide_settings_page()
    app.templates = _rb_kept_tpl
    NO.CATEGORY_COLORS.pop(_rb_cat, None)
    app.notes = []
    app.save_notes()
    _kv_settle(4)
check(f"a long name leaves its row's buttons in the row: the template's pencil "
      f"and bin, the category's, and the statistics' count ({_rb_seen}; {_rb_where}; "
      f"the category's name {_rb_need}px for a {_rb_room}px row)",
      len(_rb_seen) == 5 and all(_rb_seen.values())
      and _rb_room is not None and _rb_need > _rb_room)

# ---- KEYBOARD: a part put away by a click hands the keyboard on ----
# Round 4: a click takes no keyboard, so folding the checklist with the caret
# in its Add box left it there: x and Return added an item nobody saw, and it
# was saved. The same for the calculator, a Settings section left, the import
# panel closed. One watcher hands the keyboard on from any part put away.
def _pa_holder():
    try:
        return app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
    except (KeyError, tk.TclError):
        return None


def _pa_click(button):
    """A click on a Tk button: the press the app counts, then its command."""
    _qa_fire(button, '<ButtonPress-1>')
    button.invoke()
    _kv_settle(6)


_pa_seen = {}
app.notes = [NO.normalize_note({'id': 971, 'title': 'PaNote', 'body': 'milk',
                                'checklist': [{'text': 'eggs', 'done': False}]})]
app.save_notes()
app.refresh_note_list()
app.notebook.select(app.TAB_NOTES)
app.open_note_in_tab(app.notes[0])
_kv_settle(6)
if not app._checklist_open:
    app.toggle_checklist_section()
_kv_settle(4)
_pa_took = _take_focus(app.checklist_add_entry)
_pa_click(app.checklist_btn)                       # the bar folds the list
_pa_h = _pa_holder()
_pa_seen['checklist'] = (_pa_took, _pa_h is not None and bool(_pa_h.winfo_viewable()))
for _pa_key in ('<KeyPress-x>', '<KeyPress-Return>'):
    app.event_generate(_pa_key)                    # Tk sends it where the keyboard is
    _kv_settle(2)
app._flush_autosave()
_pa_items = [i['text'] for i in (app.find_note(971) or {}).get('checklist', [])]
if not app._calculator_open:
    app.toggle_calculator_section()
_kv_settle(4)
_pa_took = _take_focus(app.calculator_display)
_pa_click(app.calculator_btn)                      # the calculator folds
_pa_h = _pa_holder()
_pa_seen['calculator'] = (_pa_took, _pa_h is not None and bool(_pa_h.winfo_viewable()))
app.toggle_import_panel()
_kv_settle(4)
_pa_took = _take_focus(app.import_box)
app.toggle_import_panel()                          # its button, pressed again
_kv_settle(6)
_pa_h = _pa_holder()
_pa_seen['import'] = (_pa_took, _pa_h is not None and bool(_pa_h.winfo_viewable()))
app.show_settings_page()
app.toggle_settings_panel('categories')
_kv_settle(10)
_pa_new = next((e for e in _tl_widgets(app.settings_categories_panel, tk.Entry)), None)
_pa_took = _pa_new is not None and _take_focus(_pa_new)
if _pa_new is not None:
    _pa_new.insert(0, 'Zed')
_pa_click(app._settings_nav_buttons['about'])      # another section
_pa_h = _pa_holder()
_pa_seen['settings'] = (_pa_took, _pa_h is not None and bool(_pa_h.winfo_viewable()))
app.event_generate('<KeyPress-Return>')
_kv_settle(4)
_pa_zed = 'Zed' in NO.CATEGORY_COLORS
NO.CATEGORY_COLORS.pop('Zed', None)
app.hide_settings_page()
_kv_settle(4)
check(f"a click that puts away the part holding the keyboard hands it to "
      f"something in sight: the checklist, the calculator, the import panel, a "
      f"Settings section ({_pa_seen})",
      len(_pa_seen) == 4 and all(a and b for a, b in _pa_seen.values()))
check(f"...so keys typed after it change nothing saved (checklist {_pa_items}, "
      f"a category added: {_pa_zed})", _pa_items == ['eggs'] and not _pa_zed)
# Settings from the find box comes back to the note: the find bar put away
# first parked the keyboard on the window, and nothing was given back.
app._open_find()
_kv_settle(4)
_pa_in_find = _take_focus(app._find_entry)
find_btn_qa6(app.sidebar, '⚙ Settings').invoke()
_kv_settle(6)
find_btn_qa6(app.settings_page, 'Back to Notes').invoke()
_kv_settle(6)
check(f"Settings opened from the find box gives the keyboard back to the note "
      f"({_pa_in_find}, {_pa_holder()})", _pa_in_find and _pa_holder() is app.body_text)
# A tab left with the keyboard on the note list, a Canvas: only a box was
# moved off, and Alt+Up reordered notes behind the Calendar.
_pa_on_list = _take_focus(app.canvas)
app.notebook.select(app.TAB_CALENDAR)
_kv_settle(8)
_pa_h = _pa_holder()
check(f"a tab left with the keyboard on the note list takes it off the list "
      f"({_pa_on_list}, {_pa_h})",
      _pa_on_list and _pa_h is not None and bool(_pa_h.winfo_viewable()))
app.notebook.select(app.TAB_NOTES)
_kv_settle(4)
# Round 5: a toolbar re-dealt by a resize read as put away -- pack maps a
# button laid out again once its row's new size settles -- and the keyboard
# went from B into the note. The case is the watcher looking at B unmapped.
_rb_bold = app._fmt_buttons['bold']
_rb_looked, _rb_rows = [], []
_rb_real_off = app._keyboard_off_part
app._keyboard_off_part = lambda held: (_rb_looked.append(
    (held is _rb_bold, bool(held.winfo_viewable()))), _rb_real_off(held))[1]
try:
    _rb_took = _take_focus(_rb_bold)
    _rb_need = sum(w.winfo_reqwidth() + p[0] + p[1]
                   for w, p, *_r in app._fmt_bar_items)
    for _rb_width in (_rb_need + 50, _rb_need // 2, _rb_need + 50):
        app._reflow_format_bar(_rb_width)              # one row, two, one again
        _rb_rows.append(sum(app._fmt_rows_used))
        _kv_settle(6)
    _rb_h = _pa_holder()
finally:
    del app._keyboard_off_part
    app._reflow_format_bar()
    _kv_settle(4)
check(f"a toolbar re-dealt by a resize keeps the keyboard on B (rows {_rb_rows}; "
      f"looked at B unmapped: {(True, False) in _rb_looked}; on {_rb_h})",
      _rb_took and len(_rb_rows) == 3 and _rb_rows[0] == _rb_rows[2] == 1
      and _rb_rows[1] > 1 and (True, False) in _rb_looked
      and _rb_h is _rb_bold)
app.notes = []
app.save_notes()
app.refresh_note_list()
_kv_settle()

# ---- KEYBOARD: a table cell's menu ----
# Round 4: every row, column and merge command of a table lived in a
# right-click alone, and its two palettes closed at the first Tab with the
# keyboard on nothing. Shift+F10 in a cell opens the cell's menu there, a
# palette it opens takes the keyboard and keeps it, and the keyboard comes
# back into the cell once they are gone.
def _tm_labels(menu):
    out = []
    for i in range((menu.index('end') or -1) + 1):
        if menu.type(i) in ('command', 'cascade'):
            out.append(str(menu.entrycget(i, 'label')))
        if menu.type(i) == 'cascade':
            out += _tm_labels(menu.nametowidget(menu.entrycget(i, 'menu')))
    return out


app.notes = [NO.normalize_note({'id': 981, 'title': 'TmNote',
                                'body': '| Item | Qty |\n| --- | --- |\n| cinnamon | 1 |'})]
app.save_notes()
app.refresh_note_list()
app.open_note_in_tab(app.notes[0])
_kv_settle(8)
_tm_grid = app._grid_at_line(1)
_tm_posted, _tm_in_palette, _tm_back, _tm_found = [], [], False, []
_tm_real_popup = tk.Menu.tk_popup
tk.Menu.tk_popup = lambda _m, *a, **k: _tm_posted.append(_m)
try:
    if _tm_grid is not None:
        app._open_cell_editor(_tm_grid, 1, 0)
        _kv_settle(4)
        _take_focus(app._cell_editor['entry'])
        app.event_generate('<Shift-F10>')           # to the cell, where the keyboard is
        _tm_menu = _tm_posted[-1] if _tm_posted else None
        _tm_found = _tm_labels(_tm_menu) if _tm_menu is not None else []
        if _tm_menu is not None:
            _tm_menu.invoke(next(i for i in range(_tm_menu.index('end') + 1)
                                 if _tm_menu.type(i) == 'command' and str(
                                     _tm_menu.entrycget(i, 'label')).startswith('Highlight')))
        _kv_settle(4)
        _tm_pop = app._mini_popup
        for _tm_key in ('<Tab>', '<Tab>', '<Tab>'):
            try:                                    # gone, it holds nothing
                app.nametowidget(str(app.tk.call('focus', '-lastfor', _tm_pop))
                                 ).event_generate(_tm_key)
                _kv_settle(2)
                _tm_in_palette.append(
                    app._mini_popup is _tm_pop and str(app.tk.call(
                        'focus', '-lastfor', _tm_pop)).startswith(str(_tm_pop) + '.'))
            except (tk.TclError, KeyError, AttributeError):
                _tm_in_palette.append(False)
        if app._mini_popup is not None:
            app.event_generate('<Escape>')
        _kv_settle(20)
        _tm_editor = getattr(app, '_cell_editor', None)
        _tm_back = (_tm_editor is not None and _pa_holder() is _tm_editor['entry']
                    and (_tm_editor['r'], _tm_editor['c']) == (1, 0))
finally:
    tk.Menu.tk_popup = _tm_real_popup
    app._dismiss_mini_popup()
    app._close_cell_editor()
    app.update()
check(f"Shift+F10 in a table cell opens the cell's menu, rows, columns and "
      f"merges in it ({len(_tm_found)} entries)",
      {'Delete row', 'Insert column right', 'Delete column',
       'Merge with cell above'} <= set(_tm_found))
check(f"...a palette it opens takes the keyboard and keeps it through Tab "
      f"({_tm_in_palette})", len(_tm_in_palette) == 3 and all(_tm_in_palette))
check(f"...and the keyboard comes back into the cell once they are gone "
      f"({_pa_holder()})", _tm_back)
app.notes = []
app.save_notes()
app.refresh_note_list()
_kv_settle()

# ---- KEYBOARD: Tab and Enter in a table keep it in the table ----
# Round 5: Tab at the last cell of a table with a separator row (a column
# resized or hidden, a markdown table pasted) added a row and opened no editor:
# the rows were counted with the separator. The keyboard fell to nothing.
def _tt_open(nid, body):
    app.notes = [NO.normalize_note({'id': nid, 'title': f'TtNote{nid}', 'body': body})]
    app.save_notes()
    app.refresh_note_list()
    app.open_note_in_tab(app.notes[0])
    _kv_settle(8)
    return app._grid_at_line(1)


def _tt_press(grid, r, c, key):
    app._open_cell_editor(grid, r, c, select=False)
    _kv_settle(4)
    _take_focus(app._cell_editor['entry'])
    app._cell_editor['entry'].event_generate(key)
    _kv_settle(4)


_tt_sep = None
_tt_grid = _tt_open(991, '| Name | Qty |\n|---|---|\n| Milk | 2 |\n| Eggs | 12 |\nafter')
try:
    if _tt_grid is not None:
        _tt_rows = (_tt_grid['nrows'], _tt_grid['data_rows'])
        _tt_press(_tt_grid, 2, 1, '<Tab>')
        _tt_ed = app._cell_editor
        _tt_sep = (_tt_rows, _tt_ed is not None and (_tt_ed['r'], _tt_ed['c']),
                   _tt_ed is not None and _pa_holder() is _tt_ed['entry'])
finally:
    app._close_cell_editor()
    app.update()
check(f"Tab at the last cell of a table with a separator row opens the editor in "
      f"the new row ((text rows, data rows), cell, holds the keyboard: {_tt_sep})",
      _tt_sep == ((4, 3), (3, 0), True))
# And Enter, or Tab at the last cell, taking a table past what is drawn kept
# it as text with the keyboard on nothing: the keys typed next were lost.
# The limit is set to the table's own height, so one line more passes it.
_tt_flip = {}
for _tt_id, _tt_key, _tt_line in ((992, '<Return>', 3), (993, '<Tab>', 4)):
    _tt_grid = _tt_open(_tt_id, '| Name | Qty |\n| Milk | 2 |\n| Eggs | 12 |\nafter')
    try:
        if _tt_grid is not None and _tt_grid['nrows'] == 3:  # drawn, no separator
            app.MAX_DRAWN_TABLE_PX = app._grid_row_height() * 3
            _tt_press(_tt_grid, 2, 1, _tt_key)
            _tt_gone = app._grid_at_line(1) is None
            _tt_held = _pa_holder() is app.body_text
            app.event_generate('<KeyPress-x>')         # where the keyboard is
            _kv_settle(2)
            _tt_flip[_tt_key] = (_tt_gone, _tt_held, NO.core_tables.split_row(
                app.body_text.get(f'{_tt_line}.0', f'{_tt_line}.end')))
    finally:
        app.__dict__.pop('MAX_DRAWN_TABLE_PX', None)
        app._close_cell_editor()
        app.update()
check(f"Enter, and Tab at the last cell, that take a table past what is drawn put "
      f"the keyboard in its text, in the cell ((kept as text, keyboard in the "
      f"note, the row typed into): {_tt_flip})",
      _tt_flip == {'<Return>': (True, True, ['Eggs', '12<br>x']),
                   '<Tab>': (True, True, ['x', ''])})

# Round 6: Escape in a cell, and Ctrl+V of copied cells, closed the editor
# holding the keyboard and left it on nothing -- what was typed next went
# nowhere, and Tab began again at the tab strip. Escape leaves it in the
# note's text under the table, where the caret goes from a drawn table's
# lines; a paste of cells brings it back to the cell, as the same paste from
# the cell's menu does, or into the table's text once the paste takes the
# table past what is drawn. And Enter mid-cell taking the table past it puts
# the caret after the break it made, not at the cell's end.
_tw_seen = {}
_tw_cases = (
    ('Escape', 994, '| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\nafter',
     '<Escape>', None, None),
    ('Ctrl+V of cells', 995, '| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\nafter',
     '<Control-v>', 'p\tq', None),
    ('Ctrl+V of cells past the drawn limit', 996,
     '| Name | Qty |\n| Milk | 2 |\n| Eggs | 12 |\nafter', '<Control-v>',
     'x\ty\nz\tw', None),
    ('Enter mid-cell past the drawn limit', 997,
     '| Name | Qty |\n| Milk | 2 |\n| Eggs | 12 |\nafter', '<Return>', None, '1.2'))
for _tw_name, _tw_id, _tw_body, _tw_key, _tw_clip, _tw_caret in _tw_cases:
    _tw_grid = _tt_open(_tw_id, _tw_body)
    try:
        if _tw_grid is None:
            continue
        if 'limit' in _tw_name:
            app.MAX_DRAWN_TABLE_PX = app._grid_row_height() * _tw_grid['nrows']
        if _tw_clip is not None:
            app.clipboard_clear()
            app.clipboard_append(_tw_clip)
        app._open_cell_editor(_tw_grid, 2, 0, select=False)
        _kv_settle(4)
        _tw_entry = app._cell_editor['entry']
        _take_focus(_tw_entry)
        if _tw_caret is not None:
            _tw_entry.mark_set('insert', _tw_caret)
        _tw_entry.event_generate(_tw_key)
        _kv_settle(4)
        _tw_ed = app._cell_editor
        _tw_held = _pa_holder()
        _tw_where = ('the cell' if _tw_ed is not None and _tw_held is _tw_ed['entry']
                     and (_tw_ed['r'], _tw_ed['c']) == (2, 0)
                     else 'the note' if _tw_held is app.body_text else str(_tw_held))
        app.event_generate('<KeyPress-x>')             # where the keyboard is
        _kv_settle(2)
        if _tw_ed is not None and app._cell_editor is _tw_ed:
            _tw_typed = _tw_ed['entry'].get('1.0', 'end-1c')
        else:
            _tw_typed = tuple(app.body_text.get(f'{n}.0', f'{n}.end') for n in (3, 5))
        _tw_seen[_tw_name] = (_tw_where, _tw_typed)
    finally:
        app.__dict__.pop('MAX_DRAWN_TABLE_PX', None)
        app._close_cell_editor()
        app.update()


def _tw_cells(name):
    """Where the keyboard was, and the cells of line 3 and line 5 after."""
    where, typed = _tw_seen.get(name, (None, ('', '')))
    if isinstance(typed, str):
        return where, typed
    return where, NO.core_tables.split_row(typed[0]), typed[1]


check(f"every way out of a table cell leaves the keyboard somewhere: Escape under "
      f"the table, a paste of cells back in the cell or in the table's text, "
      f"Enter mid-cell after its break ((where, what the next key typed): "
      f"{_tw_seen})",
      _tw_cells('Escape') == ('the note', ['1', '2'], 'xafter')
      and _tw_cells('Ctrl+V of cells') == ('the cell', 'px')
      and _tw_cells('Ctrl+V of cells past the drawn limit')[:2] == ('the note',
                                                                      ['xx', 'y'])
      and _tw_cells('Enter mid-cell past the drawn limit')[:2] == (
          'the note', ['Eg<br>xgs', '12']))
app.notes = []
app.save_notes()
app.refresh_note_list()
_kv_settle()

# ---- A POPUP THAT GROWS STAYS INSIDE THE WINDOW ----
# Round 4: the template editor grew with its checklist and never scrolled,
# placed once for the height it opened at: 25 items, or one long one, put
# Save, Category and the Add box below the screen. The picker did the same
# with as many templates. What grows scrolls, and a popup that grows is
# placed again.
def _gp_inside(w):
    bottom = app.winfo_rooty() + app.winfo_height()
    return (w is not None and w.winfo_ismapped()
            and w.winfo_rooty() + w.winfo_height() <= bottom + 1
            and w.winfo_rooty() >= app.winfo_rooty() - 1)


app.geometry('900x600')
_kv_settle(10)
_gp_seen = {}
try:
    # Opened small, so it is placed for a short editor, then grown by
    # the Add box -- 24 items and one long one -- past the window's height.
    app._edit_template({'name': 'Packing', 'checklist': [{'text': 'socks'}]},
                       lambda: None)
    _kv_settle(10)
    _gp_pop = app._mini_popup
    _gp_add = list(_tl_entries(_gp_pop))[-1]       # the checklist's Add box
    _gp_seen['typing in its Add box'] = _take_focus(_gp_add)
    for _gp_i in range(25):
        _gp_add.insert(0, 'w ' * 900 if _gp_i == 24 else 'item %d' % _gp_i)
        app.event_generate('<Return>')             # Tk sends it to the box
        app.update()
    _kv_settle(10)
    _gp_seen['editor'] = _gp_inside(_gp_pop)
    _gp_seen['its Save'] = _gp_inside(find_btn_qa6(_gp_pop, 'Save'))
    app._bring_into_sight(_gp_add)
    _kv_settle(4)
    _gp_seen['its Add box, brought into sight'] = _gp_inside(_gp_add)
finally:
    app._dismiss_mini_popup()
    app.update()
_gp_kept = list(app.templates)
app.templates = [{'name': 'Template %d' % _gp_i, 'body': 'x'} for _gp_i in range(40)]
try:
    app.show_template_picker()
    _kv_settle(10)
    _gp_pick = app._mini_popup
    _gp_last = [b for b in _tl_widgets(_gp_pick, tk.Button)
                if 'Template 39' in str(b.cget('text'))]
    _gp_seen['picker'] = _gp_inside(_gp_pick)
    if _gp_last:
        app._bring_into_sight(_gp_last[0])
        _kv_settle(4)
    _gp_seen['its last template, brought into sight'] = bool(_gp_last) and _gp_inside(_gp_last[0])
finally:
    app._dismiss_mini_popup()
    app.templates = _gp_kept
    app.geometry('1100x750')
    _kv_settle(6)
check(f"the template editor grown to 26 items, and the picker with 40 "
      f"templates, stay inside a 900x600 window, what they hold in reach "
      f"({_gp_seen})", len(_gp_seen) == 6 and all(_gp_seen.values()))
app.notes = []
app.save_notes()
app.refresh_note_list()
_kv_settle()

# ---- KEYBOARD: a tick box is looked at the moment it is pressed ----
# Round 3 of the final audit: the look after Space waited 100 ms for every
# Tk button, though a tick box runs its command at once. A template's tick
# box redraws its list, the keyboard fell to the editor's own window, and a
# Tab inside those 100 ms went to the header's ✕, whose next Space closed the
# editor without a question.
def _cb_boxes(w):
    for c in w.winfo_children():
        if isinstance(c, tk.Checkbutton):
            yield c
        yield from _cb_boxes(c)


_cb_after = None
_cb_on_x = None
try:
    app._edit_template({'name': 'CbTemplate', 'title': '', 'body': '',
                        'category': 'General',
                        'checklist': [{'text': 'one', 'done': False},
                                      {'text': 'two', 'done': False}]},
                       lambda: None)
    app.update()
    _cb_pop = app._mini_popup
    _cb_first = next(_cb_boxes(_cb_pop), None) if _cb_pop is not None else None
    if _cb_first is not None and _take_focus(_cb_first):
        _cb_first.event_generate('<space>')
        app.update()                    # what a person's next key waits for
        time.sleep(0.04)
        try:
            _cb_now = app.nametowidget(str(app.tk.call('focus', '-lastfor', _cb_pop)))
        except (KeyError, tk.TclError):
            _cb_now = _cb_pop
        _cb_now.event_generate('<Tab>')
        _kv_settle(10)
        try:
            _cb_after = app.nametowidget(str(app.tk.call('focus', '-lastfor', _cb_pop)))
        except (KeyError, tk.TclError):
            _cb_after = None
        _cb_on_x = (isinstance(_cb_after, tk.Button)
                    and str(_cb_after.cget('text')) == '✕')
finally:
    app._dismiss_mini_popup()
    app.update()
check(f'Space on a template\'s tick box, then Tab 40 ms later, goes on from '
      f'the box, not to the editor\'s ✕ ({_cb_after})',
      _cb_after is not None and _cb_on_x is False
      and not isinstance(_cb_after, tk.Toplevel))

# ---- THE TEMPLATE PREVIEW IS DRAWN AGAIN ONLY WHEN ITS TABLES CHANGE ----
# Round 4: every key in the template editor redrew one canvas item per line
# of every cell -- 0.16 s a key for one paste of line breaks -- though the
# tables are out of the box's sight and typing never changes them.
_pv_ids = []
try:
    app._edit_template({'name': 'Prev', 'body': '| a | b |\n| --- | --- |\n| '
                        + '<br>'.join(['x'] * 200) + ' | y |'}, lambda: None)
    _kv_settle(6)
    _pv_pop = app._mini_popup
    _pv_body = [t for t in _tl_widgets(_pv_pop, tk.Text) if int(t.cget('height')) >= 4][0]
    _pv_cv = [c for c in _tl_widgets(_pv_pop, tk.Canvas) if c.find_all()
              and any(c.type(i) != 'window' for i in c.find_all())][0]
    for _pv_change in (False, False, True):
        if _pv_change:
            _pv_body.insert('3.2', 'w')                # inside the table's cell
        app._draw_template_table_preview(_pv_cv, _pv_body)
        _pv_ids.append(_pv_cv.find_all())
finally:
    app._dismiss_mini_popup()
    app.update()
check(f"the template preview is drawn again only when its tables change "
      f"({[len(i) for i in _pv_ids]} items; kept: {len(_pv_ids) == 3 and _pv_ids[0] == _pv_ids[1]}, "
      f"redrawn: {len(_pv_ids) == 3 and _pv_ids[1] != _pv_ids[2]})",
      len(_pv_ids) == 3 and len(_pv_ids[0]) > 200 and _pv_ids[0] == _pv_ids[1]
      and _pv_ids[1] != _pv_ids[2])

# ---- A PASTE OVER A SELECTION IN A LIMITED BOX REPLACES IT, SHORTENED ----
# Round 4: off X11, Tk's own paste deletes the selection and inserts as two
# edits; the delete passed the limit's check, the insert did not, and what
# was typed was gone. Windows' paste is run here on every system. Since
# round 5 a paste past the limit is shortened to the room the selection
# leaves, as the title's is.
_wp_real_bind = str(app.tk.call('bind', 'Entry', '<<Paste>>'))
_wp_real_read = NO.clipboard.read_text
_wp_kept = None
app.tk.call('bind', 'Entry', '<<Paste>>',
            'catch {%W delete sel.first sel.last}\n'
            '%W insert insert [::tk::GetSelection %W CLIPBOARD]\n'
            'tk::EntrySeeInsert %W')
try:
    app._edit_template(None, lambda: None)
    _kv_settle(6)
    _wp_box = list(_tl_entries(app._mini_popup))[-1]       # the checklist's Add box
    _wp_box.insert(0, 'y' * 1900)
    _wp_box.selection_range(1800, 'end')                   # the last 100 chosen
    app.clipboard_clear()
    app.clipboard_append('z' * 2500)
    NO.clipboard.read_text = lambda: 'z' * 2500
    _wp_box.event_generate('<<Paste>>')
    app.update()
    _wp_kept = _wp_box.get()
finally:
    NO.clipboard.read_text = _wp_real_read
    app.tk.call('bind', 'Entry', '<<Paste>>', _wp_real_bind)
    app.clipboard_clear()
    app._dismiss_mini_popup()
    app.update()
check(f"a paste past a box's limit over its selection replaces it, shortened to "
      f"the room left ({_wp_kept.count('y') if _wp_kept is not None else None} "
      f"typed and {_wp_kept.count('z') if _wp_kept is not None else None} pasted)",
      _wp_kept == 'y' * 1800 + 'z' * 200)

# ---- A checklist item left in an Add box goes into the template saved ----
# Round six of the final audit (a twin the Android fixer named): the template
# editor's Save, its question on closing and its quiet save read the
# checklist without the item typed in its Add box and not yet added, so a
# "passport" typed there and saved was lost with the editor; Save as template
# read a note's checklist the same way. The note's box keeps its item.
_pa_seen = {}
_pa_real_ask = app.ask_yes_no_cancel
_pa_kept = list(app.templates)
try:
    app.templates = []
    app._edit_template(None, lambda: None)
    _kv_settle(6)
    _pa_pop = app._mini_popup
    _pa_boxes = list(_tl_entries(_pa_pop))
    _pa_boxes[-1].insert(0, 'passport')                 # typed, never added
    _pa_asked = []
    app.ask_yes_no_cancel = lambda *a, **k: (_pa_asked.append(a[0]), None)[1]
    _pa_seen['closing asks'] = (_pa_pop._confirm_dismiss() is False
                                and _pa_asked == ['Save changes?'])
    app.ask_yes_no_cancel = _pa_real_ask
    _pa_boxes[0].delete(0, 'end')                       # "Untitled template"
    _pa_boxes[0].insert(0, 'PendTpl')
    find_btn_qa6(_pa_pop, 'Save').invoke()
    app.update()
    _pa_saved = [t for t in app.templates if t.get('name') == 'PendTpl']
    _pa_seen['Save keeps it'] = (len(_pa_saved) == 1 and [
        i.get('text') for i in _pa_saved[0].get('checklist', [])] == ['passport'])
finally:
    app.ask_yes_no_cancel = _pa_real_ask
    app._dismiss_mini_popup()
    app.update()
app.notes = [NO.normalize_note({'id': 952, 'title': 'PaNote', 'body': 'b',
                                'checklist': [{'text': 'socks', 'done': False}]})]
app.save_notes()
app.refresh_note_list()
app.open_note_in_tab(app.notes[0])
_kv_settle(6)
try:
    app.checklist_add_var.set('towel')                  # typed, never added
    app.save_current_as_template()
    app.update()
    _pa_name = next(_tl_entries(app._mini_popup), None)
    if _pa_name is not None:
        _pa_name.delete(0, 'end')
        _pa_name.insert(0, 'FromNote')
        find_btn_qa6(app._mini_popup, 'Save').invoke()
        app.update()
    _pa_from = [t for t in app.templates if t.get('name') == 'FromNote']
    _pa_seen['Save as template keeps it'] = (len(_pa_from) == 1 and [
        i.get('text') for i in _pa_from[0].get('checklist', [])] == ['socks', 'towel'])
    _pa_seen["the note's box keeps it"] = app.checklist_add_var.get() == 'towel'
finally:
    app.checklist_add_var.set('')
    app._dismiss_mini_popup()
    app.templates = _pa_kept
    app.update()
check(f"an item typed in a checklist's Add box and not added goes into the "
      f"template saved, and closing the editor asks about it ({_pa_seen})",
      len(_pa_seen) == 4 and all(_pa_seen.values()))

# ...and a template's list at 1,000 items: its Add, and words waiting in the
# box, were cut by normalize_template at Save, unsaid, and the editor closed
# without asking (round 6). The Add and Save refuse them and say why; closing
# asks; Save as template from a full note says so too.
_cfp_seen, _cfp_said = {}, []
_cfp_real = (app.show_info, app.ask_yes_no_cancel)
_cfp_kept = list(app.templates)
app.show_info = lambda *a, **k: _cfp_said.append(a[0] if a else '')
_cfp_full = [{'text': 'row %d' % i, 'done': False} for i in range(1000)]
try:
    app.templates = [NO.normalize_template({'name': 'Full', 'body': 'b',
                                            'checklist': _cfp_full})]
    app._edit_template(app.templates[0], lambda: None)
    _kv_settle(6)
    _cfp_pop = app._mini_popup
    _cfp_boxes = list(_tl_entries(_cfp_pop))
    _cfp_boxes[-1].insert(0, 'passport')
    find_btn_qa6(_cfp_pop, '+ Add').invoke(); app.update()
    _cfp_seen['Add refused, words kept'] = (_cfp_boxes[-1].get() == 'passport'
                                            and _cfp_said == ['Checklist full'])
    _cfp_asked = []
    app.ask_yes_no_cancel = lambda *a, **k: (_cfp_asked.append(a[0]), None)[1]
    _cfp_seen['closing asks'] = (_cfp_pop._confirm_dismiss() is False
                                 and _cfp_asked == ['Save changes?'])
    find_btn_qa6(_cfp_pop, 'Save').invoke(); app.update()
    _cfp_seen['Save refused, said'] = (_cfp_said == ['Checklist full'] * 2
                                       and app._mini_popup is _cfp_pop)
finally:
    app.show_info, app.ask_yes_no_cancel = _cfp_real[0], _cfp_real[1]
    app._dismiss_mini_popup()
    app.update()
app.show_info = lambda *a, **k: _cfp_said.append(a[0] if a else '')
app.notes = [NO.normalize_note({'id': 953, 'title': 'FullNote', 'body': 'b',
                                'checklist': _cfp_full})]
app.save_notes()
app.refresh_note_list()
app.open_note_in_tab(app.notes[0])
_kv_settle(6)
try:
    app.checklist_add_var.set('towel')
    app.save_current_as_template()
    app.update()
    _cfp_name = next(_tl_entries(app._mini_popup), None)
    if _cfp_name is not None:
        _cfp_name.delete(0, 'end')
        _cfp_name.insert(0, 'FromFull')
        find_btn_qa6(app._mini_popup, 'Save').invoke()
        app.update()
    _cfp_from = [t for t in app.templates if t.get('name') == 'FromFull']
    _cfp_seen['Save as template says so'] = (
        len(_cfp_from) == 1 and len(_cfp_from[0].get('checklist', [])) == 1000
        and _cfp_said == ['Checklist full'] * 3)
finally:
    app.show_info = _cfp_real[0]
    app.checklist_add_var.set('')
    app._dismiss_mini_popup()
    app.templates = _cfp_kept
    app.update()
check(f"a template's list at 1,000 items refuses more at its Add and Save, "
      f"says why, and closing asks ({_cfp_seen}, {_cfp_said})",
      len(_cfp_seen) == 4 and all(_cfp_seen.values()))

# Round 8: round 7 taught Enter held down to press once on a drawn control,
# the preview's buttons and a question's answers -- not the note list, the
# calendar or the boxes that act on Enter. A group header folded and opened
# at every repeat, writing settings.json each time; and a press nobody asked
# about left the next control blind to the key still held. Every Enter that
# acts asks (_enter_repeats), in both shapes a held key takes.
_kr8_seen, _kr8_counts = {}, []
_kr8_keys_kept = _kh_support.REAL_KEYS
_kr8_names = ('_toggle_group_collapsed', '_toggle_note_selected', 'open_day_popup',
              'show_info', '_settle_date_fields')
_kr8_real = {n: getattr(app, n) for n in _kr8_names}
_kr8_had = {n: app.__dict__[n] for n in _kr8_names if n in app.__dict__}
_kr8_kept_notes, _kr8_kept_templates = list(app.notes), list(app.templates)
_kr8_t = [300_000]


def _kr8_counting(name, then=None):
    def counted(*a, **k):
        _kr8_counts.append(name)
        return then(*a, **k) if then is not None else None
    return counted


def _kr8_key(kind, when):
    # To the widget holding the keyboard, in whichever window: an inline
    # rename is a window of its own, which `focus -lastfor` does not see.
    try:
        holder = app.focus_get()
    except (KeyError, tk.TclError):
        holder = None
    (holder or _ka_holder() or app).event_generate(f'<Key{kind}-Return>', time=when)
    _kv_settle(2)


def _kr8_hold(widget, ready=lambda: None):
    """Enter held on *widget* in both shapes: how often each acted."""
    seen = []
    for shape in ('presses alone', 'release and press'):
        _take_focus(widget)
        ready()
        _kv_settle(2)
        app._cancel_pending_autosave()
        del _kr8_counts[:]
        t0 = _kr8_t[0] = _kr8_t[0] + 10_000
        _kr8_key('Press', t0)
        for i in range(10):
            if shape == 'release and press':
                _kr8_key('Release', t0 + 500 + 33 * i)
            _kr8_key('Press', t0 + 500 + 33 * i)
        _kr8_key('Release', t0 + 900)
        seen.append(len(_kr8_counts))
    return seen


_kh_support.REAL_KEYS = [('the held-Enter check', 'its own keys')]
try:
    app.show_info = _kr8_counting('show_info')          # no modal waits here
    app.open_day_popup = _kr8_counting('open_day_popup')
    app._toggle_group_collapsed = _kr8_counting(
        '_toggle_group_collapsed', _kr8_real['_toggle_group_collapsed'])
    app._toggle_note_selected = _kr8_counting(
        '_toggle_note_selected', _kr8_real['_toggle_note_selected'])
    app._settle_date_fields = _kr8_counting(
        '_settle_date_fields', _kr8_real['_settle_date_fields'])
    app.new_note(); _kv_settle(2)
    _kr8_a, _kr8_b = (NO.normalize_note({'id': 4901 + i, 'title': 'Held %d' % i,
                                         'body': 'b', 'category': 'General'})
                      for i in range(2))
    app.notes = [_kr8_a, _kr8_b]; app.save_notes()
    app.notebook.select(app.TAB_NOTES)
    app.group_by_category.set(True); app._on_toggle_group_by_category()
    app.collapsed_groups.clear(); app.refresh_note_list(); _kv_settle(4)
    _kr8_seen['a group header'] = _kr8_hold(
        app.canvas, lambda: app._set_ring_row(('header', 'General')))
    app.collapsed_groups.clear(); app.refresh_note_list(); _kv_settle(4)
    app._toggle_selection_mode(); _kv_settle(2)
    _kr8_seen['a note, in selection mode'] = _kr8_hold(
        app.canvas, lambda: app._set_ring_row(('note', 4901)))
    app._toggle_selection_mode(); _kv_settle(2)
    app.group_by_category.set(False); app._on_toggle_group_by_category()
    app.notebook.select(app.TAB_CALENDAR)
    app.render_calendar(); _kv_settle(6)
    _kr8_seen['a calendar day'] = _kr8_hold(app.cal_canvas)
    app.notebook.select(app.TAB_NOTES); _kv_settle(2)
    _kr8_full = NO.normalize_note({'id': 4903, 'title': 'Full', 'body': 'b', 'checklist': [
        {'text': 'item %d' % i, 'done': False} for i in range(1000)]})
    app.notes = [_kr8_full]; app.save_notes()
    app.open_note_in_tab(_kr8_full); _kv_settle(4)
    if not app._checklist_open:
        app.toggle_checklist_section(); _kv_settle(4)
    app.checklist_add_var.set('one more')
    _kr8_seen["a full list's Add box"] = _kr8_hold(app.checklist_add_entry)
    app.checklist_add_var.set('')
    _kr8_seen['the date field'] = _kr8_hold(app.date_entry)
    app.templates = [NO.normalize_template({'name': 'Full', 'body': 'b', 'checklist': [
        {'text': 'row %d' % i, 'done': False} for i in range(1000)]})]
    app._edit_template(app.templates[0], lambda: None)
    _kv_settle(6)
    _kr8_tpl_box = (list(_tl_entries(app._mini_popup)) or [None])[-1]
    if _kr8_tpl_box is not None:
        _kr8_tpl_box.insert(0, 'passport')
        _kr8_seen["a full template's Add box"] = _kr8_hold(_kr8_tpl_box)
    app._dismiss_mini_popup()
    _kv_settle(2)
    # A name refused keeps the box open, so every repeat would reach it.
    app._show_inline_rename(app.title_entry, 'Name',
                            _kr8_counting('an inline rename', lambda text: False))
    _kv_settle(4)
    _kr8_box = next(_tl_entries(app._mini_popup), None)
    _kr8_seen['an inline rename'] = _kr8_hold(_kr8_box) if _kr8_box else None
finally:
    for _kr8_n in _kr8_names:
        app.__dict__.pop(_kr8_n, None)
    app.__dict__.update(_kr8_had)
    app._dismiss_mini_popup()
    app.checklist_add_var.set('')
    if app.selection_mode:
        app._toggle_selection_mode()
    app.group_by_category.set(False); app._on_toggle_group_by_category()
    app.collapsed_groups.clear()
    app.new_note(); _kv_settle(2)
    app.notes = _kr8_kept_notes; app.save_notes()
    app.templates = _kr8_kept_templates
    app.notebook.select(app.TAB_NOTES)
    app.refresh_note_list(); _kv_settle(4)
    _kh_support.REAL_KEYS = _kr8_keys_kept
check(f"Enter held on the note list, the calendar and every box that acts on it "
      f"presses once ((presses alone, release and press): {_kr8_seen})",
      _kr8_seen == {k: [1, 1] for k in (
          'a group header', 'a note, in selection mode', 'a calendar day',
          "a full list's Add box", 'the date field', "a full template's Add box",
          'an inline rename')})

print()
print(f"=== QA6 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
