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

# Restore rule for every configure() section below: capture the previous
# APP_DIR and configure() back to it in the finally. Hand-restoring a
# subset of the path globals (the old way) left the OTHER paths pointing
# into the deleted temp dir — the same "a list of fields exempts the
# next field" trap the Issues Log tells about, in path form; every
# section appended after the leak inherited ghost paths.
_notes_dir = tempfile.mkdtemp()
_prev_app_dir = NO_paths.APP_DIR
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
          # All-falsy rather than an exact dict: an exact shape breaks the
          # moment the report gains a key, without testing anything more.
          not any(_report.values()))

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
    NO_paths.configure(_prev_app_dir)

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
_prev_app_dir = NO_paths.APP_DIR
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
    NO_paths.configure(_prev_app_dir)

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
_prev_app_dir = NO_paths.APP_DIR
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
    NO_paths.configure(_prev_app_dir)

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

# ---- Purge deletes the files of what it purges ----
# "Files that outlived the notes they belonged to" (ISSUES_LOG): the
# startup purge is the ONE automatic permanent deletion, so it must not
# be the one place that leaves orphaned attachment files behind. The
# old-teeth audit (2026-08-31) found nothing pinned this -- removing
# the deletion call left every suite green.
import datetime as _dtT
os.makedirs(_paths.ATTACHMENTS_DIR, exist_ok=True)
_old_att = os.path.join(_paths.ATTACHMENTS_DIR, "teeth_old.bin")
_new_att = os.path.join(_paths.ATTACHMENTS_DIR, "teeth_new.bin")
with open(_old_att, "w") as _f:
    _f.write("x")
with open(_new_att, "w") as _f:
    _f.write("x")
