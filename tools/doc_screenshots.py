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
Copy ``note_organizer.py``, the ``noteorganizer/`` package and this
script into a scratch folder outside the project tree, then::

    py doc_screenshots.py                 # every scene
    py doc_screenshots.py calendar-view   # just one

PNGs land in ``./shots``; copy the ones you want into
``docs/screenshots/``. Windows only, like ``visual_scenes.py``, for the
same reason: ImageGrab needs real win32 windows.
"""

# HERMETIC SEED -- same guard as the qa scripts, for the same reason.
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

import os
import sys
import time

from PIL import ImageGrab

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


# ImageGrab works in PHYSICAL pixels; Tk reports window geometry in
# LOGICAL ones. On a display with any scaling the two differ, and a grab
# box built from Tk's numbers lands up and to the left of the window --
# the first retakes cut the calendar's History button off the right edge
# and included a strip of the window behind. Measured once, here, rather
# than assumed to be 1.
SCALE = ImageGrab.grab().size[0] / float(app.winfo_screenwidth())
print('display scale: %.2f' % SCALE)


# ---- Nothing of anybody's screen ends up in these files -------------
#
# ImageGrab photographs the SCREEN at the window's coordinates, not the
# window. Raising ours and setting -topmost is necessary and NOT
# sufficient: another always-on-top window wins anyway, and on the first
# full run an Android emulator sat in the middle of nineteen pictures.
# A browser did it once before that.
#
# Being careful is not a mechanism. So before every shutter, points
# across the box are asked WHICH window is actually on top there. A
# window belonging to another program means the picture would be of
# something else -- so it is not taken, and the scene says so.

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_OUR_PID = os.getpid()


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def _owner_pid_at(x, y):
    """Which process owns the window drawn at this screen point."""
    hwnd = _user32.WindowFromPoint(_POINT(int(x), int(y)))
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _foreign_window_over(box, steps=7):
    """A window from another program, covering any part of the box."""
    left, top, right, bottom = box
    seen = set()
    for i in range(steps):
        for j in range(steps):
            x = left + (right - left) * (i + 0.5) / steps
            y = top + (bottom - top) * (j + 0.5) / steps
            pid = _owner_pid_at(x, y)
            if pid and pid != _OUR_PID:
                seen.add(pid)
    return sorted(seen)


def _window_title_of(pid):
    """Best-effort name for the intruder, so the message is useful."""
    titles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _lparam):
        owner = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and _user32.IsWindowVisible(hwnd):
            length = _user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.strip():
                    titles.append(buf.value.strip())
        return True

    _user32.EnumWindows(each, 0)
    return titles[0] if titles else "pid %d" % pid


def capture(name, widgets=None, pad=8):
    """Save the whole window, or the box that holds `widgets`."""
    app.lift()
    app.attributes('-topmost', True)
    app.focus_force()
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
    if widgets:
        xs, ys, xe, ye = [], [], [], []
        for w in widgets:
            xs.append(w.winfo_rootx())
            ys.append(w.winfo_rooty())
            xe.append(w.winfo_rootx() + w.winfo_width())
            ye.append(w.winfo_rooty() + w.winfo_height())
        box = (min(xs) - pad, min(ys) - pad, max(xe) + pad, max(ye) + pad)
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
    intruders = _foreign_window_over(box)
    if intruders:
        who = ", ".join(_window_title_of(p) for p in intruders)
        print('  %-22s NOT TAKEN: %s is covering the window' % (name, who))
        return
    box = tuple(int(round(v * SCALE)) for v in box)
    img = ImageGrab.grab(bbox=box)
    path = os.path.join(OUT, name + '.png')
    img.save(path)
    print('  %-22s %dx%d' % (name, img.size[0], img.size[1]))


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

    app.search_var.set('')
    app.sort_var.set(app.SORT_OPTIONS[0])
    app.category_filter_var.set('All') if hasattr(app, 'category_filter_var') else None
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
    app.load_note(note)
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
    for title, body, cat in (
            ('Quarterly review', 'Numbers for the board pack.', 'Work'),
            ('Reading list', 'Three books before the holidays.', 'Personal'),
            ('Groceries', 'Everything for the weekend.', 'Personal')):
        app.notes.append(_note(title=title, body=body, category=cat))
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


@scene('calendar-view')
def calendar_view():
    """The calendar, with a repeating note and the day panel open.

    Stale since 0.71.111: the calendar gained a History button, which the
    old shot predates.
    """
    _weekly_note()
    app.notebook.select(app.TAB_CALENDAR)
    pump(14)
    app.open_day_popup('2026-09-14')
    pump(14)
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
        app.load_note(note)
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
    capture('tables', widgets=_editor_box('body_text'), pad=12)


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
    app.load_note(note)
    pump(10)
    if not app.checklist_section.winfo_ismapped():
        app.toggle_checklist_section()
    pump(16)
    capture('checklist',
            widgets=_editor_box('checklist_btn', 'checklist_section',
                                'calculator_btn'), pad=12)


@scene('calculator')
def calculator():
    """The calculator open, with a result and a history behind it."""
    _demo_notebook()
    app.load_note(app.notes[0])
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
    app.load_note(note)
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
    app.load_note(note)
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
    app.load_note(note)
    pump(10)
    app._show_emoji_picker(app.body_text)
    pump(20)
    capture('emoji-picker')


@scene('calendar-day-color')
def calendar_day_color():
    """A calendar day painted a colour of its own."""
    _weekly_note()
    app.day_colors = dict(getattr(app, 'day_colors', {}))
    app.day_colors['2026-09-18'] = '#ff8800'
    app._persist_day_colors()
    app.notebook.select(app.TAB_CALENDAR)
    pump(10)
    # The month is DRAWN, not watched: setting a day's colour and adding a
    # note change the data, and the grid keeps showing what it drew before.
    # The first take was a picture of an empty September.
    app.render_calendar()
    pump(20)
    app.open_day_popup('2026-09-18')
    pump(16)
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
def settings_overview():
    """The Settings page: the section list, and one section open.

    Statistics rather than General, which holds one blank field and makes
    a picture of an empty page. This one shows the nav beside a panel
    with something in it, and no other shot covers it.
    """
    _demo_notebook()
    _table_note()
    _settings('statistics')
    capture('settings-overview')
    app.hide_settings_page()
    pump()


@scene('theme-picker')
def theme_picker():
    """Settings -> Appearance, with the theme cards."""
    _demo_notebook()
    _settings('appearance')
    capture('theme-picker')
    app.hide_settings_page()
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
         'category': 'General', 'deleted_at': '2026-09-12 08:30:00'},
        {'id': 902, 'title': 'Draft email to the landlord',
         'body': 'About the boiler service.', 'category': 'General',
         'deleted_at': '2026-09-09 19:05:00'},
        {'id': 903, 'title': 'Conference notes', 'body': 'Talk three was the good one.',
         'category': 'Work', 'deleted_at': '2026-09-02 11:20:00'},
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
