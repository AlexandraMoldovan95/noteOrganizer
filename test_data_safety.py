"""Data-safety tests: backups made before touching real notes, and the
migration logic that moves data between storage locations. Runs headlessly,
no GUI needed — everything here is pure filesystem/settings logic.

Like the qa*.py scripts, this must be run from an isolated working
directory, never the project's own root — see CLAUDE.md's "QA testing
safety" section. Unlike qa*.py, most checks here use their own temporary
directories (not the app's real data folder) for extra isolation, since
this file specifically exercises backup/migration code."""
import sys
import os
import json
import shutil
import tempfile
# ---- REFUSE TO RUN BESIDE REAL NOTES ----
# This file deletes and rewrites notes_data.json in its own directory.
# Run from the project root it destroys the real notebook -- which
# happened once, despite the warning above being here the whole time. A
# warning depends on being read; this check does not. CI and a proper
# scratch copy have no notes_data.json here, so they pass through.
def _guard_real_notes():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "notes_data.json")
    try:
        with open(here, encoding="utf-8") as f:
            notes = json.load(f)
    except (IOError, OSError, ValueError):
        return
    if isinstance(notes, list) and notes:
        sys.exit(
            "REFUSING to run: the notes_data.json beside this test holds "
            "%d notes.\nThis test deletes and rewrites that file. Run it "
            "only from a throwaway copy\noutside the project tree -- see "
            "CLAUDE.md, 'QA testing safety'." % len(notes))


_guard_real_notes()

import note_organizer as NO
# Patch targets live in the module that LOOKS THE NAME UP. run_migrations and
# purge_stale_copies moved into noteorganizer.core.paths, so they resolve
# get_appdata_dir in that module's namespace — patching the re-exported
# note_organizer.get_appdata_dir has no effect on them and would silently let
# these tests run against the real %APPDATA%.
from noteorganizer.core import paths as NO_paths

# Importing note_organizer no longer resolves a data folder, migrates notes or
# writes settings — that all moved into initialise(), so an import cannot
# damage a notebook by itself. This file works directly with the data layer
# rather than building a window, so it has to ask for it explicitly. Doing so
# in THIS directory is exactly why the file must be run from a throwaway copy
# (see CLAUDE.md's "QA testing safety").
NO.initialise()

fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

# ---- backup_notes_file(): the one-time-cleanup / version-upgrade backup ----
if os.path.exists(NO.DATA_FILE):
    os.remove(NO.DATA_FILE)
check('backup_notes_file returns None when there is no file to back up',
      NO.backup_notes_file() is None)