_stampO = (_dtT.datetime.now()
           - _dtT.timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
_stampN = _dtT.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
_keptT, _nT = _storage.purge_expired_trash([
    {"id": 1, "deleted_at": _stampO,
     "attachments": [{"stored_as": "teeth_old.bin"}]},
    {"id": 2, "deleted_at": _stampN,
     "attachments": [{"stored_as": "teeth_new.bin"}]},
])
check("purge removes the expired entry and keeps the fresh one",
      _nT == 1 and len(_keptT) == 1 and _keptT[0]["id"] == 2)
check("purge permanently deletes the expired entry's attachment file",
      not os.path.exists(_old_att))
check("while the kept entry's file is untouched",
      os.path.exists(_new_att))
os.remove(_new_att)

# ---- Attachment deletion can't escape the attachments folder ----
# A crafted share code (or hand-edited data) could carry an attachment
# whose stored_as is "../../file" — permanent deletion used to join it
# onto ATTACHMENTS_DIR and remove whatever it pointed at. The path
# guard keeps every delete inside the folder; a legit filename still
# deletes.
_outside = os.path.join(os.path.dirname(_paths.ATTACHMENTS_DIR),
                        "precious_outsider.txt")
with open(_outside, "w") as _f:
    _f.write("do not delete me")
_inside = os.path.join(_paths.ATTACHMENTS_DIR, "legit_att.bin")
with open(_inside, "w") as _f:
    _f.write("x")
_rel = os.path.relpath(_outside, _paths.ATTACHMENTS_DIR)  # e.g. "..\precious..."
_storage._delete_attachment_files([
    {"attachments": [{"stored_as": _rel},
                     {"stored_as": "legit_att.bin"}]}])
check("a traversal stored_as cannot delete a file outside attachments/",
      os.path.exists(_outside))
check("a legit attachment filename is still deleted",
      not os.path.exists(_inside))
check("_attachment_path_within rejects traversal, accepts a bare name",
      _storage._attachment_path_within(_rel) is None
      and _storage._attachment_path_within("legit_att.bin") is not None)
# The guard's invariant, stated platform-independently: on any crafted
# stored_as it must NEVER raise, and must NEVER return a path OUTSIDE
# the attachments folder. It MAY return a valid contained path for a
# value that doesn't actually escape on this OS (e.g. "C:\x" is a
# drive path on Windows but a plain filename on Linux) — that's correct,
# not a leak. Asserting a fixed None result here was the bug: it made
# the check platform-dependent and it failed on Linux CI.
_base_real = os.path.realpath(_paths.ATTACHMENTS_DIR)
_guard_ok = True
for _bad in ("C:\\Windows\\System32\\x", "\\\\server\\share\\x",
             "Z:relative", "x\x00y", "..", ".", "../../out",
             _rel):  # _rel genuinely escapes on every platform
    try:
        _r = _storage._attachment_path_within(_bad)
    except Exception:
        _guard_ok = False  # a raise is the launch-blocker we're guarding against
        continue
    if _r is not None:
        # returned a path -> it must be inside the attachments folder
        try:
            if os.path.commonpath([_base_real, _r]) != _base_real:
                _guard_ok = False
        except ValueError:
            _guard_ok = False
# And the values that escape on EVERY platform must resolve to None.
if _storage._attachment_path_within(_rel) is not None:
    _guard_ok = False
if _storage._attachment_path_within("../../out") is not None:
    _guard_ok = False
check("the path guard never raises and never returns a path outside the folder",
      _guard_ok)
# And normalize_note flattens a smuggled path to a bare filename at the
# data choke point, closing traversal for every channel (share + zip +
# hand-edit), not only the sinks.
from noteorganizer.core.model import normalize_note as _nn_att
_flat = _nn_att({"id": 1, "title": "x", "attachments": [
    {"filename": "doc.pdf", "stored_as": "../../evil.exe"},
    {"filename": "y", "stored_as": "C:\\Windows\\z"},
    "not-a-dict"]})
check("normalize_note reduces every attachment stored_as to a bare name",
      [a["stored_as"] for a in _flat["attachments"]] == ["evil.exe", "z"])
# Defensive: under a mutant that breaks the guard the outsider is gone,
# and a bare remove would crash the run before its footer. The checks
# already recorded their verdicts; this only lets the suite finish.
if os.path.exists(_outside):
    os.remove(_outside)

# ---- Duplicating a note gives the copy its OWN attachment files ----
# A plain deep-copy shared the original's stored_as (same files on disk);
# permanently deleting either note then removed the file the other still
# referenced -- silent attachment loss (audit Z01-F04). copy_attachment_file
# hands the copy fresh files.
os.makedirs(_paths.ATTACHMENTS_DIR, exist_ok=True)
_dup_src = os.path.join(_paths.ATTACHMENTS_DIR, "20260101_shared.bin")
with open(_dup_src, "w") as _f:
    _f.write("shared bytes")
_fresh = _storage.copy_attachment_file("20260101_shared.bin")
check("copy_attachment_file returns a NEW distinct name",
      _fresh is not None and _fresh != "20260101_shared.bin"
      and os.path.isfile(os.path.join(_paths.ATTACHMENTS_DIR, _fresh)))
# Deleting the copy's file leaves the original's file intact.
_storage._delete_attachment_files([{"attachments": [{"stored_as": _fresh}]}])
check("deleting the copy's attachment file leaves the original's intact",
      os.path.isfile(_dup_src)
      and not os.path.isfile(os.path.join(_paths.ATTACHMENTS_DIR, _fresh)))
# A missing source yields None (caller keeps the old ref, no crash).
check("copy_attachment_file returns None for a missing source",
      _storage.copy_attachment_file("does_not_exist.bin") is None)
# Defensive: a mutant sharing the file deletes _dup_src above, so a bare
# remove would crash the run before its footer. Verdicts already recorded.
if os.path.exists(_dup_src):
    os.remove(_dup_src)

# ---- The atomic-write family: every data file saves the safe way ----
# trash/templates/settings once wrote with a bare open('w'): an emoji
# with a lone surrogate raised UnicodeEncodeError mid-dump and left the
# file truncated, and a crash mid-write truncated it too. They all
# route through _write_json_atomic now — proven here by the two
# failure modes that used to bite, plus the corrupt-load preserve.

_astral = "note \U0001F600 with a lone \ud83d surrogate half"


def _no_raise(fn):
    """True if the call completed. The naive writers this section guards
    against RAISED mid-dump (that was half the bug) — a mutant bringing
    them back must turn into FAIL lines, not a crashed suite."""
    try:
        fn()
        return True
    except Exception:
        return False


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None  # unreadable/truncated -> the check comparing it fails


_okT = _no_raise(lambda: _storage.save_trash(
    [{"id": 1, "title": _astral, "deleted_at": "2026-01-01 00:00:00"}]))
_trS = _read_json(_paths.TRASH_FILE)
check("save_trash survives astral + lone-surrogate text as valid JSON",
      _okT and isinstance(_trS, list) and len(_trS) == 1
      and "\U0001F600" in _trS[0]["title"])

_okP = _no_raise(lambda: _storage.save_templates(
    [{"name": _astral, "title": "", "body": ""}]))
_tpS = _read_json(_paths.TEMPLATES_FILE)
check("save_templates survives astral + lone-surrogate text",
      _okP and isinstance(_tpS, list) and len(_tpS) == 1
      and "\U0001F600" in _tpS[0]["name"])

_setS = _storage.load_settings()
_setS["username"] = _astral
_okS = _no_raise(lambda: _storage.save_settings(_setS))
check("save_settings survives astral + lone-surrogate text",
      _okS and "\U0001F600" in _storage.load_settings().get("username", ""))

# A dump that fails midway must neither raise nor leave a damaged file.
_storage.save_trash([{"id": 2, "title": "survivor"}])
with open(_paths.TRASH_FILE, encoding="utf-8") as _f:
    _beforeT = _f.read()
_okF = _no_raise(lambda: _storage.save_trash(
    [{"id": 3, "bad": {1, 2}}]))  # a set: json.dump raises mid-write
with open(_paths.TRASH_FILE, encoding="utf-8") as _f:
    _afterT = _f.read()
check("a failed trash write neither raises nor touches the previous file",
      _okF and _beforeT == _afterT)
check("and leaves no .tmp litter behind",
      not os.path.exists(_paths.TRASH_FILE + ".tmp"))

# ---- Corrupt loads preserve the original bytes before falling back ----
with open(_paths.TRASH_FILE, "w", encoding="utf-8") as _f:
    _f.write('{"broken": [')
_trC = _storage.load_trash()
_corrT = [p for p in os.listdir(_paths.APP_DIR)
          if p.startswith("trash_corrupt_")]
check("corrupt trash.json -> empty list plus a preserved copy",
      _trC == [] and len(_corrT) >= 1)
check("the preserved trash copy holds the original bytes",
      bool(_corrT) and open(os.path.join(_paths.APP_DIR, _corrT[0]),
                            encoding="utf-8").read() == '{"broken": [')

with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    _f.write("not json at all")
_notesC, _reportC = _storage.load_notes(None)
_corrN = [os.path.join(_paths.APP_DIR, p) for p in os.listdir(_paths.APP_DIR)
          if p.startswith("notes_data_corrupt_")]
check("corrupt notes_data.json -> empty list, flag set, copy preserved",
      _notesC == [] and _reportC["notes_file_corrupt"]
      and _reportC["corrupt_backup_path"] in _corrN)
check("the preserved notes copy holds the original bytes",
      bool(_reportC["corrupt_backup_path"])
      and os.path.isfile(_reportC["corrupt_backup_path"])
      and open(_reportC["corrupt_backup_path"], encoding="utf-8").read()
      == "not json at all")

# A wrong-shape file (valid JSON, but not a list) counts as corrupt too —
# it would be silently emptied just the same.
with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    _f.write('{"i am": "a dict"}')
_notesW, _reportW = _storage.load_notes(None)
check("a wrong-shape notes file is treated as corrupt, not silently emptied",
      _notesW == [] and _reportW["notes_file_corrupt"])

# A list whose entries are ALL junk is the same loss in another costume —
# the outer bracket being right must not let it slip past the net.
with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    _f.write('["x", 3, null]')
_notesJ, _reportJ = _storage.load_notes(None)
check("an all-junk list notes file is treated as corrupt too",
      _notesJ == [] and _reportJ["notes_file_corrupt"]
      and bool(_reportJ["corrupt_backup_path"]))

with open(_paths.TEMPLATES_FILE, "w", encoding="utf-8") as _f:
    _f.write('["junk"]')
_tpJ = _storage.load_templates()
check("an all-junk templates file is preserved before falling back",
      _tpJ == [] and any(p.startswith("templates_corrupt_")
                         for p in os.listdir(_paths.APP_DIR)))

# On a corrupt launch the one-time cleanup must NOT rewrite the notes
# file — when even the preserve failed, that rewrite would destroy the
# last copy of the user's bytes while the startup notice still points
# at them.
_setC = _storage.load_settings()
_had_cleanup = _setC.pop("cleanup_done", None)
_storage.save_settings(_setC)
with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    _f.write("still not json")
_notesG, _reportG = _storage.load_notes(None)
with open(_paths.DATA_FILE, encoding="utf-8") as _f:
    _stillG = _f.read()
check("the one-time cleanup is gated off on a corrupt launch",
      _reportG["notes_file_corrupt"] and _stillG == "still not json")
_setC["cleanup_done"] = True if _had_cleanup is None else _had_cleanup
_storage.save_settings(_setC)

# The cleanup rewrite itself must write the safe way: a lone-surrogate
# escape in stored JSON parses into an unencodable string, and a naive
# rewrite would raise (and truncate) where the atomic one mends and
# completes.
_setK = _storage.load_settings()
_had_cleanup2 = _setK.pop("cleanup_done", None)
_storage.save_settings(_setK)
with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    _f.write('[{"id": 1, "title": "lone \\ud83d half"}]')
_okK = _no_raise(lambda: _storage.load_notes(None))
_dataK = _read_json(_paths.DATA_FILE)
check("the cleanup rewrite mends surrogates and completes atomically",
      _okK and isinstance(_dataK, list) and len(_dataK) == 1)
_setK = _storage.load_settings()
_setK["cleanup_done"] = True
_storage.save_settings(_setK)

# The two loaders without a corrupt fixture yet: settings (unparsable)
# and trash (wrong shape). Content-matched rather than counted, so a
# same-second timestamp collision cannot fake a pass or a fail.
with open(_paths.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    _f.write("{broken settings")
_setP = _storage.load_settings()
check("corrupt settings.json -> empty dict plus a preserved copy",
      _setP == {} and any(
          open(os.path.join(_paths.APP_DIR, p), encoding="utf-8").read()
          == "{broken settings"
          for p in os.listdir(_paths.APP_DIR)
          if p.startswith("settings_corrupt_")))
_storage.save_settings({"cleanup_done": True})  # heal for what follows

with open(_paths.TRASH_FILE, "w", encoding="utf-8") as _f:
    _f.write('{"wrong": "shape"}')
_trW = _storage.load_trash()
check("a wrong-shape trash.json is preserved before falling back",
      _trW == [] and any(
          open(os.path.join(_paths.APP_DIR, p), encoding="utf-8").read()
          == '{"wrong": "shape"}'
          for p in os.listdir(_paths.APP_DIR)
          if p.startswith("trash_corrupt_")))

# ---- The reclaim migration preserves a corrupt settings.json ----
# run_migrations used to clobber an unreadable settings file with the
# %APPDATA% copy, no trace kept — and its marker write was the last
# naive (non-atomic) data-file writer in the codebase.
_mig_app = tempfile.mkdtemp()
_mig_appdata = tempfile.mkdtemp()
_real_gad_mig = NO_paths.get_appdata_dir
try:
    NO_paths.get_appdata_dir = lambda: _mig_appdata
    with open(os.path.join(_mig_appdata, "notes_data.json"), "w", encoding="utf-8") as _f:
        json.dump([{"id": 1, "title": "AppData note"}], _f)
    with open(os.path.join(_mig_appdata, "settings.json"), "w", encoding="utf-8") as _f:
        json.dump({"theme": "dark"}, _f)
    with open(os.path.join(_mig_app, "settings.json"), "w", encoding="utf-8") as _f:
        _f.write("{corrupt settings")

    _mig_msg = NO.run_migrations(_mig_app)
    _mig_kept = [p for p in os.listdir(_mig_app)
                 if p.startswith("settings_corrupt_")]
    check("the reclaim migration preserves an unreadable settings.json first",
          _mig_msg is not None and len(_mig_kept) == 1)
    check("the preserved settings copy holds the original bytes",
          bool(_mig_kept)
          and open(os.path.join(_mig_app, _mig_kept[0]),
                   encoding="utf-8").read() == "{corrupt settings")
    with open(os.path.join(_mig_app, "settings.json"), encoding="utf-8") as _f:
        _mig_set = json.load(_f)
    check("the reclaim marker still lands in a valid settings file",
          _mig_set.get("reclaimed_from_appdata") is True)
finally:
    NO_paths.get_appdata_dir = _real_gad_mig
    shutil.rmtree(_mig_app, ignore_errors=True)
    shutil.rmtree(_mig_appdata, ignore_errors=True)

# ---- Silent write failures now leave a trace (audit Z01-F06/Z02-F03) ----
# save_trash/save_templates/save_settings dropped _write_json_atomic's
# verdict, so a failed write was invisible: no return, no log, no
# callback — while save_notes had been explicitly reworked to report.
# Each sibling now returns (ok, exc) the same way, and every failure
# lands in crash_log.txt and reaches the on_write_failure callback.
_wf_dir = tempfile.mkdtemp()
_real_wf_trash = NO_paths.TRASH_FILE
_real_wf_templates = NO_paths.TEMPLATES_FILE
_real_wf_settings = NO_paths.SETTINGS_FILE
_real_wf_appdir = NO_paths.APP_DIR
_real_wf_cb = _storage.on_write_failure
_wf_calls = []
try:
    NO_paths.APP_DIR = _wf_dir
    _storage.on_write_failure = lambda path, exc: _wf_calls.append(str(path))

    NO_paths.TRASH_FILE = os.path.join(_wf_dir, "trash.json")
    NO_paths.TEMPLATES_FILE = os.path.join(_wf_dir, "templates.json")
    NO_paths.SETTINGS_FILE = os.path.join(_wf_dir, "settings.json")
    check("save_trash reports success the way save_notes does",
          _storage.save_trash([]) == (True, None))
    check("save_templates and save_settings report success too",
          _storage.save_templates([]) == (True, None)
          and _storage.save_settings({}) == (True, None))
    check("a clean write fires no failure callback", _wf_calls == [])

    NO_paths.TRASH_FILE = os.path.join(_wf_dir, "no_such_dir", "trash.json")
    # Guarded unpack: under the dropped-return mutant this is None, and a
    # bare unpack would crash the suite before its footer.
    _wf_res = _storage.save_trash([])
    _wf_ok, _wf_exc = _wf_res if isinstance(_wf_res, tuple) else (None, None)
    check("a failed trash write returns the reason instead of silence",
          _wf_ok is False and _wf_exc is not None)
    _wf_log = os.path.join(_wf_dir, "crash_log.txt")
    check("the failed write lands in crash_log.txt",
          os.path.exists(_wf_log)
          and "write failure" in open(_wf_log, encoding="utf-8").read())
    check("the failed write reaches the on_write_failure callback",
          len(_wf_calls) == 1 and "trash.json" in _wf_calls[0])
    _storage.on_write_failure = lambda *a: (_ for _ in ()).throw(RuntimeError)
    _wf_res2 = _storage.save_trash([])
    check("a broken callback cannot take down the save path itself",
          isinstance(_wf_res2, tuple) and _wf_res2[0] is False)
finally:
    NO_paths.TRASH_FILE = _real_wf_trash
    NO_paths.TEMPLATES_FILE = _real_wf_templates
    NO_paths.SETTINGS_FILE = _real_wf_settings
    NO_paths.APP_DIR = _real_wf_appdir
    _storage.on_write_failure = _real_wf_cb
    shutil.rmtree(_wf_dir, ignore_errors=True)

# ---- The one-time cleanup must not delete real notes (product review T0-1) ----
# note_is_empty decides what the cleanup DESTROYS, so it has to mean the
# same thing by "content" as the editor does. It counted title/body/
# comments/attachments only, while save_current_note happily saves a note
# that is nothing but a checklist -- so the app created notes its own
# cleanup then deleted, with no Trash and no undo.
_model = NO
check("a checklist-only note is not 'empty'",
      not _model.note_is_empty({"title": "", "body": "", "comments": "",
                                "attachments": [],
                                "checklist": [{"text": "milk", "done": False}]}))
check("a repeating note with no text is not 'empty' either",
      not _model.note_is_empty({"title": "", "body": "", "comments": "",
                                "attachments": [], "checklist": [],
                                "recurrence": {"freq": "weekly"}}))
check("a dated note with no text is not 'empty' either",
      not _model.note_is_empty({"title": "", "body": "", "comments": "",
                                "attachments": [], "checklist": [],
                                "date": "2026-07-01"}))
check("a genuinely blank note still is",
      _model.note_is_empty({"title": "  ", "body": "", "comments": "",
                            "attachments": [], "checklist": []}))

# ...and two notes that differ only in what is TICKED are two notes.
_dup_a = _model.normalize_note({"id": 1, "title": "Groceries", "body": "",
                                "checklist": [{"text": "milk", "done": True}]})
_dup_b = _model.normalize_note({"id": 2, "title": "Groceries", "body": "",
                                "checklist": [{"text": "milk", "done": False}]})
_cleaned, _stats = _model.clean_notes([_dup_a, _dup_b])
check("notes differing only by their checklist are not merged away",
      len(_cleaned) == 2 and _stats["duplicates_removed"] == 0)
_same_a = _model.normalize_note({"id": 1, "title": "Same", "body": "x"})
_same_b = _model.normalize_note({"id": 2, "title": "Same", "body": "x"})
check("genuinely identical notes still collapse",
      len(_model.clean_notes([_same_a, _same_b])[0]) == 1)

# ---- A pasted share code cannot make a note that kills the app (T0-7) ----
# Every checklist item becomes four widgets at render time and nothing
# capped the count: 20,000 items is a 60KB code that passes every decoder
# guard, and the app never starts again once the note is saved.
_bomb = _model.normalize_note(
    {"id": 1, "title": "bomb",
     "checklist": [{"text": "x", "done": False}] * 20000})
check("normalize_note caps the checklist at the data choke point",
      len(_bomb["checklist"]) == _model.MAX_CHECKLIST_ITEMS)
check("and the cap is far above any real list",
      _model.MAX_CHECKLIST_ITEMS >= 500)

# ---- The rescue copy survives a restart (T0-6) ----
# _prev is written to disk by the save that shrank the note, but was not
# in the schema -- so the next launch discarded it while the button still
# offered to restore from it.
_with_prev = _model.normalize_note(
    {"id": 1, "title": "t", "body": "short",
     "_prev": {"title": "t", "body": "the long original text",
               "comments": "", "formatting": [], "paragraphs": []}})
check("normalize_note carries the restore-previous copy through",
      _with_prev.get("_prev", {}).get("body") == "the long original text")
check("a junk _prev is dropped rather than trusted",
      "_prev" not in _model.normalize_note({"id": 1, "_prev": "nonsense"}))

# ---- One malformed id cannot break every "new note" forever ----
# id was the single field normalize_note passed through untouched, so a
# hand-edited or foreign notes_data.json broke max([n["id"]...]) + 1 on
# every route that makes a note.
check("a string id is coerced to an int",
      _model.normalize_note({"id": "7"})["id"] == 7)
check("an unusable id falls back to 0 instead of poisoning the list",
      _model.normalize_note({"id": ["nope"]})["id"] == 0
      and _model.normalize_note({"id": None})["id"] == 0)
_mixed = [_model.normalize_note({"id": "3", "title": "a"}),
          _model.normalize_note({"id": 5, "title": "b"})]
check("so the next-id arithmetic still works on a repaired list",
      max(n["id"] for n in _mixed) + 1 == 6)

# ---- One notebook, one app (product review T0-2) ----
# Two windows on the same data directory each hold their own copy of the
# whole notebook, and every save rewrites the file wholesale -- so the
# second one to autosave silently deletes everything the first wrote.
# The guard is an OS file lock, which the kernel releases however the
# process dies, so a crash can never lock a user out of their own notes.
import subprocess as _sp
from noteorganizer.core import single_instance as _si

_lock_dir = tempfile.mkdtemp()
_lock_path = os.path.join(_lock_dir, "notebook.lock")
_PROBE = (
    "import sys; sys.path.insert(0, %r);"
    "from noteorganizer.core import single_instance as si;"
    "print('GOT' if si.acquire(%r) else 'BLOCKED')"
    % (os.path.dirname(os.path.abspath(__file__)), _lock_path))


def _other_process_can_take_it():
    out = _sp.run([sys.executable, "-c", _PROBE], capture_output=True,
                  text=True, cwd=_lock_dir)
    return "GOT" in out.stdout


try:
    check("a second process is refused while the first holds the notebook",
          _si.acquire(_lock_path) is True
          and _other_process_can_take_it() is False)
    check("the holder knows it holds it", _si.held() is True)
    check("taking it twice in one process is fine (qa builds several apps)",
          _si.acquire(_lock_path) is True)
    # Guarded: a release that leaves the handle behind blows up on the
    # SECOND release (seek on a closed file), and a mutant must fail a
    # check rather than take the suite down before its footer.
    try:
        _si.release()
        _released_cleanly = True
    except Exception:
        _released_cleanly = False
    check("releasing hands it straight over -- no stale lock to strand anyone",
          _released_cleanly and _other_process_can_take_it() is True)
    check("and the holder knows it let go",
          _released_cleanly and _si.held() is False)
    # The LOCKING call's failure mode, separately from open()'s: a
    # filesystem that cannot do byte-range locks answers the lock call
    # with EINVAL/ENOLCK/EOPNOTSUPP, and reading that as "already open"
    # bricked the app on exactly those folders (adversarial review,
    # reinstated by the completeness critic after the wave misjudged it).
    # Only the someone-holds-it errnos may refuse.
    import errno as _errno
    import noteorganizer.core.single_instance as _si_mod

    def _acquire_with_lock_error(err):
        if os.name == "nt":
            import msvcrt as _lockmod
            attr = "locking"
        else:
            import fcntl as _lockmod
            attr = "flock"
        real = getattr(_lockmod, attr)

        def _boom(*a, **k):
            raise OSError(err, "synthetic lock failure")

        setattr(_lockmod, attr, _boom)
        try:
            got = _si_mod.acquire(os.path.join(_lock_dir, "errno_probe.lock"))
        finally:
            setattr(_lockmod, attr, real)
            try:
                _si_mod.release()
            except Exception:
                pass
        return got

    check("a filesystem that cannot lock at all fails OPEN, not closed",
          _acquire_with_lock_error(_errno.EINVAL) is True
          and _acquire_with_lock_error(_errno.ENOSYS) is True)
    check("while a lock genuinely held elsewhere still refuses",
          _acquire_with_lock_error(_errno.EACCES) is False
          and _acquire_with_lock_error(_errno.EAGAIN) is False)

    # A lock that cannot be created must never stop the app from starting:
    # refusing to open because a LOCK failed is worse than what it guards.
    check("an uncreatable lock file reports success rather than blocking",
          _si.acquire(os.path.join(_lock_dir, "no_such_dir", "x.lock")) is True)
    try:
        _si.release()
    except Exception:
        pass
finally:
    try:
        _si.release()
    except Exception:
        pass
    shutil.rmtree(_lock_dir, ignore_errors=True)

# ---- ONE content signature, every consumer (T0-1 swept to its class) ----
# The dedup fixed its field list and the stale-copy purge -- which gates
# an irreversible os.remove of a whole legacy notebook folder -- kept the
# old five-field tuple, so notes differing only by checklist still read
# as "fully covered" and were deleted. The fix is a single definition in
# model.content_signature; these assert both the behaviour AND the
# delegation, so the two can never drift apart silently again.
from noteorganizer.core import paths as _paths_mod
from noteorganizer.core import model as _model_mod
from noteorganizer.core.duplicates import find_duplicate_groups as _fdg

_base = {"title": "", "body": "", "comments": "", "category": "General",
         "date": "", "formatting": [], "paragraphs": [], "attachments": []}
_ck_milk = dict(_base, checklist=[{"text": "milk", "done": False}])
_ck_gym = dict(_base, checklist=[{"text": "gym kit", "done": False}])

check("checklist-differing notes carry different content signatures",
      _model_mod.content_signature(_ck_milk)
      != _model_mod.content_signature(_ck_gym))


def _legacy_file(notes):
    fd, p = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        _json.dump(notes, f)
    return p


_lf_both = _legacy_file([_ck_milk, _ck_gym])
_lf_gym = _legacy_file([_ck_gym])
try:
    check("the purge no longer reads a checklist-differing folder as covered",
          _paths_mod.is_redundant_copy(_lf_both, [_ck_gym]) is False)
    check("a genuinely covered folder still purges (the feature survives)",
          _paths_mod.is_redundant_copy(_lf_gym, [_ck_gym, _ck_milk]) is True)

    # The delegation itself: bend the single definition and the purge's
    # answer must bend with it. The fixtures DIFFER IN TITLE on purpose:
    # a private (title, body, ...) copy answers False for them no matter
    # what model says, while the bent shared signature collapses them to
    # True -- so only genuine delegation can pass. (The first version of
    # this check used title-less fixtures a private copy also collapsed,
    # and the drift mutant survived it.)
    _ta = _legacy_file([dict(_base, title="UnTitlu")])
    _real_sig = _model_mod.content_signature
    try:
        _model_mod.content_signature = lambda n, strict=False: ("bent",)
        check("the purge consults model.content_signature, not a private copy",
              _paths_mod.is_redundant_copy(_ta, [dict(_base, title="AltTitlu")])
              is True)
    finally:
        _model_mod.content_signature = _real_sig
        try:
            os.remove(_ta)
        except OSError:
            pass
finally:
    for _p in (_lf_both, _lf_gym):
        try:
            os.remove(_p)
        except OSError:
            pass

# The purge asks a STRICTER question than the duplicate collapse, and
# the difference is written down rather than drifting: styling, layout,
# per-day edits and skipped dates are real work that does not show up in
# the default signature, so a leftover notebook differing only in those
# was judged "already covered" and deleted -- while the startup message
# promised nothing was deleted unless it already existed locally.
_fmt_a = dict(_base, title="Acelasi", body="text",
              formatting=[{"start": 0, "end": 4, "style": "bold"}])
_fmt_b = dict(_base, title="Acelasi", body="text")
check("styling does NOT split a duplicate for the startup collapse",
      _model_mod.content_signature(_fmt_a)
      == _model_mod.content_signature(_fmt_b))
check("but it DOES for the purge, whose wrong answer is unrecoverable",
      _model_mod.content_signature(_fmt_a, strict=True)
      != _model_mod.content_signature(_fmt_b, strict=True))
for _field, _value in (("paragraphs", [{"line": 0, "kind": "bullet"}]),
                       ("overrides", {"2026-01-01": {"title": "zi"}}),
                       ("exceptions", ["2026-01-02"])):
    check("the strict answer also sees %s" % _field,
          _model_mod.content_signature(dict(_fmt_b, **{_field: _value}),
                                       strict=True)
          != _model_mod.content_signature(_fmt_b, strict=True))
_lf_fmt = _legacy_file([_fmt_a])
try:
    check("a folder differing only in styling is NOT purged",
          _paths_mod.is_redundant_copy(_lf_fmt, [_fmt_b]) is False)
    check("...while a genuinely identical one still is",
          _paths_mod.is_redundant_copy(_lf_fmt, [_fmt_a]) is True)
finally:
    try:
        os.remove(_lf_fmt)
    except OSError:
        pass
# Raw shapes off disk must never raise inside the signature: the purge
# feeds it dicts parsed straight from a file, before any normalization,
# and an exception there would abort a startup.
check("the strict signature tolerates raw junk shapes",
      _model_mod.content_signature(
          {"formatting": {"a": [1, {"b": None}]}, "overrides": 7,
           "exceptions": "nope", "paragraphs": object()},
          strict=True) is not None)

# Find-duplicates and the import scans share _dup_key; checklist and
# recurrence joined its key (they are never merged, so a grouping there
# destroys whichever copy is dropped), attachments deliberately did NOT
# (cleanup hands the kept note the group's combined files).
_t1 = dict(_base, title="Cumparaturi", checklist=[{"text": "milk", "done": False}])
_t2 = dict(_base, title="Cumparaturi", checklist=[{"text": "gym", "done": False}])
check("different checklists keep two same-text notes apart",
      _fdg([_t1, _t2]) == [])
_r1 = dict(_base, title="Sport", date="2026-01-01",
           recurrence={"freq": "weekly", "weekdays": [0]})
_r2 = dict(_base, title="Sport", date="2026-01-01", recurrence={})
check("a repeat rule keeps a series apart from its one-off twin",
      _fdg([_r1, _r2]) == [])
_a1 = dict(_base, title="Acte", attachments=[{"stored_as": "a.pdf"}])
_a2 = dict(_base, title="Acte", attachments=[{"stored_as": "b.pdf"}])
check('a repeat rule signs by MEANING, not representation',
      _model_mod._recurrence_signature({}) == ()
      and _model_mod._recurrence_signature(
          _model_mod.normalize_recurrence({})) == ()
      and _model_mod._recurrence_signature({'freq': 'weekly'})
      == _model_mod._recurrence_signature(
          _model_mod.normalize_recurrence({'freq': 'weekly'})))
check("attachment-differing copies still group (cleanup merges files)",
      len(_fdg([_a1, _a2])) == 1)
_i1 = dict(_base, title="Idem", checklist=[{"text": "x", "done": True}])
_i2 = dict(_base, title="Idem (copy)",
           checklist=[{"text": "x", "done": True}])
check("true duplicates still group, ' (copy)' suffix ignored",
      len(_fdg([_i1, _i2])) == 1)

# ---- The category door has ceilings, like its siblings ----
# The category map arrives from settings.json and from any imported
# backup, and the sidebar builds a widget per entry with the name drawn
# in full -- so it is the same unbounded-field class as the checklist and
# the attachment list, through a door that had no limit at all.
from noteorganizer.core import categories as _cats_mod
from noteorganizer.core.storage import save_settings as _save_settings
_cat_backup = dict(_cats_mod.CATEGORY_COLORS)
_settings_backup = _storage.load_settings()
try:
    _save_settings(dict(_settings_backup, categories={
        ("Cat%04d" % i): "#112233"
        for i in range(_cats_mod.MAX_CATEGORIES + 150)}))
    _loaded = _cats_mod.load_categories()
    check("a settings file full of categories is capped on load",
          len(_loaded) <= _cats_mod.MAX_CATEGORIES + 1)  # +1: General
    _save_settings(dict(_settings_backup,
                        categories={"N" * 5000: "#112233"}))
    _loaded2 = _cats_mod.load_categories()
    # DROPPED, not truncated: a count can be capped by shortening the
    # list, but a NAME is an identifier -- shortening it meant every note
    # filed under the full name no longer matched a category that
    # existed, and normalize_note re-filed them all to General.
    # "dropped" means ABSENT, not shortened. Asserting the full 5000-char
    # prefix is missing would pass for a truncated name too, which is the
    # exact failure this check exists to catch -- so it asserts that no
    # key derived from that name survives at all.
    check("an absurdly long category name is dropped, not silently renamed",
          not any(n.startswith("NNNN") for n in _loaded2))
    _save_settings(dict(_settings_backup,
                        categories={"Proiecte": "#112233"}))
    check("...while an ordinary name is kept exactly as written",
          "Proiecte" in _cats_mod.load_categories())
finally:
    _save_settings(_settings_backup)
    _cats_mod.CATEGORY_COLORS.clear()
    _cats_mod.CATEGORY_COLORS.update(_cat_backup)

# ---- Colours are validated where they enter (the T0-7 class, colour
# door) ----
# A colour string ends its journey inside a Tk configure(), which raises
# on garbage -- and a note is SAVED before it is first drawn, so one bad
# value used to crash every launch after. sanitize_color guards the note
# field, the category import and the calendar day map.
from noteorganizer.core.model import sanitize_color as _sc
check("sanitize_color passes real colours and both hex widths",
      _sc("#A1B2C3") == "#A1B2C3" and _sc("#abc") == "#abc"
      and _sc(" #ff0000 ") == "#ff0000")
check("sanitize_color refuses everything Tk would choke on",
      _sc("#zzz123") == "" and _sc("red)") == "" and _sc(123) == ""
      and _sc(None) == "" and _sc("#12345") == ""
      and _sc("#ff0000; rm") == "")
check("normalize_note strips an undrawable note colour",
      _nn_att({"color": "#nope!!"})["color"] == ""
      and _nn_att({"color": "#00ff00"})["color"] == "#00ff00")

# ---- The bomb ceilings swept to the sibling fields (T0-7 class) ----
from noteorganizer.core.storage import normalize_template as _nt
from noteorganizer.core.formatting import (normalize_formatting as _nf,
                                           MAX_FORMATTING_SPANS as _MFS)
from noteorganizer.core.model import MAX_ATTACHMENTS as _MA
_big_tpl = _nt({"name": "b",
                "checklist": [{"text": str(i)} for i in range(3000)]})
check("a template's checklist meets the same 1000-item ceiling",
      len(_big_tpl["checklist"]) == 1000)
# templates.json is hand-editable, and the cap's slice raises on a
# dict-shaped value: what used to degrade to an empty checklist would
# have crashed startup instead.
# Guarded: the defect under test is a CRASH, so calling it unguarded
# takes the suite down before its FAILURES footer -- which reads as
# "survived nothing" instead of a red.
def _tpl_degrades(value):
    try:
        return _nt({"name": "b", "checklist": value})["checklist"] == []
    except Exception:
        return False


check("a malformed template checklist degrades instead of crashing",
      _tpl_degrades({"a": 1}) and _tpl_degrades("nope")
      and _tpl_degrades(7))
_big_fmt = _nf([{"start": i, "end": i + 1, "style": "bold"}
                for i in range(_MFS + 5000)])
check("formatting spans meet their anti-bomb ceiling",
      len(_big_fmt) == _MFS)
# ---- The cleanup renumbers IDs; the remembered note must follow ----
# Coverage-ledger C17, which was recorded as a suspicion and turned out
# to be real. The one-time cleanup renumbers every note from 1 and saves
# settings in the same breath, so a last_open_note_id left alone stops
# meaning the note it was written for. Two shapes, and the second is the
# one that matters: the number can survive and point somewhere else.
_c17_notes_path = _storage.paths.DATA_FILE
_c17_settings_path = _storage.paths.SETTINGS_FILE
_c17_saved = [p + ".c17bak" for p in (_c17_notes_path, _c17_settings_path)]
for _src, _dst in zip((_c17_notes_path, _c17_settings_path), _c17_saved):
    if os.path.exists(_src):
        shutil.copy2(_src, _dst)


def _c17_note(nid, title, body):
    return {"id": nid, "title": title, "body": body, "category": "General",
            "created": "2026-01-01 00:00", "updated": "2026-01-01 00:00"}


def _c17_run(notes, remembered):
    """Drive the one-time cleanup over this notebook, return what the app
    would open next launch: (settings' id, that note's title or None)."""
    open(_c17_notes_path, "w", encoding="utf-8").write(
        json.dumps(notes))
    open(_c17_settings_path, "w", encoding="utf-8").write(json.dumps(
        {"reclaimed_from_appdata": True, "last_open_note_id": remembered}))
    cleaned, _ = _storage.load_notes()
    after = _storage.load_settings()
    now = after.get("last_open_note_id")
    match = next((n for n in cleaned if n["id"] == now), None)
    return now, (match["title"] if match else None)


# The severe shape: one empty note in front, so every ID shifts down by
# one and the remembered number stays VALID -- pointing at the note that
# used to sit after the one being read.
_c17_id, _c17_title = _c17_run([
    _c17_note(1, "", ""),
    _c17_note(2, "The one they were reading", "real content"),
    _c17_note(3, "A completely different note", "someone else's"),
], remembered=2)
check("the remembered note follows the note through an ID renumber, "
      "not the number", _c17_title == "The one they were reading")

# The mild shape: the remembered note is renumbered to something that no
# longer exists. Opening nothing is correct; opening a stranger is not.
_c17_id2, _c17_title2 = _c17_run([
    _c17_note(1, "", ""),
    _c17_note(2, "", ""),
    _c17_note(3, "The one they were reading", "real content"),
], remembered=3)
check("...and it is found again even when its number vanished entirely",
      _c17_title2 == "The one they were reading")

# A remembered note the cleanup REMOVES has nothing to point at, and the
# setting must say so rather than aim at whoever took its number.
_c17_id3, _c17_title3 = _c17_run([
    _c17_note(1, "", ""),
    _c17_note(2, "A note that stays", "content"),
], remembered=1)
check("a remembered note that the cleanup removed leaves nothing behind, "
      "not someone else's note", _c17_id3 is None and _c17_title3 is None)

# A notebook with nothing to clean must not disturb the setting at all.
_c17_id4, _c17_title4 = _c17_run([
    _c17_note(1, "First", "content"),
    _c17_note(2, "Second", "more content"),
], remembered=2)
check("and a notebook with nothing to clean leaves the remembered note "
      "exactly where it was", _c17_id4 == 2 and _c17_title4 == "Second")

for _src, _dst in zip(_c17_saved, (_c17_notes_path, _c17_settings_path)):
    if os.path.exists(_src):
        shutil.copy2(_src, _dst)
        os.remove(_src)

# ---- The styling bomb the SPAN ceiling waves through (per line) ----
# MAX_FORMATTING_SPANS counts a whole note and sits at 10,000 on purpose,
# so it is not the defence here: what stops Tk finishing a draw is how
# many tagged ranges land on ONE LINE, and two shapes get there while
# staying far under 10,000 spans. Both were measured against the real
# editor and both failed to finish in 75 seconds; a pasted note is saved
# before it is ever drawn, so either one made the app unopenable on every
# launch after -- the checklist bomb, one field over.
from noteorganizer.core.formatting import (MAX_SPANS_PER_LINE as _MSPL,
                                           MAX_LINE_RANGES as _MLR)

_one_line = "x" * 9000
_pile = _nn_att({"title": "x", "body": _one_line,
                 "formatting": [{"start": (3 * i) % 8000,
                                 "end": (3 * i) % 8000 + 2,
                                 "style": "highlight",
                                 "value": "#%06x" % (i * 4001 % 0xffffff)}
                                for i in range(2000)]})
check("2,000 styling spans piled on one line are cut to the line ceiling",
      len(_pile["formatting"]) == _MSPL)
check("...and that is well under the span ceiling that was meant to "
      "cover it", 2000 < _MFS)

# The shape that walked through the first version of this clamp: no line
# has many spans STARTING on it, yet the last line wears all of them.
_many = "\n".join("abcdefghij" for _ in range(400))
_offs, _o = [], 0
for _ln_ in _many.split("\n"):
    _offs.append(_o)
    _o += len(_ln_) + 1
_reach = _nn_att({"title": "x", "body": _many,
                  "formatting": [{"start": _offs[i % 400], "end": len(_many),
                                  "style": "highlight",
                                  "value": "#%06x" % (i * 4001 % 0xffffff)}
                                 for i in range(2000)]})
_drawn = sum(sp["end"] > sp["start"] and
             _many.count("\n", sp["start"], sp["end"]) + 1
             for sp in _reach["formatting"])
check("spans that each run to the end of the note are cut by what they "
      "would DRAW, not by how many there are", _drawn <= _MLR)
check("...and only five of them ever started on any one line, so the "
      "per-line count alone would have let them through",
      max(sum(1 for sp in _reach["formatting"] if sp["start"] == _offs[i])
          for i in range(400)) <= 5)

# The asymmetry that matters more than either: a real note is UNTOUCHED.
# Not "roughly the same length" -- identical, span for span. A ceiling
# that quietly edits ordinary notes is worse than the bomb it stops.
_real_spans = [{"start": _offs[i], "end": _offs[i] + 5, "style": "bold"}
               for i in range(300)]
_real = _nn_att({"title": "x", "body": _many,
                 "formatting": [dict(sp) for sp in _real_spans]})
check("300 bold words across 300 lines pass through unchanged",
      _real["formatting"] == _real_spans)
_para_spans = [{"start": 3 * i, "end": 3 * i + 2, "style": "bold"}
               for i in range(_MSPL)]
_para = _nn_att({"title": "x", "body": _one_line,
                 "formatting": [dict(sp) for sp in _para_spans]})
check("a densely styled paragraph right AT the ceiling is untouched too",
      _para["formatting"] == _para_spans)

# Every door into the editor, not just the note one. A template is
# applied straight into the body widget and never meets normalize_note --
# which is exactly how the checklist bomb got a second life.
from noteorganizer.core.storage import normalize_template as _nt
_tpl_bomb = _nt({"name": "t", "body": _one_line,
                 "formatting": [{"start": (3 * i) % 8000,
                                 "end": (3 * i) % 8000 + 2,
                                 "style": "highlight",
                                 "value": "#%06x" % (i * 4001 % 0xffffff)}
                                for i in range(2000)]})
check("a template meets the same per-line ceiling a note does",
      len(_tpl_bomb["formatting"]) == _MSPL)
# "Restore previous version" is the third door: it puts stored spans
# straight back into the editor without passing the note's own field.
_prev_bomb = _nn_att({"title": "x", "body": "y", "_prev": {
    "title": "x", "body": _one_line, "comments": "",
    "formatting": [{"start": (3 * i) % 8000, "end": (3 * i) % 8000 + 2,
                    "style": "highlight",
                    "value": "#%06x" % (i * 4001 % 0xffffff)}
                   for i in range(2000)],
    "paragraphs": []}})
check("so does the previous version a note carries for its restore button",
      len(_prev_bomb["_prev"]["formatting"]) == _MSPL)

_big_att = _nn_att({"title": "x", "attachments": [
    {"stored_as": "f%d.txt" % i} for i in range(_MA + 300)]})
check("attachment records meet their ceiling",
      len(_big_att["attachments"]) == _MA)
_dirty_att = _nn_att({"title": "x", "attachments": [
    {"stored_as": "evil.lnk. "}, {"no_names_at_all": 1},
    {"filename": "doc.pdf", "stored_as": "doc.pdf"}]})
check("stored names lose their trailing-dot disguise at the choke point",
      _dirty_att["attachments"][0]["stored_as"] == "evil.lnk"
      and _dirty_att["attachments"][0]["filename"] == "evil.lnk")
check("a record naming no file at all is dropped, not crashed on",
      len(_dirty_att["attachments"]) == 2)

_MAIN_GUARD_DRIVER = '"""Drive the REAL _main() with the heavy parts stubbed to recorders.\n\nWritten and launched by test_data_safety to prove the single-instance\nguard is WIRED, not merely implemented: _main must consult acquire() and\nhonour the answer. The adversarial review caught the gap this closes --\ndeleting the whole guard from _main left every suite green, because the\nlock primitive was tested end-to-end while the one call site a user ever\ntravels through was tested by nobody.\n"""\nimport json\nimport os\nimport sys\n\nHERE = os.path.dirname(os.path.abspath(__file__))\nos.chdir(HERE)\nsys.path.insert(0, HERE)\n\n# Hermetic seed BEFORE the note_organizer import: the module resolves its\n# data directory and runs migrations at import time, and an unseeded dir\n# invites the adoption of the machine\'s real notebook.\nif not os.path.exists("notes_data.json"):\n    with open("notes_data.json", "w", encoding="utf-8") as f:\n        f.write("[]")\ntry:\n    with open("settings.json", "r", encoding="utf-8") as f:\n        _settings = json.load(f)\nexcept Exception:\n    _settings = {}\nif not isinstance(_settings, dict):\n    _settings = {}\n_settings.setdefault("reclaimed_from_appdata", True)\nwith open("settings.json", "w", encoding="utf-8") as f:\n    json.dump(_settings, f)\n\nimport tkinter.messagebox as mb  # noqa: E402\n\nimport note_organizer as NO  # noqa: E402\nfrom noteorganizer.core import paths  # noqa: E402\n\nevents = []\nNO.initialise = lambda: (paths.configure(HERE), events.append("init"))\n_real_acquire = NO.single_instance.acquire\n\n\ndef _recording_acquire(path=None):\n    events.append("acquire")\n    return _real_acquire(path)\n\n\nNO.single_instance.acquire = _recording_acquire\n\n\nclass FakeApp:\n    def __init__(self):\n        events.append("app")\n\n    def protocol(self, *a, **k):\n        pass\n\n    def on_app_close(self):\n        pass\n\n    def mainloop(self):\n        events.append("loop")\n\n\nclass FakeRoot:\n    def withdraw(self):\n        pass\n\n    def destroy(self):\n        pass\n\n\nNO.NoteOrganizer = FakeApp\nNO.tk.Tk = FakeRoot\nmb.showinfo = lambda *a, **k: events.append("refused-dialog")\n\nNO._main()\nprint("EVENTS:" + json.dumps(events))\n'

# ---- The guard is WIRED, not merely implemented ----
# The primitive above is proven end-to-end; this proves _main() actually
# consults it and honours the answer. Without this, deleting the whole
# guard from _main left every suite green (adversarial review, 2026-09-11)
# -- the classic tested-library-untested-call-site gap, on the one call
# site a user ever travels through.
_driver_path = os.path.join(os.getcwd(), "_main_guard_driver.py")
with open(_driver_path, "w", encoding="utf-8") as _f:
    _f.write(_MAIN_GUARD_DRIVER)


def _run_main_driver():
    out = _sp.run([sys.executable, _driver_path], capture_output=True,
                  text=True, cwd=os.getcwd(), timeout=120)
    for line in (out.stdout or "").splitlines():
        if line.startswith("EVENTS:"):
            try:
                return json.loads(line[len("EVENTS:"):])
            except ValueError:
                break
    return ["driver-broke", (out.stdout or "")[-300:], (out.stderr or "")[-300:]]


try:
    _got_lock = _si.acquire(os.path.join(os.getcwd(), ".notebook.lock"))
    _ev_held = _run_main_driver()
    check("holding the notebook makes _main refuse: dialog shown, no app built",
          _got_lock and "refused-dialog" in _ev_held
          and "app" not in _ev_held)
    # ...and it refuses BEFORE touching the shared folder. initialise()
    # migrates files out of older locations, purges stale copies and
    # consumes the one-shot pre-upgrade backup -- all of which a second
    # launch used to do to the FIRST instance's notebook on its way to
    # being told no.
    check("and it refuses before initialise touches the shared folder",
          "init" not in _ev_held and _ev_held[:1] == ["acquire"])
    try:
        _si.release()
    except Exception:
        pass
    _ev_free = _run_main_driver()
    check("with the notebook free, the same gate lets _main build the app",
          "app" in _ev_free and "loop" in _ev_free
          and "refused-dialog" not in _ev_free)
    # index() raises when a step is MISSING, and a missing step is exactly
    # what the mutant for this produces -- a crash here would take the
    # suite down before its FAILURES footer, which reads as "survived
    # nothing" instead of a red.
    def _order_ok(events, *steps):
        try:
            spots = [events.index(s) for s in steps]
        except ValueError:
            return False
        return spots == sorted(spots)

    check("...and only then does the startup work happen, in that order",
          _order_ok(_ev_free, "acquire", "init", "app"))
finally:
    try:
        _si.release()
    except Exception:
        pass
    for _leftover in (_driver_path,
                      os.path.join(os.getcwd(), ".notebook.lock")):
        try:
            os.remove(_leftover)
        except OSError:
            pass

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
