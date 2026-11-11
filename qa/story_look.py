"""Photograph the app's screens, and say what MOVED since last time.

WHY THIS EXISTS
---------------
The suite answers questions. The stories walk paths. Neither can see a
screen that simply stopped looking right: a control clipped, a panel
sliding under another one, a colour that stayed behind after a theme
switch. Twice in this project a bug was invisible in the source and
obvious in a photograph, and both times a person had to be looking.

This takes the photographs itself and compares them with the ones from
the last run. What it reports is not "this is wrong" -- it cannot know
that -- but "this changed, and nobody said it would". A change you asked
for is approved by running with ``--accept``; anything else is worth a
look before it ships.

WHAT IT IS NOT
--------------
It is not a pixel-perfect gate. Text rendering shifts by a pixel between
runs for reasons nobody controls, so a tiny difference is noise and is
reported as such. It answers one question honestly: did a screen change
shape while we were not looking?

HOW SMALL A THING IT CANNOT SEE, measured rather than guessed. The
comparison reduces each picture to a 40x40 grid, so one cell is about
1/1600 of the screen -- roughly 43x31 pixels at the size these are taken.
A control smaller than that can appear or vanish and this tool will report
"same". Measured: adding the search box's clear button moved 0.0%. So a
green run means no screen changed SHAPE; it does not mean no button came
or went. For a small control, look at the picture.

    py qa/story_look.py            # compare against the stored shots
    py qa/story_look.py --accept   # bless what is on screen now

The stored shots live in qa/screens/ and are meant to be committed, so a
change of appearance shows up in a diff like any other change.
"""
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STORE = os.path.join(HERE, "screens")

