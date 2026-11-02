"""Visual scene runner: staged screenshots of the real app, for eyes.

WHAT THIS IS FOR
----------------
The qa suite asserts behaviour in numbers; nothing in it ever LOOKS at
the app. This tool closes that gap: it launches the real application
in-process, stages a set of named scenes (a rich note, a table-heavy
note, the settings page, the find bar mid-search...), and writes one PNG
per scene plus a ``shots/log.json`` with timings and any Tk callback
errors that fired along the way. A reviewer -- human or agent -- then
looks at the gallery.

Burst mode exists for what a still image cannot show: transient
repaints. ``--burst`` runs a few staged ACTIONS (theme switch over a
table note, a push-down Enter, a wheel scroll) capturing frames as fast
as the platform allows, and logs the pixel-difference score between
consecutive frames -- a flicker shows up as a spike in an otherwise
quiet series. Frame pacing is bounded by ImageGrab (~40-100ms/frame),
so sub-frame flickers can escape it; that limit is honest and logged.

RUNNING IT (the qa safety rule applies -- NEVER in place)
---------------------------------------------------------
Copy ``note_organizer.py``, the ``noteorganizer/`` package, this script,
``tools/guest.py`` and ``qa/_qa_support.py`` into a scratch folder outside
the project tree, then:

    py visual_scenes.py            # still scenes
    py visual_scenes.py --burst    # burst scenes too

Output lands in ``./shots``. Windows only (ImageGrab + real win32
windows); the CI Linux job has no place here. guest.py gives the run its
turn and its memory ceiling before the app is built; every frame goes
through _qa_support's shutter (a picture holds only the app's pixels).
"""

# THE TURN, THE CEILING AND THE SEED before the app -- this builds the whole
# app, on the screen. _qa_support.seed_here does all three, after the DPI call
# below (it loads tkinter): see its use there.
import os as _guest_os, sys as _guest_sys
_guest_sys.path.insert(0, _guest_os.path.dirname(_guest_os.path.abspath(__file__)))
if not _guest_os.path.exists(_guest_os.path.join(_guest_sys.path[0], '_qa_support.py')):
    _guest_sys.exit('REFUSING to run: no _qa_support.py here, the shutter. Copy '
                    'tools/guest.py and qa/_qa_support.py beside this script (see '
                    'its docstring).')

import ctypes
import json
import os
import sys
import time
import traceback

# DPI awareness BEFORE tkinter loads, so winfo_* coordinates equal real
# screen pixels and the grab bbox lands exactly on the window.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from PIL import ImageChops, ImageStat

# After the DPI call: _qa_support loads tkinter. seed_here settles as a guest
# (tools/guest.py, beside it), then seeds an empty notebook here: only where
# the app will open it, asked of its own resolver, and never beside notes.
from _qa_support import grab as _shutter, seed_here
seed_here()
import note_organizer as NO
import tkinter as tk
from noteorganizer.core import tables as core_tables

OUT = os.path.join(os.getcwd(), 'shots')
os.makedirs(OUT, exist_ok=True)

log = {'scenes': [], 'bursts': [], 'tk_errors': [], 'not_covered': []}

# The window's resize freeze asks Windows whether the mouse button is down,
# anywhere on the desktop, and lays nothing out while it is: a click held in
# another program during a run would photograph a page not laid out yet.
# The qa suite pins the same answer (_qa_support's pin_the_desktop).
if hasattr(NO.NoteOrganizer, '_pointer_button_held'):
    NO.NoteOrganizer._pointer_button_held = lambda self: False

app = NO.NoteOrganizer()
app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.geometry('1280x900+40+40')
app.lift()
app.attributes('-topmost', True)

_orig_report = app.report_callback_exception
def _report(exc, val, tb):
    log['tk_errors'].append(''.join(
        traceback.format_exception_only(exc, val)).strip())
    _orig_report(exc, val, tb)
app.report_callback_exception = _report


def pump(n=6, sleep=0.02):
    for _ in range(n):
        app.update()
        app.update_idletasks()
        time.sleep(sleep)