with open(NO.DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump([{'id': 1, 'title': 'Real note', 'body': 'x'}], f)
backup_path = NO.backup_notes_file()
check('backup_notes_file creates a real file when notes exist',
      backup_path is not None and os.path.exists(backup_path))
if backup_path:
    with open(backup_path, encoding='utf-8') as f:
        backed_up = json.load(f)
    check('the backup contains the original note content',
          bool(backed_up) and backed_up[0]['title'] == 'Real note')
    os.remove(backup_path)
os.remove(NO.DATA_FILE)

# ---- _timestamped_backup(): the migration-path backup helper ----
tmpdir = tempfile.mkdtemp()
try:
    fake_notes = os.path.join(tmpdir, 'notes_data.json')
    check('_timestamped_backup returns None for a file that does not exist',
          NO._timestamped_backup(fake_notes, 'test') is None)

    with open(fake_notes, 'w', encoding='utf-8') as f:
        json.dump([{'id': 1, 'title': 'Local note'}], f)
    tb_path = NO._timestamped_backup(fake_notes, 'test')
    check('_timestamped_backup creates a real backup',
          tb_path is not None and os.path.exists(tb_path))
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# ---- detect_version_change() ----
def set_stored_version(v):
    settings = NO.load_settings()
    if v is None:
        settings.pop('app_version', None)
    else:
        settings['app_version'] = v
    NO.save_settings(settings)

original_settings = NO.load_settings()  # restore at the end

set_stored_version(None)
check('detect_version_change is silent on a true first run (no stored version)',
      NO.detect_version_change() is None)

set_stored_version('0.0.1')  # guaranteed lower than any real APP_VERSION
result = NO.detect_version_change()
check('detect_version_change reports an upgrade when the stored version is older',
      result is not None and result[0] == 'up' and result[1] == '0.0.1')
check('detect_version_change records the current version after checking',
      NO.load_settings().get('app_version') == NO.APP_VERSION)

major, minor, patch = NO.parse_version(NO.APP_VERSION)
set_stored_version(f'{major + 1}.0.0')  # guaranteed higher than the running app
result2 = NO.detect_version_change()
check('detect_version_change stays silent on an apparent downgrade (re-baselines quietly)',
      result2 is None)

# ---- get_first_launch_date(): stamped once, never overwritten ----
settings = NO.load_settings()
settings.pop('first_launch_date', None)
NO.save_settings(settings)
stamped = NO.get_first_launch_date()
check('get_first_launch_date stamps a date when none exists yet',
      NO.load_settings().get('first_launch_date') == stamped)

settings = NO.load_settings()
settings['first_launch_date'] = '2020-01-01'
NO.save_settings(settings)
check('get_first_launch_date returns the existing date without overwriting it',
      NO.get_first_launch_date() == '2020-01-01')
check('the stored date is unchanged on disk after that call',
      NO.load_settings().get('first_launch_date') == '2020-01-01')

NO.save_settings(original_settings)  # restore whatever was really there

# ---- run_migrations(): Case 1 backup-verification fix ----
# The bug this closes: if backing up the local file before overwriting it
# with the AppData copy failed, the overwrite used to proceed anyway. Now
# it should refuse and leave the local file untouched instead.
real_get_appdata_dir = NO_paths.get_appdata_dir
app_dir = tempfile.mkdtemp()
appdata_dir = tempfile.mkdtemp()
try:
    NO_paths.get_appdata_dir = lambda: appdata_dir

    with open(os.path.join(appdata_dir, 'notes_data.json'), 'w', encoding='utf-8') as f:
        json.dump([{'id': 1, 'title': 'AppData note'}], f)

    local_notes_path = os.path.join(app_dir, 'notes_data.json')
    with open(local_notes_path, 'w', encoding='utf-8') as f:
        json.dump([{'id': 2, 'title': 'Local note that must not be lost'}], f)

    real_copy2 = shutil.copy2
    def failing_copy2(src, dst):
        if src == local_notes_path:
            raise OSError('simulated backup failure')
        return real_copy2(src, dst)
    shutil.copy2 = failing_copy2
    try:
        result3 = NO.run_migrations(app_dir)
    finally:
        shutil.copy2 = real_copy2

    check('run_migrations aborts (returns None) when the safety backup fails',
          result3 is None)
    with open(local_notes_path, encoding='utf-8') as f:
        still_there = json.load(f)
    check('the local file is untouched when the backup failed',
          bool(still_there) and still_there[0]['title'] == 'Local note that must not be lost')

    # Now confirm the normal (backup succeeds) path still works correctly.
    result4 = NO.run_migrations(app_dir)
    check('run_migrations succeeds and reclaims when the backup works normally',
          result4 is not None)
    with open(local_notes_path, encoding='utf-8') as f:
        reclaimed = json.load(f)
    check('after a successful reclaim, the local file now holds the AppData note',
          bool(reclaimed) and reclaimed[0]['title'] == 'AppData note')
    backups = [f for f in os.listdir(app_dir) if f.startswith('notes_data_replaced_')]
    check('a backup of the displaced local note was kept, not deleted',
          len(backups) == 1)
finally:
    NO_paths.get_appdata_dir = real_get_appdata_dir
    shutil.rmtree(app_dir, ignore_errors=True)
    shutil.rmtree(appdata_dir, ignore_errors=True)

# ---- purge_stale_copies(): must never delete the real AppData folder ----
# The bug this closes: AppData was treated as just another disposable
# "legacy" folder, so the instant its content also existed somewhere else
# (which the reclaim step above guarantees, right after copying it) it got
# deleted outright as a "redundant stale copy" -- including notes_data.json,
# settings.json, and the whole attachments/ folder. That happened simply
# from importing this module in script mode from any throwaway directory
# (a dev checkout, a CI runner, even a test script's own scratch copy)
# while real notes existed in AppData. It must now be permanently exempt.
app_dir = tempfile.mkdtemp()
appdata_dir = tempfile.mkdtemp()
try:
    NO_paths.get_appdata_dir = lambda: appdata_dir

    appdata_note = [{'id': 1, 'title': 'Real AppData note'}]
    with open(os.path.join(appdata_dir, 'notes_data.json'), 'w', encoding='utf-8') as f:
        json.dump(appdata_note, f)
    with open(os.path.join(appdata_dir, 'settings.json'), 'w', encoding='utf-8') as f:
        json.dump({'app_version': NO.APP_VERSION}, f)
    os.makedirs(os.path.join(appdata_dir, 'attachments'))
    with open(os.path.join(appdata_dir, 'attachments', 'photo.png'), 'w', encoding='utf-8') as f:
        f.write('fake image bytes')

    # The local copy is a perfect superset (as it would be right after a
    # reclaim) -- exactly the condition that used to trigger deletion.
    with open(os.path.join(app_dir, 'notes_data.json'), 'w', encoding='utf-8') as f:
        json.dump(appdata_note, f)
    os.makedirs(os.path.join(app_dir, 'attachments'))
    with open(os.path.join(app_dir, 'attachments', 'photo.png'), 'w', encoding='utf-8') as f:
        f.write('fake image bytes')

    NO.purge_stale_copies(app_dir)

    check('AppData notes_data.json still exists after purge_stale_copies',
          os.path.exists(os.path.join(appdata_dir, 'notes_data.json')))
    with open(os.path.join(appdata_dir, 'notes_data.json'), encoding='utf-8') as f:
        still_there = json.load(f)
    check('AppData notes_data.json content is untouched',
          still_there == appdata_note)
    check('AppData settings.json still exists after purge_stale_copies',
          os.path.exists(os.path.join(appdata_dir, 'settings.json')))
    check('AppData attachments/ still exists after purge_stale_copies',
          os.path.exists(os.path.join(appdata_dir, 'attachments', 'photo.png')))

    # Confirm the fix is scoped correctly: a genuinely stale, non-AppData
    # leftover (e.g. an old dist\ copy from a previous relative-path build)
    # must still get cleaned up exactly as before.
    dist_dir = os.path.join(app_dir, 'dist')
    os.makedirs(dist_dir)
    with open(os.path.join(dist_dir, 'notes_data.json'), 'w', encoding='utf-8') as f:
        json.dump(appdata_note, f)
    NO.purge_stale_copies(app_dir)
    check('a genuinely stale non-AppData leftover is still cleaned up',
          not os.path.exists(os.path.join(dist_dir, 'notes_data.json')))
finally:
    NO_paths.get_appdata_dir = real_get_appdata_dir
    shutil.rmtree(app_dir, ignore_errors=True)
    shutil.rmtree(appdata_dir, ignore_errors=True)

# ---- Regression: resolve_data_dir() must key off the ENTRY POINT, not off
# wherever its own source file happens to live. It used to derive the folder
# from its own __file__; when the function moved into noteorganizer/core/,
# that silently pointed two levels deeper and the app chose the wrong data
# folder (then migrated real notes into it). It now takes the directory as
# an argument, so moving the file again can't change the answer.
import inspect
_sig = inspect.signature(NO.resolve_data_dir)
check('resolve_data_dir takes the base directory as an argument',
      len(_sig.parameters) == 1)

_probe = tempfile.mkdtemp(prefix='qa_resolve_')
try:
    _resolved, _note = NO.resolve_data_dir(_probe)
    check('resolve_data_dir returns exactly the directory it was given',
          os.path.normcase(_resolved) == os.path.normcase(os.path.abspath(_probe)))
    check('...and reports no fallback warning for a writable directory',
          _note is None)
finally:
    shutil.rmtree(_probe, ignore_errors=True)

_p1 = tempfile.mkdtemp(prefix='qa_resolve_a_')
_p2 = tempfile.mkdtemp(prefix='qa_resolve_b_')
try:
    # Two different inputs must give two different answers — proof the result
    # follows the argument rather than any fixed location on disk.
    _r1, _ = NO.resolve_data_dir(_p1)
    _r2, _ = NO.resolve_data_dir(_p2)
    check('resolve_data_dir follows its argument, not a fixed location',
          os.path.normcase(_r1) == os.path.normcase(os.path.abspath(_p1))
          and os.path.normcase(_r2) == os.path.normcase(os.path.abspath(_p2))
          and _r1 != _r2)
finally:
    shutil.rmtree(_p1, ignore_errors=True)
    shutil.rmtree(_p2, ignore_errors=True)

# The app's own APP_DIR must sit beside note_organizer.py, not inside the
# noteorganizer/ package.
check('APP_DIR is not inside the noteorganizer package',
      'noteorganizer' not in os.path.normpath(NO.APP_DIR).split(os.sep)[-2:])

# ---- core/storage.load_notes + save_notes ----
#
# These were methods on the Tkinter class until they moved here, so this is
# the first coverage they have had that does not go through a window. Two
# things are worth pinning down beyond "it round-trips":
#
#   * load_notes takes version_change as an ARGUMENT. It used to read the
#     entry module's global, which is the value that silently goes missing
#     when the app runs as `py note_organizer.py` (the running copy is
#     __main__, so `import note_organizer` yields a second, uninitialised
#     module). Passing it in removes that whole class of bug.
#   * save_notes REPORTS failure instead of showing a dialog. Nothing in
#     core may touch the interface, so the caller decides what a failure
#     looks like on screen.
from noteorganizer.core import storage as _storage

_notes_dir = tempfile.mkdtemp()
_prev_paths = (NO_paths.DATA_FILE, NO_paths.SETTINGS_FILE)
try:
    NO_paths.configure(_notes_dir)
    with open(NO_paths.SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'cleanup_done': True}, f)
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump([{'id': 1, 'title': 'Kept'}], f)

    _loaded, _report = _storage.load_notes()
    check('load_notes reads the notes file', [n['title'] for n in _loaded] == ['Kept'])
    check('load_notes fills in missing fields via normalize_note',
          'attachments' in _loaded[0] and 'checklist' in _loaded[0])
    check('load_notes reports no backup when nothing special happened',
          _report == {'version_backup_path': None, 'cleanup_report': None})

    _loaded.append({'id': 2, 'title': 'Added'})
    _ok, _exc = _storage.save_notes(_loaded)
    check('save_notes reports success as (True, None)', (_ok, _exc) == (True, None))
    _again, _ = _storage.load_notes()
    check('what save_notes wrote is what load_notes reads back',
          [n['title'] for n in _again] == ['Kept', 'Added'])

    # An upgrade must snapshot the file before this version's code rewrites it.
    _before = len([f for f in os.listdir(_notes_dir) if f.startswith('notes_data_backup_')])
    _storage.load_notes(version_change=('up', '0.1.0', '0.2.0'))
    _after = len([f for f in os.listdir(_notes_dir) if f.startswith('notes_data_backup_')])
    check('load_notes backs the file up when told the app was upgraded', _after == _before + 1)

    _storage.load_notes(version_change=None)
    check('load_notes takes no backup when there was no version change',
          len([f for f in os.listdir(_notes_dir)
               if f.startswith('notes_data_backup_')]) == _after)

    # A write that cannot succeed must come back as a value, not a dialog and
    # not an exception -- the caller is what knows how to tell the user.
    NO_paths.DATA_FILE = os.path.join(_notes_dir, 'no_such_dir', 'notes_data.json')
    _ok2, _exc2 = _storage.save_notes([{'id': 1}])
    check('save_notes reports failure instead of raising', _ok2 is False)
    check('save_notes hands back the reason it failed', isinstance(_exc2, OSError))
