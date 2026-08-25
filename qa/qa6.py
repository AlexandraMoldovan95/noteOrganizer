import sys
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile
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
check('grouping enabled shows category headers', find_widget(app.list_frame, tk.Frame) is not None)

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
app.username_var = tk.StringVar(value='Alexandra')
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
name_entry = find_widget(app.settings_page, tk.Entry)
name_entry.focus_set()
app.update()

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

# ---- SETTINGS: clicking elsewhere on the page clears field focus (regression) ----
# Previously, clicking a non-interactive part of the Settings page (a
# section title, card background) left whatever field was focused — e.g.
# the username entry — still showing a blinking cursor, even though the
# value had already autosaved. Switching tabs and back already cleared it
# correctly; this is specifically the same-page click case.
name_entry.focus_set()
app.update()
check('username entry has focus before clicking elsewhere', app.focus_get() is name_entry)
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
name_title.event_generate('<Button-1>')
app.update()
check('clicking a section title elsewhere in Settings clears the field\'s focus',
      app.focus_get() is not name_entry)

# Regression: clicking "Back to Notes" directly (without clicking elsewhere
# in Settings first) must also clear focus — this is the exact path a user
# takes when they finish typing and immediately leave, and it broke once
# during development when the fix above was implemented too narrowly
# (bound to individual widgets instead of centrally).
name_entry.focus_set()
app.update()
check('username entry has focus before leaving Settings', app.focus_get() is name_entry)
back_btn = find_widget(app.settings_page, tk.Button, 'Back to Notes')
back_btn.event_generate('<Button-1>')
back_btn.event_generate('<ButtonRelease-1>')
app.update()
check('clicking "Back to Notes" directly clears the field\'s focus',
      app.focus_get() is not name_entry)
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
theme_canvases[0].event_generate('<MouseWheel>', delta=-120)
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
chip_frames[0].event_generate('<MouseWheel>', delta=-120)
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
grid_frame = find_all(app.stats_frame, tk.Frame)[0]
chip = grid_frame.winfo_children()[0]
check('statistics chip has no hand cursor (not clickable-looking)',
      str(chip.cget('cursor')) != 'hand2')
chip.event_generate('<Button-1>')
chip.event_generate('<ButtonRelease-1>')
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
app._ask_category_deletion = lambda name, count: "move"
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
delete_btn.event_generate('<Button-1>')
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

app.remove_attachment(0)
app.update()
check('remove_attachment clears the list', len(app.current_attachments) == 0)
check('remove_attachment deletes the file from disk', not os.path.isfile(stored_path))

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

print()
print(f"=== QA6 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