def grab():
    """The window, through the one shutter: cut to the primary screen's work
    area, and refused when another program's window lies over it."""
    img, why = _shutter(app)
    if img is None:
        raise RuntimeError('NOT TAKEN: %s' % why)
    return img


def capture(name):
    pump()
    t0 = time.time()
    img = grab()
    path = os.path.join(OUT, name + '.png')
    img.save(path)
    log['scenes'].append({'name': name, 'file': os.path.basename(path),
                          'ms': round((time.time() - t0) * 1000),
                          'size': img.size})
    print('  shot', name)


def diff_score(a, b):
    """Mean pixel difference between two frames -- 0.0 for identical."""
    return round(sum(ImageStat.Stat(ImageChops.difference(a, b)).mean), 2)


def burst(name, action, frames=10):
    """Frames around an action; consecutive diff scores expose transients."""
    try:
        _burst(name, action, frames)
    except RuntimeError as exc:
        log['bursts'].append({'name': name, 'error': str(exc)})
        print('  BURST NOT TAKEN', name, exc)


def _burst(name, action, frames):
    pump()
    series = [grab()]
    stamps = [0.0]
    t0 = time.time()
    action()
    while len(series) <= frames:
        app.update()
        app.update_idletasks()
        series.append(grab())
        stamps.append(round((time.time() - t0) * 1000))
    scores = [diff_score(series[i], series[i + 1])
              for i in range(len(series) - 1)]
    for i, img in enumerate(series):
        img.save(os.path.join(OUT, f'{name}_f{i:02d}.png'))
    log['bursts'].append({'name': name, 'frames': len(series),
                          'ms': stamps, 'diffs': scores})
    print('  burst', name, 'diffs:', scores)


# ---------------------------------------------------------------- scenes

# Wide separators on purpose: the drawn grid honours the separator's
# dash count as the stored display width, so `---` renders collapsed
# 3-char columns (real behaviour for pasted skinny-separator markdown —
# noted as an audit seed). Native tables carry content-wide separators;
# the scene stages that canonical look.
TABLE_BODY = core_tables.align(
    'Meal plan for the week' + '\n'
    + '| Day | Lunch | Dinner |' + '\n'
    + '| ---------- | ------- | ---------- |' + '\n'
    + '| Monday | Soup | Pasta |' + '\n'
    + '| Tuesday | [x] | Tacos |' + '\n'
    + '| Wednesday | [ ] | Stir-fry |' + '\n'
    + 'Table 1: description' + '\n' + 'Source: cookbook')[0]


def stage_rich_note():
    app.new_note()
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'A well-dressed note')
    b = app.body_text
    b.insert('1.0', 'Bold opening line\n'
                    'A centred thought\n'
                    '• first item\n• second item\n'
                    'And a plain closing paragraph.')
    b.tag_add('sel', '1.0', '1.17')
    app._fmt_buttons['bold'].invoke()
    b.tag_remove('sel', '1.0', 'end')
    b.mark_set('insert', '2.0')
    app._set_paragraph_align('center')
    app._resync_list_tags()
    pump()


def stage_table_note():
    app.new_note()
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'Table territory')
    app.body_text.insert('1.0', TABLE_BODY)
    app._render_table_grids()
    pump()


def stage_long_list():
    app.notes = [NO.normalize_note(
        {'id': 9000 + i, 'title': f'Note number {i}',
         'body': 'body text ' * 6,
         'category': 'General' if i % 2 else 'Work'})
        for i in range(24)]
    app.group_by_category.set(True)
    app._on_toggle_group_by_category()
    app.refresh_note_list()
    pump()


SCENES = []


def scene(name, themed=False):
    def deco(fn):
        SCENES.append((name, fn, themed))
        return fn
    return deco


@scene('s01_empty', themed=True)
def s01():
    app.new_note()


@scene('s02_rich_note', themed=True)
def s02():
    stage_rich_note()


@scene('s03_table_note', themed=True)
def s03():
    stage_table_note()


@scene('s04_table_cell_editor')
def s04():
    stage_table_note()
    info = app._grid_at_line(2)
    if info:
        app._open_cell_editor(info, 0, 1)


