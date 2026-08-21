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

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
