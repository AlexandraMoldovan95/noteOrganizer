"""Retake the documentation screenshots, from the real app.

WHY THIS EXISTS
---------------
The screenshots in ``docs/screenshots/`` are part of the documentation,
and they go stale silently: a control is added, an option is renamed, and
the picture keeps showing the old app with nothing to say so. The 2026-09-11
audit found three shots picturing controls that no longer exist --
a calendar without its History button, a sort list still offering
"Date (soonest)", an editor missing the banner a repeating note now
carries. Nobody had looked since the shots were taken.

So the staging lives in code, next to the app, and a retake is a command
rather than an afternoon of clicking. Each scene below stages a note or a
panel deliberately, so the picture shows the app doing something real
rather than whatever a dev notebook happened to hold.

RUNNING IT (the qa safety rule applies -- NEVER in place)
---------------------------------------------------------
Copy ``note_organizer.py``, the ``noteorganizer/`` package, this script,
``tools/guest.py`` and ``qa/_qa_support.py`` into a scratch folder outside
the project tree, then::

    py doc_screenshots.py                 # every scene
    py doc_screenshots.py calendar-view   # just one

PNGs land in ``./shots``; copy the ones you want into
``docs/screenshots/``. Windows only, like ``visual_scenes.py``, for the
same reason: ImageGrab needs real win32 windows. guest.py gives the run
its turn and its memory ceiling before the app is built; _qa_support's
shutter takes every picture (a picture holds only the app's pixels).
"""

# THE TURN, THE CEILING AND THE SEED FIRST -- this builds the whole app, on the
# screen. seed_here settles as a guest (tools/guest.py, beside _qa_support),
# then seeds an empty notebook here: only where the app will open it, asked of
# its own resolver, and never beside notes (the qa scripts' guard).
import os as _guest_os, sys as _guest_sys
_guest_sys.path.insert(0, _guest_os.path.dirname(_guest_os.path.abspath(__file__)))
try:
    from _qa_support import grab, photograph, seed_here
except ImportError as _missing:
    _guest_sys.exit('REFUSING to run: %s. Copy tools/guest.py and qa/_qa_support.py '
                    'beside this script (see its docstring).' % _missing)
seed_here()

import datetime
import os
import sys
import time

import tkinter as tk

import note_organizer as NO

OUT = os.path.join(os.getcwd(), 'shots')
os.makedirs(OUT, exist_ok=True)

# The app hides its -topmost popups whenever another program holds the
# Windows foreground, on a 300ms heartbeat -- and a scripted run never
# holds it, so a dropdown opened here would be photographed closed. The
# qa suite pins the same answer for the same reason (_qa_support's
# pin_popup_visibility); this is that patch, applied before the app is
# built so the heartbeat never sees the real answer.
_pinned = False
if hasattr(NO.NoteOrganizer, '_foreground_is_ours'):
    NO.NoteOrganizer._foreground_is_ours = lambda self: True
    _pinned = True
# The guard was renamed. The line above kept its old name and quietly
# stopped doing anything -- a patch that no longer patches, which is why
# the emoji picker photographed as an empty editor. The heartbeat that
# actually hides popups is _popup_watch_step; silencing it is what pins
# them open for a scripted run.
if hasattr(NO.NoteOrganizer, '_popup_watch_step'):
    NO.NoteOrganizer._popup_watch_step = lambda self: None
    _pinned = True
if not _pinned:
    print('WARNING: no popup guard found -- popups may close while shooting')
# The window's resize freeze asks Windows whether the mouse button is down,
# anywhere on the desktop, and lays nothing out while it is: a click held in
# another program during a run would photograph a page not laid out yet.
# The qa suite pins the same answer (_qa_support's pin_the_desktop).
if hasattr(NO.NoteOrganizer, '_pointer_button_held'):
    NO.NoteOrganizer._pointer_button_held = lambda self: False

app = NO.NoteOrganizer()
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
# Positioned, not just sized: ImageGrab reads the SCREEN, so a window
# hanging off the right edge is saved with its right edge missing -- the
# first retake lost the calendar's whole History button that way. Sized
# to fit the screen it is actually running on.
_sw, _sh = app.winfo_screenwidth(), app.winfo_screenheight()
WIN_W, WIN_H = min(1300, _sw - 60), min(960, _sh - 100)
app.geometry('%dx%d+20+20' % (WIN_W, WIN_H))
app.update()
# ImageGrab photographs the SCREEN at the window's coordinates, not the
# window -- so anything sitting on top is what gets saved. Without this,
# a retake captured a browser window that happened to be in front, which
# is both a useless screenshot and someone's private screen in a file
# headed for a public repo. Raised and kept on top, like visual_scenes.
app.lift()
app.attributes('-topmost', True)


def pump(n=8, sleep=0.03):
    for _ in range(n):
        app.update()
        app.update_idletasks()
        time.sleep(sleep)


# ---- Nothing of anybody's screen ends up in these files -------------
#
# A picture copies the SCREEN at the window's coordinates, not the window.
# Raising ours and setting -topmost is necessary and NOT sufficient: another
# always-on-top window wins anyway, and on the first full run an Android
# emulator sat in the middle of nineteen pictures. A browser did it once
# before that. So every picture goes through the one shutter
# (_qa_support.grab/photograph): the box cut to the window and the primary
# screen's work area, points across it asked WHICH window is on top there
# before and after the copy, and no picture -- said -- when one is another
# program's. It also measures the screen's scale for itself.