finally:
    shutil.rmtree(_notes_dir, ignore_errors=True)
    NO_paths.DATA_FILE, NO_paths.SETTINGS_FILE = _prev_paths

# ---- the core layer stays free of the interface ----
#
# ARCHITECTURE.md has said "core must never import tkinter" since the split
# began, but nothing enforced it -- and the rule is what makes the data layer
# usable from anything: a test, a script, or a different front end. One
# stray import would take that away silently, so check it rather than trust it.
_core_dir = os.path.join(os.path.dirname(os.path.abspath(NO_paths.__file__)))
_core_modules = [f[:-3] for f in sorted(os.listdir(_core_dir))
                 if f.endswith('.py') and not f.startswith('__')]
check('every core module was found', len(_core_modules) >= 10)

_offenders = []
for _name in _core_modules:
    _src = open(os.path.join(_core_dir, _name + '.py'), encoding='utf-8').read()
    for _line in _src.split('\n'):
        _stripped = _line.strip()
        if _stripped.startswith(('import tkinter', 'from tkinter')):
            _offenders.append(f'{_name}.py: {_stripped}')
check('no core module imports tkinter', not _offenders, )
if _offenders:
    print('   offenders:', _offenders)

# ---- core/storage trash operations ----
#
# Delete and restore were methods on the app class and touched no interface,
# so this is their first coverage that does not open a window. The restore
# case worth pinning down is the orphan: a note whose category was deleted
# while it sat in the trash would otherwise come back filed under something
# that no longer exists.
_trash_dir = tempfile.mkdtemp()
_prev = (NO_paths.DATA_FILE, NO_paths.SETTINGS_FILE, NO_paths.TRASH_FILE)
try:
    NO_paths.configure(_trash_dir)
    with open(NO_paths.SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'cleanup_done': True}, f)

    _notes = [{'id': 1, 'title': 'Keep'}, {'id': 2, 'title': 'Bin', 'category': 'Gone'}]
    _trash = []
    _storage.move_notes_to_trash(_trash, [_notes[1]])
    check('move_notes_to_trash puts the note in the trash', len(_trash) == 1)
    check('move_notes_to_trash stamps a deletion time', bool(_trash[0].get('deleted_at')))
    check('move_notes_to_trash writes the trash file', os.path.exists(NO_paths.TRASH_FILE))

    check('days_left_in_trash counts from the stamp',
          _storage.days_left_in_trash(_trash[0]['deleted_at']) == NO.TRASH_RETENTION_DAYS)
    check('days_left_in_trash returns None for an unreadable stamp',
          _storage.days_left_in_trash('not a date') is None)
    check('days_left_in_trash returns None rather than raising on junk',
          _storage.days_left_in_trash(None) is None)

    _notes = [n for n in _notes if n['id'] != 2]
    # A note created AFTER the delete has taken the id the trashed one used.
    # Without this the id check cannot fail, which is exactly how the first
    # version of it passed against code that never reassigned an id at all.
    _notes.append({'id': 2, 'title': 'Made later'})
    _restored_from = dict(_trash[0])
    _notes, _trash = _storage.restore_from_trash(_notes, _trash, _trash[0])
    check('restore_from_trash puts the note back', len(_notes) == 3)
    check('restore_from_trash empties it out of the trash', _trash == [])
    check('a restored note whose category is gone falls back rather than orphaning',
          _notes[-1]['category'] == 'General')
    check('restore_from_trash gives the note an id that cannot collide',
          _notes[-1]['id'] not in [n['id'] for n in _notes[:-1]])
    check('...and specifically does not reuse the id it had when deleted',
          _notes[-1]['id'] != _restored_from['id'])
    check('restore_from_trash drops the deleted_at stamp',
          'deleted_at' not in _notes[-1])