@scene('s05_find_bar_on_table')
def s05():
    stage_table_note()
    app._open_find()
    app._find_var.set('Tacos')
    app._find_rescan(reveal=True)


@scene('s06_checklist_calculator')
def s06():
    app.new_note()
    app._working_checklist = [
        {'text': 'pack the bags', 'done': True},
        {'text': 'call the venue', 'done': False}]
    if hasattr(app, '_checklist_rows'):
        app._render_checklist_items()
    if not app._checklist_open:
        app.toggle_checklist_section()
    if not getattr(app, '_calculator_open', False):
        app._sync_calculator_open_state()


@scene('s07_long_list_grouped')
def s07():
    stage_long_list()


@scene('s08_share_panel')
def s08():
    stage_long_list()
    if not app.share_panel.winfo_ismapped():
        app.toggle_share_panel()


@scene('s09_settings')
def s09():
    app.show_settings_page()


@scene('s10_calendar')
def s10():
    app.hide_settings_page()
    app.notebook.select(app.TAB_CALENDAR)
    app.render_calendar()


def run_scenes():
    for name, fn, themed in SCENES:
        try:
            app.notebook.select(app.TAB_NOTES)
        except tk.TclError:
            pass
        try:
            fn()
            capture(name + '_dark')
            if themed:
                app.set_theme('light')
                pump()
                capture(name + '_light')
                app.set_theme('dark')
                pump()
        except Exception as e:
            log['scenes'].append({'name': name, 'error': repr(e)})
            print('  SCENE FAILED', name, repr(e))


def run_bursts():
    # The bursts stage the NOTES tab explicitly -- the first run left the
    # notebook on the calendar and measured ten identical frames of it.
    app.notebook.select(app.TAB_NOTES)
    pump()
    stage_table_note()
    burst('b01_theme_switch_on_table',
          lambda: app.set_theme('light'))
    app.set_theme('dark')
    pump()

    # A push-down needs a note that STARTS with a table and the caret at the
    # start of the line under it. The table note above opens with a caption,
    # so this scene used to time an ordinary Enter under the caption, which
    # pushes nothing. And a real key, press and release: the release is
    # where a second rebuild once came from (ISSUES_LOG, smaller lessons).
    app.new_note()
    app.body_text.insert('1.0', core_tables.align(
        '| Day | Lunch | Dinner |\n| --- | --- | --- |\n'
        '| Monday | Soup | Pasta |\n| Tuesday | Salad | Tacos |')[0] + '\nbelow the table')
    app._render_table_grids()
    pump()
    below = app._table_block_at(1)[1] + 1
    app.body_text.mark_set('insert', f'{below}.0')
    app._last_caret_line = below
    app.body_text.focus_force()
    pump()

    def press_enter():
        app.body_text.event_generate('<KeyPress-Return>', keysym='Return', when='now')
        app.body_text.event_generate('<KeyRelease-Return>', keysym='Return', when='now')

    burst('b02_pushdown_enter_above_table', press_enter)

    stage_long_list()
    burst('b03_list_scroll', lambda: app.canvas.yview_scroll(5, 'units'))


def main():
    print('scenes ->', OUT)
    run_scenes()
    if '--burst' in sys.argv:
        run_bursts()
    else:
        log['not_covered'].append('burst scenes (run with --burst)')
    log['not_covered'].append(
        'sub-frame flicker: ImageGrab paces ~40-100ms/frame')
    with open(os.path.join(OUT, 'log.json'), 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=1, ensure_ascii=False)
    errs = len(log['tk_errors'])
    # A scene that raised is recorded with an 'error' key — and used to
    # be invisible to the exit code, so a failed scene still exited 0
    # and the run read as passed.
    scene_errs = sum(1 for entry in log['scenes'] + log['bursts']
                     if 'error' in entry)
    print(f"done: {len(log['scenes'])} scenes, {len(log['bursts'])} bursts, "
          f'{errs} tk errors, {scene_errs} scene errors -> shots/log.json')
    try:
        app.destroy()
    except Exception:
        pass
    sys.exit(1 if errs or scene_errs else 0)


if __name__ == '__main__':
    main()