def _top_of_cut_row(edge):
    """The top of the highest line of text or button that `edge` cuts.

    Containers, canvases and scrollbars are left out: they run to the
    window's edge by design, and their contents are what gets cut.
    """
    tops = []
    for w in _all_widgets(app):
        try:
            if (w.winfo_toplevel() is not app or not w.winfo_ismapped()
                    or w.winfo_class() in ('Canvas', 'Scrollbar',
                                           'TScrollbar')):
                continue
            top, height = w.winfo_rooty(), w.winfo_height()
        except tk.TclError:
            continue
        if height <= 60 and top < edge < top + height:
            tops.append(top)
    return min(tops) if tops else None


def _box_of(widgets, pad=0):
    """The screen box, in Tk's logical pixels, that holds every widget."""
    xs, ys, xe, ye = [], [], [], []
    for w in widgets:
        xs.append(w.winfo_rootx())
        ys.append(w.winfo_rooty())
        xe.append(w.winfo_rootx() + w.winfo_width())
        ye.append(w.winfo_rooty() + w.winfo_height())
    return (min(xs) - pad, min(ys) - pad, max(xe) + pad, max(ye) + pad)


def _fit(box, aspect):
    """`box` grown -- never cut -- to the shape `aspect` (width / height),
    evenly on both sides, then slid back inside the window where it ran
    past an edge. The website's cards show a picture at 16:10, cropping
    the rest: a picture already that shape loses nothing of its subject."""
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    if width / float(height) < aspect:
        grow = height * aspect - width
        left, right = left - grow / 2, right + grow / 2
    else:
        grow = width / aspect - height
        top, bottom = top - grow / 2, bottom + grow / 2
    frame = (app.winfo_rootx(), app.winfo_rooty(),
             app.winfo_rootx() + app.winfo_width(), app.winfo_rooty() + app.winfo_height())
    for lo, hi, flo, fhi in ((0, 2, 0, 2), (1, 3, 1, 3)):
        edges = [left, top, right, bottom]
        if edges[lo] < frame[flo]:
            shift = frame[flo] - edges[lo]
            edges[lo] += shift
            edges[hi] += shift
        if edges[hi] > frame[fhi]:
            shift = edges[hi] - frame[fhi]
            edges[lo] -= shift
            edges[hi] -= shift
        left, top, right, bottom = edges
    return tuple(int(round(v)) for v in (left, top, right, bottom))


def _cut(box, aspect):
    """`box` cut to the shape `aspect`, keeping its top-left corner: for a
    subject that starts at the top and runs on further than a card shows."""
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    if width / float(height) < aspect:
        bottom = top + width / aspect
    else:
        right = left + height * aspect
    return tuple(int(round(v)) for v in (left, top, right, bottom))


def _widgets_with_text(*texts):
    """The mapped widgets of the main window whose text is one of `texts`,
    for a panel that keeps no handle on the rows or tiles it draws."""
    found = []
    for w in _all_widgets(app):
        try:
            if w.winfo_ismapped() and w.cget('text') in texts:
                found.append(w)
        except tk.TclError:
            continue
    return found


def capture(name, widgets=None, pad=8, box=None):
    """Save the whole window, the box that holds `widgets`, or `box` --
    left, top, right, bottom on the screen, in Tk's logical pixels."""
    app.lift()
    app.attributes('-topmost', True)
    app.focus_force()
    # The keyboard on the window's own canvas, which shows nothing for it:
    # landing in the search box, it would clear the box's hint (<FocusIn>).
    app.main_canvas.focus_set()
    # ...and then our own popups back above it. Raising the main window
    # raises it above its OWN children too, so the emoji picker was being
    # photographed from underneath: present, mapped, inside the frame, and
    # covered by the very window the shot is of.
    for child in app.winfo_children():
        if isinstance(child, tk.Toplevel):
            try:
                if child.winfo_ismapped():
                    child.lift()
            except tk.TclError:
                pass
    pump(10)
    if widgets or box:
        if widgets:
            box = _box_of(widgets, pad)
        # Clamped to the window. A crop that reaches past the edge
        # photographs whatever is behind the app -- the checklist shot
        # came back with the Windows taskbar along its bottom, and the
        # occlusion guard missed it because a 40px strip falls between
        # sample points. A picture of this app can only be made of pixels
        # belonging to this app.
        frame = (app.winfo_rootx(), app.winfo_rooty(),
                 app.winfo_rootx() + app.winfo_width(),
                 app.winfo_rooty() + app.winfo_height())
        box = (max(box[0], frame[0]), max(box[1], frame[1]),
               min(box[2], frame[2]), min(box[3], frame[3]))
    else:
        box = (app.winfo_rootx(), app.winfo_rooty(),
               app.winfo_rootx() + app.winfo_width(),
               app.winfo_rooty() + app.winfo_height())
        # A line the window's bottom edge runs through reads as a picture
        # cut short: the hero shot ended in half of the editor's "Created
        # ... Last updated" line. The picture ends above it instead.
        cut = _top_of_cut_row(box[3])
        if cut is not None:
            box = (box[0], box[1], box[2], cut - 2)
    taken, size = photograph(app, os.path.join(OUT, name + '.png'), box=box)
    if not taken:
        print('  %-22s NOT TAKEN: %s' % (name, size))
        return
    print('  %-22s %dx%d' % (name, size[0], size[1]))