finally:
    shutil.rmtree(_trash_dir, ignore_errors=True)
    NO_paths.DATA_FILE, NO_paths.SETTINGS_FILE, NO_paths.TRASH_FILE = _prev

# ---- core/model note lookups ----
#
# find_note, count_notes_in_category and rename_category_everywhere were
# methods on the app class and touch no interface. The case worth pinning
# down in all three is the per-occurrence override: a repeating note can
# carry a patch for one date that names a different category from the
# series, so anything that only looks at note["category"] gets it wrong --
# undercounting, or leaving a patch pointing at a name that is gone.
from noteorganizer.core.model import (
    find_note as _find_note,
    count_notes_in_category as _count_in_cat,
    rename_category_everywhere as _rename_cat,
)

_ln = [
    {'id': 1, 'title': 'plain', 'category': 'Work'},
    {'id': 2, 'title': 'series', 'category': 'Work',
     'overrides': {'2026-03-01': {'category': 'Urgent'},
                   '2026-03-08': {'category': 'Urgent'}}},
    {'id': 3, 'title': 'other', 'category': 'Home'},
]

check('find_note returns the matching note', _find_note(_ln, 2)['title'] == 'series')
check('find_note returns None for an id that is not there', _find_note(_ln, 99) is None)
check('find_note on an empty list returns None', _find_note([], 1) is None)

