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

import note_organizer as NO

OUT = os.path.join(os.getcwd(), 'shots')
os.makedirs(OUT, exist_ok=True)

# The app hides its -topmost popups whenever another program holds the
# Windows foreground, on a 300ms heartbeat -- and a scripted run never
# holds it, so a dropdown opened here would be photographed closed. The
# qa suite pins the same answer for the same reason (_qa_support's
# pin_popup_visibility); this is that patch, applied before the app is
# built so the heartbeat never sees the real answer.
if hasattr(NO.NoteOrganizer, '_foreground_is_ours'):
    NO.NoteOrganizer._foreground_is_ours = lambda self: True

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


def capture(name, widgets=None, pad=8):
    """Save the whole window, or the box that holds `widgets`."""
    app.lift()
    app.attributes('-topmost', True)
    app.focus_force()
    pump(10)
    if widgets:
        xs, ys, xe, ye = [], [], [], []
        for w in widgets:
            xs.append(w.winfo_rootx())
            ys.append(w.winfo_rooty())
            xe.append(w.winfo_rootx() + w.winfo_width())
            ye.append(w.winfo_rooty() + w.winfo_height())
        box = (min(xs) - pad, min(ys) - pad, max(xe) + pad, max(ye) + pad)
    else:
        box = (app.winfo_rootx(), app.winfo_rooty(),
               app.winfo_rootx() + app.winfo_width(),
               app.winfo_rooty() + app.winfo_height())
    box = tuple(int(round(v * SCALE)) for v in box)
    img = ImageGrab.grab(bbox=box)
    path = os.path.join(OUT, name + '.png')
    img.save(path)
    print('  %-22s %dx%d' % (name, img.size[0], img.size[1]))


def clean():
    app.notes = []
    app.save_notes()
    app.open_blank_tab()
    pump()


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