def clean():
    """Put the app back to a fresh start, not merely to an empty notebook.

    Two runs were lost to what this did NOT reset. A scene ending on the
    Calendar left nineteen pictures of a month view, one of them filed as
    "main-window". And a scene that typed "team" into the search box left
    every later sidebar reading "No notes match your search or filter" --
    including the hero shot.

    Each is a screen-state leak between scenes, so the answer is to
    return the SCREEN to its start, not just the data.
    """
    app.notes = []
    app.trash = []
    app.templates = []
    app.current_attachments = []
    NO.save_templates([])
    app.save_notes()
    # A painted day outlives its scene: every later picture of that month
    # (the README's moving picture is one) would show it orange.
    app.day_colors, app.day_emoji = {}, {}
    app._persist_day_colors()
    app._persist_day_emoji()

    try:
        app.hide_settings_page()
    except Exception:
        pass
    for panel_toggle, panel_attr in (('toggle_share_panel', 'share_panel'),
                                     ('toggle_import_panel', 'import_panel')):
        panel = getattr(app, panel_attr, None)
        toggle = getattr(app, panel_toggle, None)
        if panel is not None and toggle is not None and panel.winfo_ismapped():
            toggle()

    # The box as the app opens it: its hint written in, in the hint's colour.
    # Merely emptied, it waits for a <FocusOut> to put the hint back, and
    # every sidebar was photographed with an empty, unlabelled box.
    app.search_entry.show_hint()
    app.sort_var.set(app.SORT_OPTIONS[0])
    app.filter_var.set('All')
    if app.group_by_category.get():
        app.group_by_category.set(False)
        app._on_toggle_group_by_category()

    try:
        app.notebook.select(app.TAB_NOTES)
    except Exception:
        pass
    app.open_blank_tab()
    app.refresh_note_list()
    pump(6)


SCENES = []


def scene(name):
    def deco(fn):
        SCENES.append((name, fn))
        return fn
    return deco


def _note(**fields):
    base = {'title': '', 'body': '', 'category': 'General',
            'created': '2026-09-01 09:00', 'updated': '2026-09-11 09:00'}
    base.update(fields)
    if 'id' not in base:
        base['id'] = max([n['id'] for n in app.notes], default=0) + 1
    return NO.normalize_note(base)


def _days_ago(days, at='09:00'):
    """A timestamp `days` before today, in the app's own shape.

    Statistics' "this week" and the Trash's "days left" count from today,
    so a fixed date ages inside the picture: a trash row staged on
    2 September read "0 day(s) left" a month later.
    """
    day = datetime.date.today() - datetime.timedelta(days=days)
    return '%s %s' % (day.isoformat(), at)


def _open_day(day):
    """The calendar on the month `day` is in, with that day open.

    The calendar opens at today's month and these scenes stage fixed
    dates: once September was over, the September day opened under an
    October grid, and the painted day was not on screen at all.
    """
    app.notebook.select(app.TAB_CALENDAR)
    pump(10)
    app.cal_year, app.cal_month = int(day[:4]), int(day[5:7])
    app.render_calendar()
    pump(14)
    app.open_day_popup(day)
    pump(14)
    # The day opens below the month and, on purpose, does not scroll
    # itself into view: a person scrolls down to it, and so does this.
    app.cal_scroll_canvas.yview_moveto(1.0)
    pump(10)


def _scroll_editor_to(widget, pad=12):
    """Scroll the editor until `widget` ends inside the window.

    A crop is clamped to the window, so a section running past its
    bottom edge lost its last row: the checklist's Add button.
    """
    pump(4)
    edge = app.winfo_rooty() + app.winfo_height()
    overflow = widget.winfo_rooty() + widget.winfo_height() + pad - edge
    region = app.editor_canvas.bbox('all')
    if overflow > 0 and region:
        top = app.editor_canvas.yview()[0]
        app.editor_canvas.yview_moveto(
            top + overflow / float(region[3] - region[1]))
        pump(8)


def _weekly_note():
    """A repeating note, the shape the editor screenshot is about.

    Built as data and loaded, rather than driven through the recurrence
    form: the picture is of the editor holding a repeating note, and
    clicking the form to get there adds nothing to it.
    """
    note = _note(
        title='Team stand-up',
        body='What we shipped, what is stuck, what is next.',
        category='Work',
        date='2026-09-14',
        recurrence={'freq': 'weekly', 'interval': 1, 'weekdays': [0]},
        checklist=[{'text': 'Collect blockers before the call', 'done': True},
                   {'text': 'Write up the decisions', 'done': False}],
        comments='Room 2 is booked for the whole quarter.')
    app.notes.append(note)
    app.save_notes()
    app.refresh_note_list()
    app.open_note_in_tab(note)
    pump(12)
    return note


@scene('note-editor')
def note_editor():
    """A repeating note open in the editor.

    Stale since 0.69.108: a repeating note now carries a banner saying
    edits reach every day, and the old shot has no banner at all.
    """
    _weekly_note()
    # The banner is the reason this shot needed retaking, so it has to be
    # IN it: cropping from the title row down starts one row too low.
    frame = [app.title_entry, app.comments_text]
    banner = getattr(app, 'occurrence_banner', None)
    if banner is not None and banner.winfo_ismapped():
        frame.append(banner)
    capture('note-editor', widgets=frame, pad=14)