# Each scene: a name, and what to do to the app before the picture.
SCENES = [
    ("01-note-list", """
app.notebook.select(app.TAB_NOTES)
app.refresh_note_list()
"""),
    ("02-editor", """
app.notebook.select(app.TAB_NOTES)
app.open_note_in_tab(app.notes[0])
"""),
    ("03-calendar", """
app.notebook.select(app.TAB_CALENDAR)
app.cal_year, app.cal_month = 2026, 9
app.render_calendar()
"""),
    ("04-settings-trash", """
app.show_settings_page()
app.toggle_settings_panel('trash')
"""),
    ("05-settings-categories", """
app.show_settings_page()
app.toggle_settings_panel('categories')
"""),
    ("06-light-theme", """
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.set_theme(NO.LIGHT_THEMES[0])
app.refresh_note_list()
"""),
    # ---- The five scenes below were added for 0.76.192, because five of
    # that release's seven changes were about how something LOOKS and none
    # of the six scenes above contains any of them: the search box is
    # always empty here, the template editor is never open, and no popup
    # or Share panel is ever on screen. A check reading a widget's
    # properties cannot see that a new button crowds the text beside it.
    ("07-search-with-a-query", """
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
# 'dark', the key. The display name 'Midnight' was passed here and set_theme
# ignores a name it does not know, so every scene from here on was taken in
# the light theme scene 06 left behind -- without anyone choosing that.
app.set_theme('dark')
assert app.theme_name == 'dark', 'the dark theme was not applied'
app.search_var.set('bread')
app.refresh_note_list()
"""),
    ("08-share-panel-with-a-code", """
# The box as the app opens it, hint and hint colour. Set to '' it waits for
# a <FocusOut> to write the hint back, and every later scene photographed
# an empty, unlabelled box (tools/doc_screenshots.py had the same bug).
app.search_var.set(app.SEARCH_PLACEHOLDER)
app.search_entry.config(fg=app.colors['subtext'])
app.refresh_note_list()
app.toggle_share_panel()
# The EXISTING vars are set rather than replaced: the checkbuttons on screen
# are bound to the ones the panel built, so a fresh BooleanVar would generate
# a code for notes whose boxes still looked unticked -- a picture that lies
# about what was asked for.
app._share_vars[app._order_identity(app.notes[0])].set(True)
app._share_vars[app._order_identity(app.notes[1])].set(True)
app.notes[0]['attachments'] = [{'filename': 'f.txt', 'stored_as': 'x_f.txt'}]
app._generate_inline_share()
"""),
    ("09-template-editor", """
app.notes[0].pop('attachments', None)
app.toggle_share_panel()
app.hide_settings_page()
app.templates.append(NO.normalize_template({
    'name': 'Weekly review', 'title': 'Week of', 'body': 'What went well',
    'category': 'General',
    'checklist': [{'text': 'read last week', 'done': False},
                  {'text': 'pick three things', 'done': False}]}))
app.show_settings_page()
# update() between the two. It used to be load-bearing: toggle_settings_panel
# unpacked the section that was showing by asking winfo_ismapped(), which Tk
# answers False until it has drawn it, so back to back the previous section
# was skipped and two stacked -- Recently deleted above a nav reading
# Templates, which is what the first version of this shot showed. The app
# asks whether a section has its place now (_is_placed), so back to back is
# safe; scenes 04 and 05 above, which never had this update(), had been
# photographing two stacked sections since their first reference, and were
# accepted five times without anyone seeing it (0.82.233).
app.update()
app.toggle_settings_panel('templates')
app.update()
app._edit_template(app.templates[-1], lambda: None)
"""),
    ("10-highlight-picker", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.open_note_in_tab(app.notes[0])
app.body_text.tag_add('sel', '1.0', '1.10')
app._open_color_swatch_popup('highlight')
"""),
    ("11-text-colour-picker", """
app._dismiss_mini_popup()
app._open_color_swatch_popup('text_color')
"""),
    # Added for 0.76.198. The day-marker popup at its three-marker cap is the
    # only place that release changed on screen, and none of the scenes above
    # contains a popup from the calendar. Seeded to three rather than clicked
    # to three, so the picture is the same every time: the popup works out on
    # build that it is already at the cap.
    # Added for 0.80.198. Three of that release's four changes had nowhere
    # to show: the stored Trash is empty in these scenes so its rows never
    # appear, and the selection bar only exists while notes are ticked.
    ("13-trash-with-rows-ticked", """
app._dismiss_mini_popup()
app.notebook.select(app.TAB_NOTES)
app.trash = [
    {'id': 9001, 'title': 'Notes', 'body': 'the one about the boiler',
     'category': 'General', 'deleted_at': _days_ago(5)},
    {'id': 9002, 'title': 'Notes', 'body': 'the one about the car',
     'category': 'General', 'deleted_at': _days_ago(4)},
    {'id': 9003, 'title': 'Weekend plan', 'body': 'walk, then the market',
     'category': 'General', 'deleted_at': _days_ago(3)},
]
app.show_settings_page()
app.update()
app.toggle_settings_panel('trash')
app.update()
# Pressed rather than set: the offer to restore appears from the tick
# box's own command, and re-opening the panel would rebuild it and clear
# the selection on purpose -- ticks are not meant to survive leaving
# Settings and coming back.
_boxes = []
def _find_ticks(w):
    for c in w.winfo_children():
        if isinstance(c, tk.Checkbutton):
            _boxes.append(c)
        _find_ticks(c)
_find_ticks(app.settings_trash_panel)
if _boxes:
    _boxes[1].invoke()
app.update()
"""),
    ("14-selection-bar-with-pin", """
app.hide_settings_page()
app.trash = []
app.notebook.select(app.TAB_NOTES)
app.update()
if not app.selection_mode:
    app._toggle_selection_mode()
app.selected_note_ids = {n['id'] for n in app.notes[:2]}
app._update_bulk_selected_label()
app.refresh_note_list()
"""),
    # Added for 0.81.199: the focus ring is that release's visible change,
    # and a ring only shows while something actually has the keyboard.
    ("15-note-card-with-keyboard-focus", """
if app.selection_mode:
    app._toggle_selection_mode()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.refresh_note_list()
app.update()
_order = app._card_order()
# Take the desktop foreground back BEFORE placing the focus, not after.
# The ring is drawn by the app when the list's canvas hears <FocusIn>, and
# Tk delivers that only while its toplevel really owns the foreground --
# another process (the terminal; the PowerShell an older shutter ran
# between scenes) can hold the foreground when this scene starts. With the
# card widgets this flaked about one run in three: the reference had the
# ring, the re-take did not, 0.6% apart, and "re-run it until it is green"
# would have hidden exactly that. Seen by opening the two pictures side by
# side.
#
# The order is the whole fix. focus_force() on the window after the list
# had the focus would move the focus OFF the list onto the window and lose
# the ring every time -- the flake would become a certainty.
app.focus_force()
app.update()
if len(_order) > 1:
    app._put_keyboard_on_card(_order[1])
app.update()
app.update_idletasks()
"""),
    ("12-day-markers-at-the-cap", """
if app.selection_mode:
    app._toggle_selection_mode()
app.update()
app._dismiss_mini_popup()
app.notebook.select(app.TAB_CALENDAR)
app.cal_year, app.cal_month = 2026, 9
app.render_calendar()
# update() before opening the popup, and it is load-bearing: select() QUEUES
# <<NotebookTabChanged>>, which the app binds to _dismiss_mini_popup. Opened
# back to back, the popup is created first and the queued event closes it a
# moment later -- the first version of this shot was a calendar with no
# popup on it. Same shape as the settings panel two scenes up.
app.update()
app.day_emoji['2026-09-15'] = [e for e, _c in app.DAY_MARKER_EMOJIS[:3]]
app._mark_day_emoji('2026-09-15')
"""),
    # The shortcuts page had no picture at all, which is part of how it
    # came to be missing a whole group without anyone noticing. Its rows
    # are drawn from SHORTCUT_GROUPS, so this is also the only place the
    # longest group title gets looked at rather than counted.
    ("16-the-shortcuts-page", """
app._dismiss_mini_popup()
app.notebook.select(app.TAB_NOTES)
app.update()
app.show_settings_page()
app.update()
app.toggle_settings_panel('shortcuts')
app.update()
app.update_idletasks()
# Scrolled to the note-list group on purpose. A picture of the top of
# this page would show the same three Ctrl combos it always has and
# would not have caught the missing group -- which is the whole reason
# this scene exists.
app.settings_canvas.yview_moveto(0.62)
app.update()
app.update_idletasks()
"""),
    # A card carrying everything a card can carry. The three labels on a
    # card are the widest thing in a fixed-width sidebar, and nothing was
    # watching what happens when their text outgrows it -- which is how a
    # checklist count came to read "1/" with the total cut off the edge,
    # on an ordinary note, in a picture taken for the documentation.
    ("17-a-note-card-at-its-fullest", """
app._dismiss_mini_popup()
# hide_settings_page() is load-bearing, and was missing: the scene before
# this one leaves the Settings page open, so without it this photographed
# the shortcuts page instead of a note card -- a 21% difference that read
# as "the card scene changed" and would have been accepted as one. A
# scene sets up everything it needs and assumes nothing about the scene
# before it.
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
if app.selection_mode:
    app._toggle_selection_mode()
app.notes = [NO.normalize_note({
    'id': 7100,
    'title': 'Quarterly planning meeting with the whole team',
    'body': ('Agenda, decisions and the follow-ups we owe each other.'
             + chr(10) + '| Item | Owner |' + chr(10) + '| --- | --- |'
             + chr(10) + '| Budget | Ana |'),
    'category': 'General',
    'comments': 'Room 2 is booked',
    'checklist': [{'text': 'send the agenda', 'done': True},
                  {'text': 'book the room', 'done': False}],
    'attachments': [{'name': 'agenda.pdf', 'stored_as': 'agenda.pdf'}],
    'date': '2026-09-15',
    'recurrence': {'freq': 'weekly', 'weekdays': [0]},
})]
app.save_notes()
app.refresh_note_list()
app.update()
app.update_idletasks()
"""),
    # The sibling sweep for the card fix. A trash row draws a title in a
    # panel that reserves width for two buttons, and its sub-line was
    # already wrapped to its own width by an earlier fix -- but the title
    # above it only has a 42-CHARACTER cap, which is not a width: forty
    # two narrow characters fit where forty two wide ones do not. This
    # scene is the measurement that says whether it is a real sibling.
    ("18-a-trash-row-with-a-long-title", """
app._dismiss_mini_popup()
app.notebook.select(app.TAB_NOTES)
if app.selection_mode:
    app._toggle_selection_mode()
app.trash = [
    {'id': 9101,
     'title': 'Quarterly planning meeting with the whole team',
     'body': 'the long one', 'category': 'General',
     'deleted_at': _days_ago(5),
     'recurrence': {'freq': 'weekly', 'weekdays': [0]}},
    {'id': 9102, 'title': 'Short one', 'body': 'b',
     'category': 'General', 'deleted_at': _days_ago(4)},
]
app.show_settings_page()
app.update()
app.toggle_settings_panel('trash')
app.update()
app.update_idletasks()
"""),
    # The Trash when the window chosen before could not be read: a line
    # that says nothing leaves by itself, a selector reading Choose…, and
    # rows with no days left. Last, because the marker stays in settings.
    ("19-trash-window-not-known", """
app._dismiss_mini_popup()
NO.save_setting(NO.TRASH_WINDOW_UNKNOWN, 'told')
app.trash = [
    {'id': 9201, 'title': 'Kept since the summer', 'body': 'b',
     'category': 'General', 'deleted_at': _days_ago(80)},
    {'id': 9202, 'title': 'Deleted last week', 'body': 'b',
     'category': 'General', 'deleted_at': _days_ago(6)},
]
app.show_settings_page()
app.update()
app.toggle_settings_panel('trash')
app.update()
app.update_idletasks()
"""),
    # A table just after "Insert row above" on its header: the new row
    # under the header, the header still drawn as one, no row of dashes.
    # Above it, the separator stopped counting and the header became data.
    ("20-a-row-inserted-under-the-header", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
if app.selection_mode:
    app._toggle_selection_mode()
_tn = NO.normalize_note({
    'id': 7200, 'title': 'Shopping list', 'category': 'General',
    'body': ('| Item | Qty | Shop |' + chr(10) + '| --- | --- | --- |'
             + chr(10) + '| Milk | 2 | corner |'
             + chr(10) + '| Eggs | 12 | market |')})
app.notes.append(_tn)
app.save_notes()
app.refresh_note_list()
app.open_note_in_tab(_tn)
app.update()
app._grid_insert_row(app._grid_at_line(1), 0)
# The row schedules an autosave, whose "Note updated" toast lands in the
# picture or not by timing alone, as in the next scene.
app._cancel_pending_autosave()
app.update()
app._hide_toast()
app.update()
app.update_idletasks()
"""),
    # A sentence made bold that keeps its italic word italic, and a list
    # after Home, then Enter, on its item: an empty item above, never
    # "• • milk". Both used to come out wrong.
    ("21-bold-keeps-italic-and-enter-at-a-marker", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
_tn = NO.normalize_note({
    'id': 7300, 'title': 'Styles and lists', 'category': 'General',
    'body': ('Pack the warm coat today' + chr(10) + '• milk'),
    'formatting': [{'start': 9, 'end': 13, 'style': 'italic'}],
    'paragraphs': [{'line': 1, 'kind': 'bullet'}]})
app.notes.append(_tn)
app.save_notes()
app.refresh_note_list()
app.open_note_in_tab(_tn)
app.update()
app.body_text.tag_add('sel', '1.0', '1.end')
app._toggle_body_style('bold')
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.mark_set('insert', '2.0')
app._on_body_return(None)
# The edits schedule an autosave, whose "Note updated" toast would land in
# the picture or not, by timing alone.
app._cancel_pending_autosave()
app.update()
app._hide_toast()
app.update()
app.update_idletasks()
"""),
    # Settings > About before the app is in the Store: the privacy policy's
    # card, and no Feedback card. The folder line would show this scratch
    # copy's path, which holds a person's name, in a picture kept in the
    # repository, so the label
    # alone is given a neutral one -- where the app writes is untouched.
    ("22-settings-about-privacy", """
app._dismiss_mini_popup()
app.show_settings_page()
app.update()
app.toggle_settings_panel('about')
app.update()
from noteorganizer.core import paths as _sl_paths
_sl_shown = chr(92).join(['C:', 'Users', 'you', 'Note Organizer'])
def _sl_no_names(widget):
    for child in widget.winfo_children():
        if isinstance(child, tk.Label) and str(child.cget('text')) == str(_sl_paths.APP_DIR):
            child.configure(text=_sl_shown)
        _sl_no_names(child)
_sl_no_names(app.settings_about_panel)
app.update()
app.update_idletasks()
"""),
    # The welcome note, opened the way About's Show opens it, scrolled to its
    # privacy section: the first thing a new notebook shows says what the app
    # does with your data, and where the privacy policy is.
    ("23-welcome-note-privacy-section", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.update()
app.show_welcome_note()
app.update()
# The section's last line first, then its heading: the whole of it in view.
_sl_privacy = app.body_text.search('Your privacy', '1.0')
_sl_policy = app.body_text.search('has the whole of it', '1.0')
for _sl_at in (_sl_policy, _sl_privacy):
    if _sl_at:
        app.body_text.see(_sl_at)
# Opening it saved the note scene 21 left edited, and that save's "Note
# updated" would be in the picture or not by timing alone.
app._hide_toast()
app.update()
app.update_idletasks()
"""),
    # The Show dropdown opened from the keyboard, the keyboard one row down:
    # its ring is the thing to look at. The foreground first, as scene 15.
    ("24-a-dropdown-walked-by-the-keyboard", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.update()
app.focus_force()
app.update()
app.filter_menu.focus_set()
app.update()
app.filter_menu.event_generate('<space>')
app.update()
_held = app.focus_get()
if _held is not None:
    _held.event_generate('<Down>')
app.update()
app.update_idletasks()
"""),
    # The emoji picker from the toolbar's button, the keyboard one emoji
    # along: the ring round a coloured chip is the thing to look at.
    ("25-the-emoji-picker-walked-by-the-keyboard", """
app._dismiss_mini_popup()
app.notebook.select(app.TAB_NOTES)
app.open_note_in_tab(app.notes[0])
app.update()
app.focus_force()
app.update()
app.emoji_btn.focus_set()
app.update()
# Pressed as Space presses it, with the keyboard on the button; then the
# keyboard is put on the second emoji, as Right puts it (qa1 walks the keys).
app.emoji_btn.invoke()
app.update()
_cells = app._walk_choices(app._mini_popup)
if len(_cells) > 1:
    _cells[1].focus_force()
app.update()
app.update_idletasks()
"""),
    # The month with the keyboard on it, its ring on the 15th: drawn in the
    # gap round the day, apart from the open day's outline inside it.
    ("26-the-month-walked-by-the-keyboard", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_CALENDAR)
app.update()
app.cal_year, app.cal_month = 2026, 9
app._cal_key_day = '2026-09-15'
app.render_calendar()
app.update()
app.focus_force()
app.update()
app.cal_canvas.focus_set()
app.update()
app.update_idletasks()
"""),
    # The question an attachment of a kind the app does not know asks before
    # it opens (the app's allow list). Photographed while it waits
    # for its answer, in place of the wait; nothing is opened.
    ("27-an-unknown-kind-of-file-asks-first", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.open_note_in_tab(app.notes[0])
app.update()
def _shoot_while_asking(_var):
    app.update()
    app.update_idletasks()
    time.sleep(0.4)
    app.lift()
    app.attributes("-topmost", True)
    app.update()
    time.sleep(0.2)
    _grab_window("27-an-unknown-kind-of-file-asks-first")
app.wait_variable = _shoot_while_asking
try:
    app._open_externally('C:/attachments/20261028090000000000_Holiday plans.zip',
                         'Holiday plans.zip')
finally:
    del app.wait_variable
_scene_took_its_own = True
"""),
    # An attachment's row: a name too long for it gives way before its type,
    # which always shows, and the name is a Tab stop with its ring. No other
    # scene shows an attachment row.
    ("28-an-attachment-row-with-a-long-name", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
# Fixed dates: the editor's foot shows them, and today's would differ each run.
app.new_note()
app.update()
app.notes[0]['created'] = app.notes[0]['updated'] = '2026-09-01 09:00:00'
app.open_note_in_tab(app.notes[0])
app.update()
_long = ('Minutes of the quarterly planning meeting with the whole team, '
         * 3 + 'final.pdf')
app.current_attachments = [
    {'filename': _long, 'stored_as': '20261028090000000000_' + _long},
    {'filename': 'photo.jpg', 'stored_as': '20261028090000000001_photo.jpg'}]
app.refresh_attachments_list()
app.update()
app.update_idletasks()
app.editor_canvas.yview_moveto(1.0)
app.update()
app.focus_force()
app.update()
_names = [w for row in app.attachments_frame.winfo_children()
          for part in row.winfo_children() for w in part.winfo_children()
          if isinstance(w, tk.Label) and 'Minutes' in str(w.cget('text'))]
if _names:
    _names[0].focus_set()
# Opening the note schedules an autosave, and the files set above would be
# saved by it: the toast, and today's stamp under the note, by timing alone.
app._cancel_pending_autosave()
app.update()
app._hide_toast()
app.update()
app.update_idletasks()
"""),
    # A checklist of 1,000 items, every fifth a long one, scrolled to its end:
    # its last items drawn at the bottom of the list, where one frame holding
    # them all stopped some 50,000 px short.
    ("29-a-long-checklist-at-its-end", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.new_note()
app.update()
_long = ('steady ' * 150)[:900]
app._working_checklist = [
    {'text': '%03d %s' % (i, _long if i % 5 == 0 else 'pack item number %d' % i),
     'done': i % 3 == 0} for i in range(1000)]
if app._checklist_open:
    app._render_checklist_items()
else:
    app.toggle_checklist_section()
app._cancel_pending_autosave()
app.update()
app.update_idletasks()
app._bring_into_sight(app.checklist_expand_btn)
app._checklist_canvas.yview_moveto(1.0)
app.update()
app._hide_toast()
app.update()
app.update_idletasks()
"""),
    # The picker with the 1,000 templates a notebook may hold, scrolled to
    # the last of them.
    ("30-the-template-picker-at-its-last", """
app._dismiss_mini_popup()
app._working_checklist = []
app._render_checklist_items()
app.templates = [NO.normalize_template({'name': 'Template %04d' % i, 'body': 'x'})
                 for i in range(1000)]
app.show_template_picker()
app.update()
app.update_idletasks()
_views = [w for w in app._mini_popup.winfo_children()]
while _views and getattr(_views[0], '_row_stack', None) is None:
    _views = _views[1:] + list(_views[0].winfo_children())
if _views:
    _views[0].yview_moveto(1.0)
app.update()
app.update_idletasks()
"""),
    # The template editor, opened from Settings, saying under its heading that
    # a paste into its name was shortened: the status line that said it stands
    # hidden behind Settings.
    ("31-the-template-editor-says-a-paste-was-shortened", """
app._dismiss_mini_popup()
app.templates = []
app.show_settings_page()
app.toggle_settings_panel('templates')
app.update()
app._edit_template(None, lambda: None)
app.update()
app.update_idletasks()
_boxes = []
def _entries(w):
    for c in w.winfo_children():
        if isinstance(c, tk.Entry):
            _boxes.append(c)
        _entries(c)
_entries(app._mini_popup)
_real_read = NO.clipboard.read_text
NO.clipboard.read_text = lambda: 'Weekly review ' * 25
try:
    _boxes[0].delete(0, 'end')
    _boxes[0].event_generate('<<Paste>>')
finally:
    NO.clipboard.read_text = _real_read
app.update()
app.update_idletasks()
"""),
    # A checklist of sixteen items of 100 lines, at its top: item 00 is what is
    # drawn there. Chunks taller than their parking place hung over the top of
    # such a list at 150-300%.
    ("32-a-checklist-of-long-items-at-its-top", """
app._dismiss_mini_popup()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.new_note()
app.update()
_tall = '\\n'.join('line %d of a long item' % k for k in range(100))
app._working_checklist = [{'text': '%02d %s' % (i, _tall), 'done': False}
                          for i in range(16)]
if app._checklist_open:
    app._render_checklist_items()
else:
    app.toggle_checklist_section()
app._cancel_pending_autosave()
app.update()
app.update_idletasks()
app._bring_into_sight(app.checklist_expand_btn)
app._checklist_canvas.yview_moveto(0)
app.update()
app._hide_toast()
app.update()
app.update_idletasks()
"""),
    # The Insert table grid, the keyboard on the second row's third square:
    # the squares lit are the table it makes, 2 x 3. Drawn from its second
    # column, it lit one square fewer than the caption said.
    ("33-the-table-grid-lights-the-table-it-makes", """
app._dismiss_mini_popup()
app._working_checklist = []
app._render_checklist_items()
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.open_note_in_tab(app.notes[1])
app.update()
app._cancel_pending_autosave()
app.focus_force()
app.update()
app._open_table_size_popup()
app.update()
_cells = app._walk_choices(app._mini_popup)
if len(_cells) > 10:
    _cells[10].focus_force()
app.update()
app._hide_toast()
app.update()
app.update_idletasks()
"""),
]

SEED = [
    # English, like the app's own interface, and with real line breaks.
    # Both were wrong: the notes were Romanian, and each body held a
    # backslash followed by an n rather than the newline it stood for --
    # so a note meant to be three lines was drawn across one, with the
    # backslashes showing.
    # The language gate did not catch the first, because none of those
    # words are in its list. It is a net, not a proof, and says so.
    {"id": 1, "title": "Bread recipe",
     "body": "500g flour\n300ml water\n10g salt",
     "category": "General", "date": "2026-09-15",
     "checklist": [{"text": "kneaded", "done": True},
                   {"text": "baked", "done": False}],
     "created": "2026-09-01 09:00", "updated": "2026-09-01 09:00"},
    {"id": 2, "title": "Shopping", "body": "milk\neggs\nbread",
     "category": "General", "created": "2026-09-02 09:00",
     "updated": "2026-09-02 09:00"},
    {"id": 3, "title": "", "body": "a note with no title, as in a real notebook",
     "category": "General", "created": "2026-09-03 09:00",
     "updated": "2026-09-03 09:00"},
]

SHOOTER = '''
import io, json, os, subprocess, sys, time
sys.path.insert(0, ".")
import note_organizer as NO, tkinter as tk
from _qa_support import pin_popup_visibility, photograph
pin_popup_visibility(NO)

app = NO.NoteOrganizer()
app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.ask_yes_no = lambda *a, **k: True
app.geometry("1150x820+60+60")
app.update()
# Raised and kept on top before anything is photographed. The grab copies
# from the SCREEN at the window's coordinates, so whatever is in front is
# what gets saved -- and these pictures are committed.
app.lift()
app.attributes("-topmost", True)
app.focus_force()

# The reminder bar is packed on demand when a note is due TODAY, and the
# seed carries a fixed date -- so on one day a year these pictures grow a
# purple band across the top and every reference taken that day is
# unusable on every other day. It is not a small difference either: the
# window does not simply shift, it REFLOWS, because the 47px the bar
# occupies are absorbed by the note list rather than pushed down. That is
# how the stored screens came to report 20% changed with nothing wrong.
# Kept off deliberately, so what these pictures show does not depend on
# the calendar. The bar itself is not what this tool is for.
def _no_reminder():
    try:
        app.reminder_bar.pack_forget()
    except Exception:
        pass
app.after(500, _no_reminder)
app.after(900, _no_reminder)

# Trash rows dated a few days before today, whatever day this runs: the
# panel counts "days left" from today, so a fixed date drifted in every
# picture, on its way to "0 day(s) left".
import datetime as _dt
def _days_ago(days):
    day = _dt.date.today() - _dt.timedelta(days=days)
    return day.isoformat() + " 09:00:00"

# The one shutter (_qa_support.photograph): the window's box, cut to the
# primary screen's work area, in the screen's own pixels, and no picture at
# all when another program's window lies over it -- these are committed.
def _grab_window(name):
    taken, why = photograph(app, os.path.join("shots", name + ".png"))
    if not taken:
        print("NOT TAKEN %s: %s" % (name, why), flush=True)

scenes = json.load(io.open("scenes.json", encoding="utf-8"))
for name, script in scenes:
    # A scene whose subject is a question photographs it itself, while the
    # question waits: once answered, it is gone (scene 27).
    _scene_took_its_own = False
    exec(script)
    if _scene_took_its_own:
        continue
    _no_reminder()          # belt and braces; see the note above
    app.update()
    app.update_idletasks()
    time.sleep(0.4)
    app.lift()
    app.attributes("-topmost", True)
    # A scene whose subject is a POPUP would otherwise be photographed with
    # the popup behind the window that owns it: the lift above raises the
    # app, and an anchored Toplevel is a separate window. So whatever popup
    # the scene opened is raised after the app, not before. Harmless when
    # there is none, which is the other five scenes.
    _pop = getattr(app, "_mini_popup", None)
    if _pop is not None:
        try:
            if _pop.winfo_exists():
                _pop.lift()
                _pop.attributes("-topmost", True)
        except tk.TclError:
            pass
    app.update()
    app.update_idletasks()
    time.sleep(0.2)
    _grab_window(name)
app.destroy()
'''

# How long the whole set of scenes may take: about two minutes when it works.
SHOOT_TIMEOUT = 600


def take_the_pictures(work):
    """Run the app in a scratch copy and photograph each scene; returns what
    the shooter printed, or None when it did not finish in time."""
    os.makedirs(os.path.join(work, "shots"))
    shutil.copy2(os.path.join(ROOT, "note_organizer.py"), work)
    shutil.copytree(os.path.join(ROOT, "noteorganizer"),
                    os.path.join(work, "noteorganizer"))
    shutil.copy2(os.path.join(HERE, "_qa_support.py"), work)
    io.open(os.path.join(work, "notes_data.json"), "w", encoding="utf-8").write(
        json.dumps(SEED))
    io.open(os.path.join(work, "settings.json"), "w", encoding="utf-8").write(
        json.dumps({"cleanup_done": True, "reclaimed_from_appdata": True,
                    "theme": "dark"}))
    io.open(os.path.join(work, "scenes.json"), "w", encoding="utf-8").write(
        json.dumps(SCENES))
    io.open(os.path.join(work, "shoot.py"), "w", encoding="utf-8").write(SHOOTER)
    try:
        run = subprocess.run([sys.executable, "shoot.py"], cwd=work,
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=SHOOT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None
    return (run.stdout or "") + (run.stderr or "")


# Below this share of the picture, a difference is rendering noise
# rather than a change of shape. One definition, because the report and
# --accept must not disagree about which screens changed.
SAME_ENOUGH = 0.5


def compare(new_dir):
    """How much of each picture changed, as a percentage of its pixels.

    Deliberately coarse: images are reduced to a small grid and compared
    cell by cell, so a pixel of text rendering does not read as a
    change while a moved control does.

    The threshold lives in SAME_ENOUGH, in one place, because both the
    report and --accept have to mean the same thing by "changed".
    """
    try:
        from PIL import Image
    except ImportError:
        print("Pillow is missing -- I cannot compare the pictures.")
        return None
    results = []
    for name, _script in SCENES:
        fresh = os.path.join(new_dir, name + ".png")
        stored = os.path.join(STORE, name + ".png")
        if not os.path.exists(fresh):
            results.append((name, None, "the picture was not taken"))
            continue
        if not os.path.exists(stored):
            results.append((name, None, "there is no reference picture"))
            continue
        a = Image.open(stored).convert("L").resize((160, 120))
        b = Image.open(fresh).convert("L").resize((160, 120))
        if a.size != b.size:
            results.append((name, 100.0, "a different size"))
            continue
        pa, pb = a.load(), b.load()
        moved = sum(1 for y in range(120) for x in range(160)
                    if abs(pa[x, y] - pb[x, y]) > 12)
        results.append((name, moved * 100.0 / (160 * 120), ""))
    return results


def main():
    accept = "--accept" in sys.argv
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import guest  # this machine's turn and the memory ceiling (tools/guest.py)
    for line in guest.settle(label="story_look" + (" --accept" if accept else "")):
        print(line)
    # Marked as this run's, and removed on every way out: by this run, or by
    # the next one if this one is killed.
    work = guest.scratch("look-")
    kept = False
    try:
        code, kept = _look(work, accept)
        return code
    finally:
        if kept:
            # The changed pictures stay to be looked at; the app's copy goes,
            # and a later run removes the rest after guest.KEPT_DAYS.
            for name in os.listdir(work):
                path = os.path.join(work, name)
                if name in ("shots", guest.MARKER):
                    continue
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
            guest.keep(work, "story_look: screens that changed")
        else:
            guest.remove(work)


def _look(work, accept):
    """Take the pictures and judge them: (exit code, keep the pictures)."""
    said = take_the_pictures(work)
    if said is None:
        print("HANG: the scenes did not finish within %d s." % SHOOT_TIMEOUT)
        return 2, False
    # A picture the shutter refused is said, with why: something that is not
    # the app was over the window, and it is never accepted into qa/screens.
    for line in said.splitlines():
        if line.startswith("NOT TAKEN "):
            print(line)
    shots = os.path.join(work, "shots")
    taken = sorted(os.listdir(shots)) if os.path.isdir(shots) else []
    if not taken:
        print("NO PICTURES. Either the app did not start or the shutter refused them all.")
        print(said[-800:])
        return 2, False

    if accept:
        # Blessed by the SAME judgement the report prints, so "accepted"
        # and "CHANGED" can never disagree -- and, more to the point, so
        # that a screen the tool calls unchanged is left alone on disk.
        # This used to copy every picture it had just taken. A PNG
        # re-encoded from identical pixels is a different FILE, so
        # accepting one new scene rewrote all sixteen and put fifteen
        # binary blobs into a commit about something else. Comparing the
        # bytes instead would not fix it, for the same reason.
        results = compare(shots)
        if results is None:
            return 2, False
        if not os.path.isdir(STORE):
            os.makedirs(STORE)
        blessed, left = [], []
        for name, pct, _note in results:
            fresh = os.path.join(shots, name + ".png")
            if pct is not None and pct < SAME_ENOUGH:
                left.append(name)
                continue
            if not os.path.exists(fresh):
                continue
            shutil.copy2(fresh, os.path.join(STORE, name + ".png"))
            blessed.append(name)
        if blessed:
            print("accepted %d screen(s):" % len(blessed))
            for name in blessed:
                print("    %s" % name)
        else:
            print("nothing to accept -- no screen has changed its shape.")
        if left:
            print("left alone: %d unchanged picture(s)." % len(left))
        return 0, False

    results = compare(shots)
    if results is None:
        return 2, False

    changed = []
    for name, pct, note in results:
        if pct is None:
            print("  ?     %-22s %s" % (name, note))
            changed.append(name)
        elif pct < SAME_ENOUGH:
            print("  same    %-22s (%.1f%%)" % (name, pct))
        else:
            print("  CHANGED %-16s %.1f%% of the screen %s" % (name, pct, note))
            changed.append(name)

    print()
    if changed:
        print("SCREENS CHANGED: %s" % ", ".join(changed))
        print("The new pictures are in: %s" % shots)
        print("If the change was wanted, accept it with:  py qa/story_look.py --accept")
        return 1, True
    print("No screen has changed its shape.")
    return 0, False


if __name__ == "__main__":
    sys.exit(main())