check('count_notes_in_category counts base categories', _count_in_cat(_ln, 'Work') == 2)
check('a note is counted once even with several overrides naming the category',
      _count_in_cat(_ln, 'Urgent') == 1)
check('count_notes_in_category returns 0 for an unused category',
      _count_in_cat(_ln, 'Nothing') == 0)

_rename_cat(_ln, 'Urgent', 'Later')
check('rename_category_everywhere leaves nothing under the old name',
      _count_in_cat(_ln, 'Urgent') == 0)
check('rename_category_everywhere rewrites per-occurrence overrides too',
      [p['category'] for p in _ln[1]['overrides'].values()] == ['Later', 'Later'])
_rename_cat(_ln, 'Work', 'Job')
check('rename_category_everywhere rewrites base categories',
      _count_in_cat(_ln, 'Job') == 2 and _count_in_cat(_ln, 'Work') == 0)
check('renaming leaves unrelated notes alone', _ln[2]['category'] == 'Home')

# ---- core/storage single-setting helpers ----
#
# Six methods were the same read-modify-write of one key. That shape is the
# point, not incidental: several parts of the app own different keys in one
# file, so writing the whole file from one caller's view of it would drop
# the others. The check below is exactly that property.
_set_dir = tempfile.mkdtemp()
_set_prev = (NO_paths.SETTINGS_FILE,)
try:
    NO_paths.configure(_set_dir)
    with open(NO_paths.SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'cleanup_done': True, 'username': 'Alexandra'}, f)

    _storage.save_setting('theme', 'dark_forest')
    check('save_setting stores the value', _storage.get_setting('theme') == 'dark_forest')
    check('save_setting leaves the other keys alone',
          _storage.get_setting('cleanup_done') is True
          and _storage.get_setting('username') == 'Alexandra')

    check('get_setting falls back when the key is missing',
          _storage.get_setting('nope', 'fallback') == 'fallback')
    _storage.save_setting('username', 12345)
    check('get_setting returns a wrong-typed value as-is without expect',
          _storage.get_setting('username') == 12345)
    check('get_setting falls back on a wrong type when expect is given',
          _storage.get_setting('username', '', expect=str) == '')