@scene('search-and-sort')
def search_and_sort():
    """The sidebar, searching, with the sort list open.

    Stale since 0.69.108: the list in the old shot ends at
    "Date (soonest)", a name that no longer exists, and is missing the
    seventh option entirely.
    """
    # Three matches -- in a title and in a body -- with dates, so the
    # search narrows a real list and the sort visibly orders it; one match
    # read to reviewers as a picture of an open note, not of a search.
    for title, body, cat, date in (
            ('Quarterly review', "Numbers for the board pack, the team's targets.",
             'Work', '2026-09-30'),
            ('Team lunch', 'Friday at the Italian place, booked for six.',
             'Personal', '2026-09-25'),
            ('Reading list', 'Three books before the holidays.', 'Personal', ''),
            ('Groceries', 'Everything for the weekend.', 'Personal', '')):
        app.notes.append(_note(title=title, body=body, category=cat, date=date))
    _weekly_note()
    app.search_var.set('team')
    app.refresh_note_list()
    pump()
    # The open dropdown is deliberately NOT staged. Its popup is a
    # -topmost Toplevel and the app's foreground guard is only half the
    # story: a scripted run also never owns the pointer, so the list
    # photographs closed however it is opened. Showing the sort control
    # SET to one of the options carries the same information the old shot
    # carried -- the names -- and this one at least shows names that
    # exist. "Calendar: oldest" is the option the old screenshot predates
    # entirely.
    app.sort_var.set('Calendar: oldest')
    app.refresh_note_list()
    pump(14)
    capture('search-and-sort')


def _september():
    """The month both calendar pictures show: a weekly note and three more.

    One short title per day: every week is as tall as its fullest day,
    and two notes on one day, or a title on two lines, made the month too
    tall to share the window with the open day.
    """
    app.notes.append(_note(
        title='Stand-up', category='Work', date='2026-09-07',
        recurrence={'freq': 'weekly', 'interval': 1, 'weekdays': [0]}))
    for title, category, day in (('Dentist', 'Personal', '2026-09-16'),
                                 ('Bike service', 'General', '2026-09-18'),
                                 ('Board review', 'Work', '2026-09-24')):
        app.notes.append(_note(title=title, category=category, date=day))
    app.save_notes()


@scene('calendar-view')
def calendar_view():
    """The calendar: a repeating note, notes on other days, one day open.

    Stale since 0.71.111: the calendar gained a History button, which the
    old shot predates.
    """
    _september()
    _open_day('2026-09-14')
    capture('calendar-view')


# ---------------------------------------------------------------------
# The rest of the gallery, added 2026-09-14.
#
# Until now this staged three scenes -- the three the 2026-09-11 audit
# found stale -- and the other nineteen pictures were still the ones
# taken by hand, on a real notebook. That showed: a sidebar counting
# "General (71)", notes titled "3" and "5", a Duplicates panel announcing
# thirty-three groups. Nothing private was legible, but nothing was
# chosen either, and a gallery half staged and half photographed goes
# stale exactly as quietly as it did before.
#
# So every picture in docs/screenshots/ now comes from here, from a
# notebook written for the camera.
# ---------------------------------------------------------------------

def _demo_notebook():
    """The notebook the pictures are taken on.

    Four notes across the three default categories: enough for a sidebar
    that looks like somebody's, short enough to read at screenshot size.
    """
    made = []
    for title, body, cat, extra in (
            # NOT the meal plan: that title belongs to _table_note(), and
            # a sidebar showing it twice reads as a bug in the picture.
            ('Bike service', 'Book it before the weekend ride.',
             'General', {'date': '2026-09-18'}),
            ('Quarterly review', 'Numbers for the board pack.', 'Work', {}),
            ('Reading list', 'Three books before the holidays.',
             'Personal', {}),
            ('Shopping list', 'Milk, bread, coffee, olive oil.',
             'General', {}),
    ):
        note = _note(title=title, body=body, category=cat, **extra)
        app.notes.append(note)
        made.append(note)
    app.save_notes()
    app.refresh_note_list()
    pump()
    return made


def _table_note(open_it=True):
    """A note holding a table, which is how several pictures need one."""
    note = _note(
        title='Weekly meal plan',
        body=('Shopping on Sunday; batch-cook the soup.\n\n'
              '| Day | Lunch | Dinner |\n'
              '| --- | --- | --- |\n'
              '| Monday | Soup | Pasta |\n'
              '| Tuesday | Salad | Tacos |\n'
              '| Wednesday | Leftovers | Grilled fish |\n'
              '| Thursday | Wraps | Stir-fry |\n'),
        category='General', date='2026-09-20')
    app.notes.append(note)
    app.save_notes()
    app.refresh_note_list()
    if open_it:
        # A person's route, as every scene here: load_note alone skips the
        # card's open-note ring, and the README showed the note unmarked.
        app.open_note_in_tab(note)
        pump(14)
    return note


def _editor_box(*names):
    """The widgets to crop around, skipping any this build does not have.

    A scene that names a widget which has been renamed should lose its
    crop, not the whole picture -- and say nothing, because the fallback
    is the full window, which is still a true photograph.
    """
    found = []
    for name in names:
        widget = getattr(app, name, None)
        if widget is not None and widget.winfo_ismapped():
            found.append(widget)
    return found or None


@scene('main-window')
def main_window():
    """The hero: the sidebar, a note open with a table, the toolbar."""
    _demo_notebook()
    _table_note()
    capture('main-window')


@scene('main-window-light')
def main_window_light():
    """The hero's window on a light theme, for the guide's Appearance: the
    stills showed the main screen in the dark default only."""
    _demo_notebook()
    _table_note()
    was = app.theme_name
    app.set_theme('light')
    pump(10)
    capture('main-window-light')
    app.set_theme(was)
    pump()


