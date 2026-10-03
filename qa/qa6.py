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
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile
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
NO.save_setting('trash_retention_days', 'forever')
check("a hand-edited 'forever' reads as the default",
      NO.trash_retention_days() == 30)
NO.save_setting('trash_retention_days', 0)
check('zero days clamps to one -- never purge-everything',
      NO.trash_retention_days() == 1)
import datetime as _dtQW
_oldQW = (_dtQW.datetime.now()
          - _dtQW.timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
_entryQW = {'id': 9990, 'title': 'old', 'deleted_at': _oldQW,
            'attachments': []}
NO.save_setting('trash_retention_days', 7)
_keptQW, _nQW = NO.purge_expired_trash([dict(_entryQW)])
NO.save_setting('trash_retention_days', 30)
_keptQW2, _nQW2 = NO.purge_expired_trash([dict(_entryQW)])
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
_rt_kept, _rt_purged = NO.purge_expired_trash([dict(e) for e in app.trash])
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


check('no Restore-selected button while nothing is ticked',
      _c14_button('selected') is None
      or not _c14_button('selected').winfo_ismapped())
# Tick two of the four.
_c14_ticks[0].invoke(); _c14_ticks[2].invoke()
app.update()
_c14_restore = _c14_button('selected')
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
_c14_after = _c14_button('selected')
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
_sid_btn = _c14_button('selected')
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

# Every redraw of Recently deleted bound a new handler on the frame that
# holds its rows -- a frame that outlives the redraw -- and Tk keeps a
# command for each one: one more per Restore, Delete, page or toast Undo
# while the panel was open, for good. The Categories list did the same
# on every rename, recolour and delete.
def _lk_cmds():
    return len(app.tk.splitlist(app.tk.call('info', 'commands')))


app.trash = [{'id': 6100 + i, 'title': 'Leak %d' % i, 'body': 'x',
              'category': 'General',
              'deleted_at': '2026-03-%02d 00:00:00' % (i + 1)} for i in range(3)]
NO.save_trash(app.trash)
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
_lk_redraw = app._trash_panel_redraw
_lk_redraw(); app.update()
_lk_before = _lk_cmds()
for _lk_i in range(30):
    _lk_redraw()
app.update()
_lk_after = _lk_cmds()
check(f'redrawing Recently deleted 30 times leaves no Tcl command behind '
      f'({_lk_before} -> {_lk_after})', _lk_after - _lk_before < 5)
_lk_canvas = app._active_panel_canvas
_lk_items = _lk_canvas.find_all()
_lk_rows = (_lk_canvas.nametowidget(_lk_canvas.itemcget(_lk_items[0], 'window'))
            if _lk_items else None)
check('...while the wheel still reaches the list and every row in it',
      _lk_rows is not None and bool(_lk_rows.bind('<MouseWheel>'))
      and len(_lk_rows.winfo_children()) >= 3
      and all(r.bind('<MouseWheel>') for r in _lk_rows.winfo_children()))
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
_od_items = _od_canvas.find_all()
_od_rows = (_od_canvas.nametowidget(_od_canvas.itemcget(_od_items[0], 'window'))
            if _od_items else None)


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
if _lk_cat_redraws:
    _lk_cat_redraws[-1](); app.update()
    _lk_before = _lk_cmds()
    for _lk_i in range(30):
        _lk_cat_redraws[-1]()
    app.update()
    _lk_after = _lk_cmds()
check(f'redrawing the Categories list 30 times leaves no Tcl command behind '
      f'({_lk_before} -> {_lk_after})',
      bool(_lk_cat_redraws) and _lk_after - _lk_before < 5)
# The Templates list, the same shape: redrawn at every save, delete and
# rename of a template.
_lk_tpl_saved = list(app.templates)
app.templates = [NO.normalize_template({'name': 'Leak tpl %d' % i, 'body': 'x'})
                 for i in range(3)]
app.toggle_settings_panel('templates'); app.update()
_lk_tpl_redraw = getattr(app, '_refresh_templates_panel', None)
if _lk_tpl_redraw is not None:
    _lk_tpl_redraw(); app.update()
    _lk_before = _lk_cmds()
    for _lk_i in range(30):
        _lk_tpl_redraw()
    app.update()
    _lk_after = _lk_cmds()
check(f'redrawing the Templates list 30 times leaves no Tcl command behind '
      f'({_lk_before} -> {_lk_after})',
      _lk_tpl_redraw is not None and _lk_after - _lk_before < 5)
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


def _stats_says(text):
    found = []

    def walk(w):
        try:
            if text in str(w.cget('text')):
                found.append(w)
        except tk.TclError:
            pass
        for kid in w.winfo_children():
            walk(kid)
    if hasattr(app, 'stats_frame'):
        walk(app.stats_frame)
    return bool(found)


app.show_settings_page()
app.toggle_settings_panel('statistics')
app.update()
check('arriving at Statistics shows the count as it is now',
      _stats_says('5'))
# Deleted from under an open Settings page: the panel must follow.
app._delete_note(app.find_note(620), None)
app.update()
check('a delete while Statistics is open updates it', _stats_says('4'))
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
check('Statistics is current on the next visit, not left behind',
      _stats_says('2') and not _stats_says('4'))
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


print()
print(f"=== QA6 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