finally:
    shutil.rmtree(_set_dir, ignore_errors=True)
    NO_paths.SETTINGS_FILE, = _set_prev

# ---- core colour and tag-name helpers ----
#
# Pure functions that were staticmethods on the app class. The colour ones
# are checked against every colour in every theme rather than a sample,
# because the whole point of contrasting_fg is that it holds for all of them.
from noteorganizer.core.themes import blend as _blend_fn, contrasting_fg as _contrast
from noteorganizer.core.formatting import (
    char_class as _cc, color_tag_name as _ctn, font_tag_for as _ftf)

_all_colours = sorted({v for pal in NO.THEMES.values() for v in pal.values()
                       if isinstance(v, str) and v.startswith('#')})
check('every theme colour gets a legible contrasting foreground',
      all(_contrast(c) in ('#1a1a1a', '#ffffff') for c in _all_colours))
check('contrasting_fg picks dark text on a light ground', _contrast('#ffffff') == '#1a1a1a')
check('contrasting_fg picks light text on a dark ground', _contrast('#1e1e2f') == '#ffffff')

check('blend at t=0 returns the first colour', _blend_fn('#000000', '#ffffff', 0) == '#000000')
check('blend at t=1 returns the second colour', _blend_fn('#000000', '#ffffff', 1) == '#ffffff')
check('blend at t=0.5 lands halfway', _blend_fn('#000000', '#ffffff', 0.5) == '#808080')