@scene('no-match')
def no_match():
    """The note list when nothing matches the search: what the list says
    instead of going blank."""
    _demo_notebook()
    app.search_var.set('passport')
    app.refresh_note_list()
    pump(10)
    capture('no-match')
    app.search_var.set('')
    app.refresh_note_list()
    pump()


@scene('grouped-notes')
def grouped_notes():
    """The sidebar with Group by category on, showing real groups."""
    _demo_notebook()
    app.group_by_category.set(True)
    app._on_toggle_group_by_category()
    pump(16)
    capture('grouped-notes')
    app.group_by_category.set(False)
    app._on_toggle_group_by_category()
    pump()


@scene('tables')
def tables():
    """A table in a note: header row, aligned columns, the caption."""
    _table_note()
    # Cut at the text box's own top: the format bar sits closer than the
    # margin above it, and a strip of its buttons came into the picture.
    widgets = _editor_box('body_text')
    box = None
    if widgets:
        left, _top, right, bottom = _box_of(widgets, 12)
        box = (left, min(w.winfo_rooty() for w in widgets), right, bottom)
    capture('tables', box=box)


@scene('checklist')
def checklist():
    """The checklist open beside the calculator, part ticked."""
    note = _note(
        title='Trip packing',
        body='The flight leaves early; nothing left for the morning.',
        checklist=[{'text': 'Passports', 'done': True},
                   {'text': 'Charger and adapter', 'done': True},
                   {'text': 'Print the booking', 'done': False},
                   {'text': 'Stop the milk', 'done': False}])
    app.notes.append(note)
    app.save_notes()
    app.refresh_note_list()
    app.open_note_in_tab(note)
    pump(10)
    if not app.checklist_section.winfo_ismapped():
        app.toggle_checklist_section()
    pump(16)
    _scroll_editor_to(app.checklist_section)
    capture('checklist',
            widgets=_editor_box('checklist_btn', 'checklist_section',
                                'calculator_btn'), pad=12)


@scene('calculator')
def calculator():
    """The calculator open, with a result and a history behind it."""
    _demo_notebook()
    app.open_note_in_tab(app.notes[0])
    pump(8)
    if not app.calculator_section.winfo_ismapped():
        app.toggle_calculator_section()
    pump(8)
    for expression in ('7×8', '250÷4'):
        app._calc_display_var.set(expression)
        app._calc_press('=')
        pump(6)
    if not getattr(app, '_calc_history_open', False):
        app._toggle_calc_history()
    pump(16)
    # Whole window: the open history pushes the section past the bottom
    # edge, and a crop that reaches outside the window photographs the
    # desktop -- which the guard correctly refuses to do.
    capture('calculator')


@scene('attachments')
def attachments():
    """The attachments section of a note, with files on it."""
    note = _note(title='Car insurance',
                 body='Renewal is due in March. Policy and photo attached.')
    app.notes.append(note)
    app.save_notes()
    app.refresh_note_list()
    app.open_note_in_tab(note)
    pump(8)
    app.current_attachments = [
        {'filename': 'policy-2026.pdf', 'stored_as': 'policy-2026.pdf'},
        {'filename': 'registration.jpg', 'stored_as': 'registration.jpg'}]
    app.refresh_attachments_list()
    pump(16)
    capture('attachments')


@scene('formatting-toolbar')
def formatting_toolbar():
    """The toolbar, over a body that shows what its buttons do."""
    note = _note(
        title='Recipe: bread',
        body=('Bold for the heading, italic for the aside, underline for '
              'the warning, and a line struck through when it is done.\n\n'
              'Mix, rest two hours, bake at 220.'),
        # Offsets computed from the text, not counted by eye: the
        # first attempt was one character out and the picture showed
        # "itali" in italics with a plain c after it.
        formatting=[{'start': 0, 'end': 4, 'style': 'bold'},
                    {'start': 22, 'end': 28, 'style': 'italic'},
                    {'start': 44, 'end': 53, 'style': 'underline'},
                    {'start': 77, 'end': 96, 'style': 'strike'}])
    app.notes.append(note)
    app.save_notes()
    app.refresh_note_list()
    app.open_note_in_tab(note)
    pump(18)
    capture('formatting-toolbar',
            widgets=_editor_box('title_entry', 'body_text'), pad=10)


@scene('recurrence-setup')
def recurrence_setup():
    """The Repeat section, mid-setup: weekly, on a chosen day."""
    _weekly_note()
    pump(16)
    capture('recurrence-setup',
            widgets=_editor_box('title_entry', 'body_text'), pad=12)


@scene('share-panel')
def share_panel():
    """The Share notes panel, with notes ticked."""
    _demo_notebook()
    app.toggle_share_panel()
    pump(18)
    capture('share-panel')


@scene('import-code')
def import_code():
    """The Import code panel, where a pasted code arrives."""
    _demo_notebook()
    app.toggle_import_panel()
    pump(18)
    capture('import-code')


@scene('emoji-picker')
def emoji_picker():
    """The emoji picker, open over the note body."""
    note = _note(title='Birthday plans',
                 body='Cake, candles, and the boat trip if it stays dry.')
    app.notes.append(note)
    app.save_notes()
    app.refresh_note_list()
    app.open_note_in_tab(note)
    pump(10)
    app._show_emoji_picker(app.body_text)
    pump(20)
    capture('emoji-picker')


@scene('calendar-day-color')
def calendar_day_color():
    """A calendar day painted a colour of its own."""
    _september()
    app.day_colors = dict(getattr(app, 'day_colors', {}))
    app.day_colors['2026-09-18'] = '#ff8800'
    app._persist_day_colors()
    # _open_day draws the month afresh: the grid shows what it drew last,
    # and the first take was a picture of an empty September.
    _open_day('2026-09-18')
    capture('calendar-day-color')
    app.notebook.select(app.TAB_NOTES)
    pump()


def _settings(section):
    """Open Settings at one section, for the panels below."""
    app.show_settings_page()
    pump(8)
    app.toggle_settings_panel(section)
    pump(18)


@scene('settings-overview')
def settings_overview(theme=None):
    """The Settings page: the section list, and one section open.

    Statistics rather than General, which holds one blank field and makes
    a picture of an empty page. On a notebook that has been used: the
    figures count from today, and five notes made on one day in September
    read as a row of zeros under "Using Note Organizer since" today. Used
    within the app's own lifetime, though: a "since" a year before the
    first commit read to reviewers as careless demo data.
    """
    if theme:
        was = app.theme_name
        app.set_theme(theme)
        try:
            return _settings_overview('settings-overview-' + theme)
        finally:
            app.set_theme(was)
            pump()
    return _settings_overview('settings-overview')


@scene('settings-overview-light')
def settings_overview_light():
    """The same page on a light theme: the website shows every picture in
    the theme the page is in, and In my words shows this one."""
    settings_overview('light')


def _settings_overview(name):
    _demo_notebook()
    _table_note()
    errands = [{'text': 'Call the bank', 'done': True},
               {'text': 'Renew the parking permit', 'done': False}]
    for days, title, category, extra in (
            (1, 'Plumber visit', 'General', {}),
            (2, 'Sprint retro', 'Work', {'checklist': errands}),
            (9, 'Gift ideas', 'Personal', {'checklist': errands}),
            (25, 'Holiday budget', 'Personal', {}),
            (40, 'Onboarding notes', 'Work', {'checklist': errands}),
            (54, 'Flat viewing', 'General', {})):
        stamp = _days_ago(days)
        app.notes.append(_note(title=title, category=category,
                               created=stamp, updated=stamp, **extra))
    for note in app.notes[:2]:
        note['updated'] = _days_ago(0)
    app.save_notes()
    app.templates = [NO.normalize_template({'name': name, 'title': name})
                     for name in ('Meeting notes', 'Weekly shop')]
    app.trash = [{'id': 905 + days, 'title': title, 'body': '',
                  'category': 'General', 'deleted_at': _days_ago(days, '18:00:00')}
                 for days, title in ((3, 'Old to-do'), (11, 'Draft'))]
    since = NO.load_settings().get('first_launch_date')
    NO.save_setting('first_launch_date', _days_ago(56)[:10])
    try:
        _settings('statistics')
        capture(name)
    finally:
        NO.save_setting('first_launch_date', since)
        app.hide_settings_page()
        pump()


@scene('theme-picker')
def theme_picker():
    """Settings -> Appearance, with the theme cards -- on a light theme, so
    the README's gallery shows both modes."""
    _demo_notebook()
    was = app.theme_name
    app.set_theme('light')
    _settings('appearance')
    capture('theme-picker')
    app.hide_settings_page()
    app.set_theme(was)
    pump()


@scene('categories-panel')
def categories_panel():
    """Settings -> Categories, with categories listed."""
    _demo_notebook()
    _settings('categories')
    capture('categories-panel')
    app.hide_settings_page()
    pump()


@scene('templates-panel')
def templates_panel():
    """Settings -> Templates, with templates to manage."""
    _demo_notebook()
    app.templates = [
        {'name': 'Meeting notes', 'title': 'Meeting — ',
         'body': 'Present:\nDecided:\nNext:', 'comments': '',
         'category': 'Work', 'checklist': []},
        {'name': 'Weekly shop', 'title': 'Shopping list',
         'body': '', 'comments': '', 'category': 'General',
         'checklist': [{'text': 'Milk', 'done': False},
                       {'text': 'Bread', 'done': False}]},
    ]
    NO.save_templates(app.templates)
    _settings('templates')
    capture('templates-panel')
    app.hide_settings_page()
    pump()


@scene('trash-panel')
def trash_panel():
    """Settings -> Recently deleted, with the retention selector."""
    _demo_notebook()
    app.trash = [
        {'id': 901, 'title': 'Old shopping list', 'body': 'Milk, bread.',
         'category': 'General', 'deleted_at': _days_ago(2, '08:30:00')},
        {'id': 902, 'title': 'Draft email to the landlord',
         'body': 'About the boiler service.', 'category': 'General',
         'deleted_at': _days_ago(5, '19:05:00')},
        {'id': 903, 'title': 'Conference notes', 'body': 'Talk three was the good one.',
         'category': 'Work', 'deleted_at': _days_ago(12, '11:20:00')},
    ]
    _settings('trash')
    capture('trash-panel')
    app.hide_settings_page()
    app.trash = []
    pump()


@scene('duplicates-panel')
def duplicates_panel():
    """Settings -> Duplicates, with a group or two to decide about."""
    _demo_notebook()
    for title, body in (('Shopping list', 'Milk, bread, coffee, olive oil.'),
                        ('Quarterly review', 'Numbers for the board pack.')):
        app.notes.append(_note(title=title, body=body, category='General'))
    app.save_notes()
    app.refresh_note_list()
    _settings('duplicates')
    capture('duplicates-panel')
    app.hide_settings_page()
    pump()