check('char_class calls a letter a word character', _cc('a') == 'word')
check('char_class calls a space a space', _cc(' ') == 'space')
check('char_class puts punctuation in its own class so it breaks a word',
      _cc('.') == 'other')
check('char_class handles the empty string', _cc('') is None)

check('color_tag_name is stable and lowercase', _ctn('highlight', '#FFF3B0') == 'highlight_fff3b0')
check('font_tag_for gives bold+italic its own compound tag',
      _ftf(True, True) == 'bold_italic')
check('font_tag_for returns None when neither is set', _ftf(False, False) is None)

# --- the emoji that killed every save after it ---------------------------
# Tk stores text in UTF-16 and hands astral characters over as surrogate
# pairs. json.dump cannot encode those, and the old except clause caught
# only I/O errors -- so the exception flew past it, autosave crash-logged
# sixteen times in a row, and every edit after the first emoji lived only
# in the running app. Saving now recombines pairs into the real character,
# replaces lone surrogates, reports any other failure instead of raising,
# and removes the half-written .tmp it would otherwise leave behind.
from noteorganizer.core import storage as _storage
from noteorganizer.core import paths as _paths

# Earlier sections re-point the data paths at their own temp dirs; this one
# depends on nothing they left behind and says so by pointing at the cwd
# itself, the same way initialise() does at startup.
_paths.DATA_FILE = os.path.join(os.getcwd(), "notes_data.json")

_pair = chr(0xD83D) + chr(0xDE00)          # what Tk gives for U+1F600
_ok, _exc = _storage.save_notes(
    [{"id": 991, "title": "x " + _pair + " y", "body": ""}])
check("a surrogate-pair emoji no longer kills the save", _ok and _exc is None)
import json as _json
_back = _json.load(open(_paths.DATA_FILE, encoding="utf-8"))
check("and it lands as the real character, not the pair",
      chr(0x1F600) in _back[0]["title"] and len(_back[0]["title"]) == 5)
check("no half-written .tmp is left beside the file",
      not os.path.exists(_paths.DATA_FILE + ".tmp"))

_ok2, _exc2 = _storage.save_notes([{"id": 992, "title": "l " + chr(0xD83D)}])
_back2 = _json.load(open(_paths.DATA_FILE, encoding="utf-8"))
check("a lone surrogate is replaced rather than poisoning the file",
      _ok2 and chr(0xFFFD) in _back2[0]["title"])

_ok3, _exc3 = _storage.save_notes([{"id": 993, "bad": {1, 2}}])
check("an unserializable note reports (False, exc) instead of raising",
      _ok3 is False and isinstance(_exc3, TypeError))
check("and cleans up its .tmp too",
      not os.path.exists(_paths.DATA_FILE + ".tmp"))
_storage.save_notes([])

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