@scene('import-backup')
def import_backup():
    """Settings -> Backup, where a whole notebook goes out and comes in."""
    _demo_notebook()
    _settings('backup')
    capture('import-backup')
    app.hide_settings_page()
    pump()


@scene('demo')
def demo():
    """The README's moving picture: a note written, given a table and
    saved; the calendar; a light theme. One frame after each step, made
    into demo.gif -- the same window, and the same guards, as every shot.
    """
    from PIL import Image
    from noteorganizer.core import tables as core_tables

    frames = []
    width = 960
    # Saved once, on purpose: an autosave caught mid-word would show a
    # half-typed title on the card for a frame or two.
    autosave = app._schedule_autosave
    app._schedule_autosave = lambda *a, **k: None

    def frame(ms):
        pump(6, 0.02)
        img, why = grab(app)
        if img is None:
            raise RuntimeError('a frame was not taken: %s' % why)
        frames.append((img.resize((width, int(img.size[1] * width / img.size[0])),
                                  Image.LANCZOS), ms))

    def type_into(insert, text, every=3):
        for count, char in enumerate(text, 1):
            insert(char)
            if count % every == 0 or count == len(text):
                frame(90)

    try:
        app.lift()
        app.main_canvas.focus_set()
        made = _demo_notebook()
        # A weekly note too, so the month has more on it than one day.
        app.notes.append(_note(
            title='Team stand-up', body='What we shipped, what is next.',
            category='Work', date='2026-09-07',
            recurrence={'freq': 'weekly', 'interval': 1, 'weekdays': [0]}))
        app.save_notes()
        app.refresh_note_list()
        app.open_note_in_tab(made[0])
        frame(1600)
        app.new_note()
        frame(500)
        app.title_entry.focus_set()
        type_into(lambda ch: app.title_entry.insert('end', ch), 'Weekend trip')
        app.body_text.focus_set()
        type_into(lambda ch: app.body_text.insert('insert', ch),
                  'Pack the tent and the stove.\n')
        app.body_text.insert('end', core_tables.align(
            '| Day | Plan | Done |\n'
            '| ---------- | ------------------ | ------ |\n'
            '| Saturday | Drive to the lake | [x] |\n'
            '| Sunday | Hike the ridge | [ ] |')[0])
        app._render_table_grids()
        frame(1600)
        app.save_current_note()
        frame(1300)
        app.notebook.select(app.TAB_CALENDAR)
        app.cal_year, app.cal_month = 2026, 9
        app.render_calendar()
        frame(1800)
        app.set_theme('light')
        app.notebook.select(app.TAB_NOTES)
        app.refresh_note_list()
        frame(2000)
    finally:
        app._schedule_autosave = autosave
        app.set_theme('dark')
        pump()
    images = [im.convert('P', palette=Image.ADAPTIVE, colors=128)
              for im, _ms in frames]
    path = os.path.join(OUT, 'demo.gif')
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=[ms for _im, ms in frames], loop=0, optimize=True)
    print('  %-22s %d frames, %d KB' % ('demo', len(frames),
                                        os.path.getsize(path) // 1024))


# ---------------------------------------------------------------------
# The website's pictures (site/src/index.html), added 2026-10-24.
#
# Its feature cards showed whole windows shrunk to a third of their size,
# the feature each card named lost somewhere inside, and dark on a light
# page as well. Each picture here is cropped close around what its card is
# about, grown to the card's 16:10 so the card crops none of it away, and
# taken in both themes: the page shows the one it is in.
# ---------------------------------------------------------------------

SITE_ASPECT = 16 / 10.0


def _site_shot(name, stage, frame):
    """`stage` the scene and photograph `frame()` -- a logical screen box --
    as site-NAME-dark.png and site-NAME-light.png."""
    was = app.theme_name
    try:
        for theme in ('dark', 'light'):
            clean()
            app.set_theme(theme)
            pump(10)
            stage()
            pump(12)
            capture('site-%s-%s' % (name, theme), box=_fit(frame(), SITE_ASPECT))
    finally:
        try:
            app.hide_settings_page()
        except Exception:
            pass
        app.set_theme(was)
        pump()


def _checklist_scene():
    note = _note(
        title='Trip packing',
        body='The flight leaves early; nothing left for the morning.',
        checklist=[{'text': 'Passports', 'done': True},
                   {'text': 'Charger and adapter', 'done': True},
                   {'text': 'Print the booking', 'done': False},
                   {'text': 'Stop the milk', 'done': False}])
    app.notes.append(note)
    app.save_notes()
    app.refresh_note_list()
    app.open_note_in_tab(note)
    pump(10)
    if not app.checklist_section.winfo_ismapped():
        app.toggle_checklist_section()
    pump(16)
    _scroll_editor_to(app.checklist_section)


def _table_frame():
    """The note's opening line and its drawn table, nothing below."""
    body = app.body_text
    grids = [info.get('canvas') for info in getattr(app, '_table_grids', [])
             if info.get('canvas') is not None]
    if not grids:
        return _box_of([body], 12)
    grid = grids[0]
    # From the text's own edge: 8px further left took in the sidebar's
    # edge and its collapse arrow.
    return (body.winfo_rootx() + 2, body.winfo_rooty() - 8,
            grid.winfo_rootx() + grid.winfo_width() + 16,
            grid.winfo_rooty() + grid.winfo_height() + 12)


def _checklist_frame():
    """The checklist's header and its items, down to the last one: the
    section runs on below them, empty, and the calculator sits beside."""
    section, header = app.checklist_section, app.checklist_btn
    left, top = section.winfo_rootx(), header.winfo_rooty() - 4
    width = section.winfo_width()
    return _cut((left, top, left + width, top + width), SITE_ASPECT)


def _repeat_frame():
    """The note's title, its date and the whole Repeat block, at the width
    its widest row needs -- not the editor's, which is mostly empty there."""
    title = app.title_entry
    left, top = title.winfo_rootx() - 12, title.winfo_rooty() - 12
    width = 480
    return (left, top, left + width, top + width / SITE_ASPECT)


def _search_scene():
    for title, body, cat, date in (
            ('Quarterly review', "Numbers for the board pack, the team's targets.",
             'Work', '2026-09-30'),
            ('Team lunch', 'Friday at the Italian place, booked for six.',
             'Personal', '2026-09-25'),
            ('Reading list', 'Three books before the holidays.', 'Personal', ''),
            ('Groceries', 'Everything for the weekend.', 'Personal', '')):
        app.notes.append(_note(title=title, body=body, category=cat, date=date))
    _weekly_note()
    app.search_var.set('team')
    app.sort_var.set('Calendar: oldest')
    app.refresh_note_list()
    pump(14)


def _search_frame():
    """The search box, the sort, and the first two matches, with the start
    of the note it opened beside them."""
    # From the sidebar's own top, so its heading and the open note's title
    # are whole: a box starting at the search field cut both through.
    s = app.sidebar
    top = s.winfo_rooty()
    height = 520
    return (s.winfo_rootx(), top, s.winfo_rootx() + height * SITE_ASPECT, top + height)


def _calendar_scene():
    _september()
    app.notebook.select(app.TAB_CALENDAR)
    pump(10)
    app.cal_year, app.cal_month = 2026, 9
    app.render_calendar()
    pump(14)


def _calendar_frame():
    """The month's first weeks, Monday to Thursday and a little more:
    readable at a card's size, as the whole month is not."""
    g = app.cal_grid_frame
    # Four of seven columns, ending in the gap before Friday: 0.62 showed
    # a sliver of Friday's note, a "B" on the edge.
    width = g.winfo_width() * 0.568
    return (g.winfo_rootx(), g.winfo_rooty(),
            g.winfo_rootx() + width, g.winfo_rooty() + width / SITE_ASPECT)


def _trash_scene():
    _demo_notebook()
    app.trash = [
        {'id': 901, 'title': 'Old shopping list', 'body': 'Milk, bread.',
         'category': 'General', 'deleted_at': _days_ago(2, '08:30:00')},
        {'id': 902, 'title': 'Draft email to the landlord',
         'body': 'About the boiler service.', 'category': 'General',
         'deleted_at': _days_ago(5, '19:05:00')},
        {'id': 903, 'title': 'Conference notes', 'body': 'Talk three was the good one.',
         'category': 'Work', 'deleted_at': _days_ago(12, '11:20:00')},
    ]
    _settings('trash')


def _trash_frame():
    """The three rows: tick box, title, date line, Restore and Delete."""
    titles = sorted(_widgets_with_text('Old shopping list', 'Conference notes'),
                    key=lambda w: w.winfo_rooty())
    first, last = titles[0], titles[-1]
    deletes = [w for w in _widgets_with_text('Delete')
               if first.winfo_rooty() - 30 <= w.winfo_rooty() <= last.winfo_rooty() + 60]
    right = max([w.winfo_rootx() + w.winfo_width() for w in deletes]
                or [last.winfo_rootx() + 400])
    left, top = first.winfo_rootx() - 56, first.winfo_rooty() - 16
    # Already the card's shape, grown downward only: grown evenly, the top
    # took in half a line of the retention text above the rows.
    return (left, top, right + 14, top + (right + 14 - left) / SITE_ASPECT)


def _themes_scene():
    _demo_notebook()
    _settings('appearance')


def _themes_frame():
    """Both rows of theme tiles, their DARK and LIGHT headings with them."""
    heads = _widgets_with_text('DARK', 'LIGHT')
    tiles = [w.master for w in _widgets_with_text(
        'Midnight Purple', 'Warm Charcoal', 'Soft Lavender', 'Warm Cream')]
    return _box_of(heads + tiles, 10)


@scene('site-cards')
def site_cards():
    """Every picture of the website's feature cards and its themes
    section, each in the dark theme and the light one."""
    _site_shot('tables', _table_note, _table_frame)
    _site_shot('checklist', _checklist_scene, _checklist_frame)
    _site_shot('repeat', _weekly_note, _repeat_frame)
    _site_shot('calendar', _calendar_scene, _calendar_frame)
    _site_shot('search', _search_scene, _search_frame)
    _site_shot('trash', _trash_scene, _trash_frame)
    _site_shot('themes', _themes_scene, _themes_frame)


def _all_widgets(w, out=None):
    out = [] if out is None else out
    for c in w.winfo_children():
        out.append(c)
        _all_widgets(c, out)
    return out


def main(argv):
    wanted = set(argv[1:])
    print('shots ->', OUT)
    for name, fn in SCENES:
        if wanted and name not in wanted:
            continue
        clean()
        try:
            fn()
        except Exception as exc:
            print('  %-22s FAILED: %s' % (name, exc))
    app.destroy()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
