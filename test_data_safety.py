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
import glob
import json
import shutil
import tempfile
# The suites' shared support (its guest step and its seed): beside this file
# in a scratch copy, in qa/ in the repository, where CI runs it.
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa"))
import _qa_support  # noqa: E402
# ---- REFUSE TO RUN BESIDE REAL NOTES ----
# This file deletes and rewrites the notebook the app opens, and files in
# its working folder. Run from the project root it destroyed the real
# notebook once, despite the warning above being here the whole time. A
# warning depends on being read; this check does not.
#
# It is the qa scripts' own guard (qa/_qa_support.hermetic_seed), not a
# copy: only where a throwaway folder has been declared (NOTEORG_SCRATCH=1,
# set by the runners and CI, or by hand in a scratch copy), failing CLOSED beside a notebook it
# cannot prove empty, and only where the folder the app will open, asked of
# its own resolver, is the working folder. The copy that was here looked
# beside the test while the app opened the folder notebook_location.txt
# names -- in the owner's checkout, her notebook.
# It seeds that folder: an empty notebook and the reclaim marker. Unseeded,
# the migration copied whatever notebook %APPDATA% held into this folder --
# the built app's, the owner's -- on every Windows run.
def _guard_real_notes():
    _qa_support.hermetic_seed()


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
# (see CLAUDE.md's "QA testing safety"); the guard above has seeded the very
# folder initialise() opens, and made sure no notes were there.
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

# On a full disk the copy stopped partway and left a cut-off file under the
# backup's name, the update's notice said nothing of it, and the one-time
# cleanup went ahead with no copy at all.
from noteorganizer.core import storage as _bk_storage
with open(NO.DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump([{'id': 1, 'title': 'Real note', 'body': 'x'},
               {'id': 2, 'title': '', 'body': ''}], f)
_bk_settings = _bk_storage.load_settings()
_bk_storage.save_settings({k: v for k, v in _bk_settings.items() if k != 'cleanup_done'})
_bk_copy2 = _bk_storage.shutil.copy2


def _bk_full(src, dst, *a, **k):
    with open(dst, 'w') as f:
        f.write('[{"id": 1, "ti')
    raise OSError(28, 'No space left on device')


_bk_storage.shutil.copy2 = _bk_full
try:
    _bk_none = NO.backup_notes_file()
    _bk_left = [n for n in os.listdir(os.path.dirname(os.path.abspath(NO.DATA_FILE)))
                if n.startswith('notes_data_backup_')]
    _bk_notes, _bk_report = _bk_storage.load_notes(('up', '0.1.0', '0.2.0'))
finally:
    _bk_storage.shutil.copy2 = _bk_copy2
check(f'a backup the disk cannot hold leaves no cut-off file under its name ({_bk_left})',
      _bk_none is None and not _bk_left)
check('...the load after an update says the safety copy could not be made',
      _bk_report.get('version_backup_failed') is True)
check('...and the one-time cleanup waits for a launch that can keep a copy',
      _bk_report.get('cleanup_report') is None and len(_bk_notes) == 2
      and not _bk_storage.load_settings().get('cleanup_done'))
_bk_storage.save_settings(_bk_settings)
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

# ---- run_migrations(): Case 1 replaces a READABLE settings.json too ----
# The module's rule is that nothing is overwritten without a copy first;
# the reclaim kept an unreadable settings.json aside but wrote over a
# readable one -- this folder's categories and choices -- with no copy.
for _rs_backup_fails in (False, True):
    _rs_app = tempfile.mkdtemp()
    _rs_old = tempfile.mkdtemp()
    try:
        NO_paths.get_appdata_dir = lambda: _rs_old
        with open(os.path.join(_rs_old, 'notes_data.json'), 'w', encoding='utf-8') as f:
            json.dump([{'id': 1, 'title': 'AppData note'}], f)
        with open(os.path.join(_rs_old, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'categories': ['From AppData']}, f)
        _rs_set = os.path.join(_rs_app, 'settings.json')
        with open(_rs_set, 'w', encoding='utf-8') as f:
            json.dump({'categories': ['Local only']}, f)
        _rs_copy2 = shutil.copy2
        def _rs_failing(src, dst):
            if _rs_backup_fails and src == _rs_set:
                raise OSError('simulated backup failure')
            return _rs_copy2(src, dst)
        shutil.copy2 = _rs_failing
        try:
            _rs_msg = NO.run_migrations(_rs_app)
        finally:
            shutil.copy2 = _rs_copy2
        with open(_rs_set, encoding='utf-8') as f:
            _rs_now = json.load(f)
        _rs_kept = [n for n in os.listdir(_rs_app) if n.startswith('settings_replaced_')]
        _rs_held = ([json.load(open(os.path.join(_rs_app, n), encoding='utf-8'))
                     for n in _rs_kept])
        with open(os.path.join(_rs_app, 'notes_data.json'), encoding='utf-8') as f:
            _rs_notes = json.load(f)
        check('the reclaim brings the notes in (settings backup fails: %s)' % _rs_backup_fails,
              _rs_msg is not None and _rs_notes[0]['title'] == 'AppData note')
        check('nothing half-copied is left behind (%s)' % _rs_backup_fails,
              not [n for n in os.listdir(_rs_app) if n.endswith('.part')])
        if _rs_backup_fails:
            check('a readable settings.json that could not be copied aside stays',
                  _rs_now.get('categories') == ['Local only'] and not _rs_kept)
        else:
            check('a readable settings.json is copied aside before it is replaced',
                  _rs_held == [{'categories': ['Local only']}])
            check('...and the reclaimed settings take its place',
                  _rs_now.get('categories') == ['From AppData']
                  and _rs_now.get('reclaimed_from_appdata') is True)
    finally:
        NO_paths.get_appdata_dir = real_get_appdata_dir
        shutil.rmtree(_rs_app, ignore_errors=True)
        shutil.rmtree(_rs_old, ignore_errors=True)

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

# ---- notebook_location.txt: a source run's notebook kept elsewhere ----
# A notebook_location.txt beside the entry point names the folder a source
# run keeps its notebook in -- the developer's own, out of the working tree.
# A scratch copy of the code has no such file, so every test keeps its own.
_NL = chr(10)
_loc_script = tempfile.mkdtemp(prefix='qa_loc_script_')
_loc_parent = tempfile.mkdtemp(prefix='qa_loc_target_')
_loc_target = os.path.join(_loc_parent, 'notebook')
try:
    _r, _w = NO.resolve_data_dir(_loc_script)
    check('without notebook_location.txt a source run keeps its notebook '
          'beside the script, as before',
          os.path.normcase(_r) == os.path.normcase(_loc_script) and _w is None)
    os.environ['NOTEORG_TEST_LOC'] = _loc_target
    with open(os.path.join(_loc_script, 'notebook_location.txt'), 'w',
              encoding='utf-8') as f:
        f.write('# my own notebook, out of the repo' + _NL + _NL
                + '$NOTEORG_TEST_LOC' + _NL)
    _r, _w = NO.resolve_data_dir(_loc_script)
    check('notebook_location.txt names the folder: comments skipped, '
          'variables expanded, the folder made',
          os.path.normcase(_r) == os.path.normcase(_loc_target) and _w is None
          and os.path.isdir(_loc_target))
    _blocker = os.path.join(_loc_script, 'a_file')
    with open(_blocker, 'w', encoding='utf-8') as f:
        f.write('x')
    with open(os.path.join(_loc_script, 'notebook_location.txt'), 'w',
              encoding='utf-8') as f:
        f.write(os.path.join(_blocker, 'cannot_be_a_folder') + _NL)
    _r, _w = NO.resolve_data_dir(_loc_script)
    check('a folder it cannot use falls back beside the script, with a '
          'warning that names the file',
          os.path.normcase(_r) == os.path.normcase(_loc_script)
          and bool(_w) and 'notebook_location.txt' in _w)
finally:
    os.environ.pop('NOTEORG_TEST_LOC', None)
    shutil.rmtree(_loc_script, ignore_errors=True)
    shutil.rmtree(_loc_parent, ignore_errors=True)

# The folder it names is the notebook, and nothing is brought into it: an
# empty one would otherwise copy in whatever notebook %APPDATA% holds --
# the .exe's, the real one. In a process of its own (initialise runs once),
# against a stand-in APPDATA; the control without the file shows the copy
# this test would see if it happened.
import subprocess as _subprocess
_mig_root = tempfile.mkdtemp(prefix='qa_loc_mig_')
try:
    _fake_appdata = os.path.join(_mig_root, 'appdata')
    os.makedirs(os.path.join(_fake_appdata, 'NoteOrganizer'))
    with open(os.path.join(_fake_appdata, 'NoteOrganizer', 'notes_data.json'),
              'w', encoding='utf-8') as f:
        json.dump([{'id': 1, 'title': 'The exe notebook'}], f)
    _here = os.path.dirname(os.path.abspath(__file__))

    def _start(script_dir):
        code = ('import sys, os, json; sys.path.insert(0, %r); '
                'import note_organizer as NO; NO.initialise(app_dir=%r); '
                'print(json.dumps([NO.APP_DIR, NO.MIGRATION_INFO is not None, '
                'os.path.exists(os.path.join(NO.APP_DIR, "notes_data.json"))]))'
                % (_here, script_dir))
        env = dict(os.environ, APPDATA=_fake_appdata,
                   XDG_DATA_HOME=_fake_appdata)
        run = _subprocess.run([sys.executable, '-c', code], env=env,
                              capture_output=True, text=True, timeout=120)
        lines = run.stdout.strip().splitlines()
        return json.loads(lines[-1]) if lines else None

    _plain = os.path.join(_mig_root, 'plain')
    os.makedirs(_plain)
    _control = _start(_plain)
    _located = os.path.join(_mig_root, 'located')
    _chosen = os.path.join(_mig_root, 'chosen')
    os.makedirs(_located)
    with open(os.path.join(_located, 'notebook_location.txt'), 'w',
              encoding='utf-8') as f:
        f.write(_chosen + _NL)
    _moved = _start(_located)
    check(f'(control) without the file, an empty folder copies in the '
          f'notebook APPDATA holds ({_control})',
          _control is not None and _control[1] and _control[2])
    check(f'the folder notebook_location.txt names brings nothing in, and '
          f'starts empty ({_moved})',
          _moved is not None
          and os.path.normcase(_moved[0]) == os.path.normcase(_chosen)
          and not _moved[1] and not _moved[2])
finally:
    shutil.rmtree(_mig_root, ignore_errors=True)

# ---- The built app keeps its notebook in the profile, beside Documents ----
# Installed from the Store it runs as an MSIX package, and what it creates
# in AppData goes to the package's private copy, which uninstalling deletes
# (2026-10-27). Played here with sys.frozen set and a stand-in profile, so
# nothing reaches the real one.
_pr_root = tempfile.mkdtemp(prefix='qa_profile_')
_pr_env = {k: os.environ.get(k) for k in ('USERPROFILE', 'APPDATA', 'XDG_DATA_HOME')}
_pr_frozen = getattr(sys, 'frozen', None)
try:
    _pr_user = os.path.join(_pr_root, 'user')
    os.environ['USERPROFILE'] = _pr_user
    os.environ['APPDATA'] = os.path.join(_pr_user, 'AppData', 'Roaming')
    os.environ['XDG_DATA_HOME'] = os.environ['APPDATA']
    sys.frozen = True
    _pr_home = NO_paths.get_user_notebook_dir()
    _pr_old = NO_paths.get_appdata_dir()
    if os.name != 'nt':
        check('elsewhere than Windows, the built app keeps the AppData equivalent',
              _pr_home == _pr_old)
    else:
        check('the built app keeps its notebook in the profile, beside Documents',
              os.path.normcase(NO_paths.resolve_data_dir(os.path.dirname(
                  os.path.abspath(__file__)))[0])
              == os.path.normcase(os.path.join(_pr_user, 'Note Organizer')))
        # An older .exe's notebook in AppData is brought in: copied, never moved.
        os.makedirs(os.path.join(_pr_old, 'attachments'))
        _pr_notes = [{'id': 1, 'uid': 'pr-1', 'title': 'From the old exe', 'body': 'a'},
                     {'id': 2, 'uid': 'pr-2', 'title': 'Second', 'body': 'b'}]
        with open(os.path.join(_pr_old, 'notes_data.json'), 'w', encoding='utf-8') as f:
            json.dump(_pr_notes, f)
        with open(os.path.join(_pr_old, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'app_version': '0.97.405', 'theme': 'dark'}, f)
        with open(os.path.join(_pr_old, 'attachments', 'pr_file.bin'), 'w') as f:
            f.write('x')
        with open(os.path.join(_pr_old, 'trash.json'), 'w', encoding='utf-8') as f:
            json.dump([{'id': 9, 'uid': 'pr-t', 'title': 'In the old Trash',
                        'deleted_at': '2026-10-20 09:00:00'}], f)
        with open(os.path.join(_pr_old, 'templates.json'), 'w', encoding='utf-8') as f:
            json.dump([{'name': 'Old template', 'title': '', 'body': 'x'}], f)
        with open(os.path.join(_pr_old, 'notes_data.json'), 'rb') as f:
            _pr_bytes = f.read()
        os.makedirs(_pr_home, exist_ok=True)
        # The first start killed mid-copy (a reboot, Task Manager): the notes
        # file is written last, so the next start copies again rather than
        # keeping notes whose files never came.
        _pr_copy2 = NO_paths.shutil.copy2

        def _pr_killed(src, dst, *a, **k):
            if src.endswith('pr_file.bin'):
                open(dst, 'w').close()   # the copy cut short where it was going
                raise SystemExit('killed mid-copy')
            return _pr_copy2(src, dst, *a, **k)
        NO_paths.shutil.copy2 = _pr_killed
        try:
            NO_paths.run_migrations(_pr_home)
        except SystemExit:
            pass
        finally:
            NO_paths.shutil.copy2 = _pr_copy2
        check('a first start killed while copying files leaves no notes file to mark it done',
              not os.path.exists(os.path.join(_pr_home, 'notes_data.json'))
              and not os.path.exists(os.path.join(_pr_home, 'attachments', 'pr_file.bin')))
        _pr_msg = NO_paths.run_migrations(_pr_home) or ''
        check(f"the first start brings the old exe's notebook in, its file too ({_pr_msg[:60]!r})",
              NO_paths.count_notes_in(os.path.join(_pr_home, 'notes_data.json')) == 2
              and os.path.exists(os.path.join(_pr_home, 'attachments', 'pr_file.bin'))
              and open(os.path.join(_pr_home, 'attachments', 'pr_file.bin')).read() == 'x')
        check('...says the notebook in AppData is kept',
              'kept as it was' in _pr_msg)
        check('...and brings its Trash and templates too, not only the notes',
              all(os.path.exists(os.path.join(_pr_home, n))
                  and open(os.path.join(_pr_home, n), 'rb').read()
                  == open(os.path.join(_pr_old, n), 'rb').read()
                  for n in ('trash.json', 'templates.json')))
        with open(os.path.join(_pr_old, 'notes_data.json'), 'rb') as f:
            _pr_after = f.read()
        NO_paths.purge_stale_copies(_pr_home)
        check('...and leaves it exactly as it was, a cleanup after it too',
              _pr_after == _pr_bytes
              and os.path.exists(os.path.join(_pr_old, 'notes_data.json'))
              and os.path.exists(os.path.join(_pr_old, 'attachments', 'pr_file.bin')))
        # An older exe run again writes to AppData; its notebook must never
        # take the place of the notes written since in the profile.
        with open(os.path.join(_pr_home, 'notes_data.json'), 'w', encoding='utf-8') as f:
            json.dump(_pr_notes + [{'id': 3, 'uid': 'pr-3', 'title': 'Written since'}], f)
        with open(os.path.join(_pr_home, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'app_version': '0.97.405'}, f)
        NO_paths.run_migrations(_pr_home)
        check("a notebook the built app has is never replaced by AppData's",
              NO_paths.count_notes_in(os.path.join(_pr_home, 'notes_data.json')) == 3
              and not any(n.startswith('notes_data_replaced_')
                          for n in os.listdir(_pr_home)))
        # A profile that cannot be written: AppData, said out loud, with
        # the one thing that can take it there -- the Store's uninstall.
        _pr_writable = NO_paths._is_writable
        NO_paths._is_writable = lambda folder: (
            os.path.normcase(folder) != os.path.normcase(_pr_home)
            and _pr_writable(folder))
        try:
            _pr_fall = NO_paths.resolve_data_dir(os.path.dirname(os.path.abspath(__file__)))
        finally:
            NO_paths._is_writable = _pr_writable
        check(f'an unwritable profile falls back to AppData, with a warning ({str(_pr_fall[1])[:50]!r})',
              os.path.normcase(_pr_fall[0]) == os.path.normcase(_pr_old)
              and _pr_fall[1] is not None and 'backup' in _pr_fall[1].lower())
        # A FILE where the folder goes: said as that, with what cures it --
        # the message used to blame a profile that could not be written.
        _pf_user = os.path.join(_pr_root, 'user_file')
        os.environ['USERPROFILE'] = _pf_user
        os.environ['APPDATA'] = os.path.join(_pf_user, 'AppData', 'Roaming')
        os.makedirs(_pf_user)
        with open(NO_paths.get_user_notebook_dir(), 'w') as f:
            f.write('not a folder')
        _pf_fall = NO_paths.resolve_data_dir(os.path.dirname(os.path.abspath(__file__)))
        check(f'a file in the notes folder\'s place is named as the cause ({str(_pf_fall[1])[:60]!r})',
              'file named' in (_pf_fall[1] or '') and 'Rename' in (_pf_fall[1] or ''))
        os.environ['USERPROFILE'] = _pr_user
        os.environ['APPDATA'] = os.path.join(_pr_user, 'AppData', 'Roaming')
        # An old notebook with no notes left (all in the Trash) or one that
        # cannot be read is still the old app's notebook: it used to be
        # passed over, its Trash and templates with it, and a welcome note
        # then ended every later attempt.
        for _pe_how, _pe_notes in (('empty', '[]'), ('unreadable', '{ broken')):
            _pe_user = os.path.join(_pr_root, 'user_' + _pe_how)
            os.environ['USERPROFILE'] = _pe_user
            os.environ['APPDATA'] = os.path.join(_pe_user, 'AppData', 'Roaming')
            _pe_old, _pe_home = NO_paths.get_appdata_dir(), NO_paths.get_user_notebook_dir()
            os.makedirs(_pe_old)
            os.makedirs(_pe_home)
            for _pe_name, _pe_text in (('notes_data.json', _pe_notes),
                                       ('settings.json', '{ not json'),
                                       ('trash.json', '[{"id": 5, "title": "Binned",'
                                                      ' "deleted_at": "2026-10-20 09:00:00"}]'),
                                       ('templates.json', '[{"name": "Kept"}]')):
                with open(os.path.join(_pe_old, _pe_name), 'w', encoding='utf-8') as f:
                    f.write(_pe_text)
            _pe_msg = NO_paths.run_migrations(_pe_home) or ''
            check(f'an {_pe_how} old notebook is brought in with its Trash and templates '
                  f'({_pe_msg[:40]!r})',
                  all(os.path.exists(os.path.join(_pe_home, n))
                      for n in ('notes_data.json', 'trash.json', 'templates.json'))
                  and 'Brought in' in _pe_msg)
            # Its settings could not be read, so there the Trash's window is
            # unknown and nothing leaves it: the same here, or the default
            # 30 days emptied that Trash at the first start (2026-10-28).
            from noteorganizer.core import storage as _pe_storage
            _pe_prev = NO_paths.APP_DIR
            try:
                NO_paths.configure(_pe_home)
                _pe_window = _pe_storage.trash_retention_days()
            finally:
                NO_paths.configure(_pe_prev)
            check(f'...and its Trash keeps the window its settings left unknown '
                  f'({_pe_how}: {_pe_window})', _pe_window is None)
        # A file the first start cannot copy (another program holds it) is
        # tried again, then named: the notes file marks the copy done, and
        # "Imported" said nothing of a Trash left behind (2026-10-28).
        _pf_user = os.path.join(_pr_root, 'user_held')
        os.environ['USERPROFILE'] = _pf_user
        os.environ['APPDATA'] = os.path.join(_pf_user, 'AppData', 'Roaming')
        _pf_old, _pf_home = NO_paths.get_appdata_dir(), NO_paths.get_user_notebook_dir()
        os.makedirs(os.path.join(_pf_old, 'attachments'))
        os.makedirs(_pf_home)
        for _pf_name, _pf_text in (('notes_data.json', '[{"id": 1, "title": "A"}]'),
                                   ('settings.json', '{"app_version": "0.97.405"}'),
                                   ('trash.json', '[]'),
                                   (os.path.join('attachments', 'held.bin'), 'x'),
                                   (os.path.join('attachments', 'free.bin'), 'y')):
            with open(os.path.join(_pf_old, _pf_name), 'w', encoding='utf-8') as f:
                f.write(_pf_text)
        _pf_copy2 = NO_paths.shutil.copy2
        _pf_tries = {}

        def _pf_held(src, dst, *a, **k):
            name = os.path.basename(src)
            _pf_tries[name] = _pf_tries.get(name, 0) + 1
            if name == 'trash.json' or (name == 'held.bin' and _pf_tries[name] < 3):
                raise PermissionError('held by another program')
            return _pf_copy2(src, dst, *a, **k)
        NO_paths.shutil.copy2 = _pf_held
        _pf_sleep = NO_paths.time.sleep
        NO_paths.time.sleep = lambda s: None
        try:
            _pf_msg = NO_paths.run_migrations(_pf_home) or ''
        finally:
            NO_paths.shutil.copy2 = _pf_copy2
            NO_paths.time.sleep = _pf_sleep
        check(f'a file held a moment at the first start is copied on a later try '
              f'({_pf_tries})',
              os.path.exists(os.path.join(_pf_home, 'attachments', 'held.bin'))
              and os.path.exists(os.path.join(_pf_home, 'attachments', 'free.bin')))
        check(f'...and one that cannot be copied is named in the message '
              f'({_pf_msg[-90:]!r})',
              'could not be copied' in _pf_msg and 'trash.json' in _pf_msg
              and 'held.bin' not in _pf_msg)
        # The notes file itself held: all or nothing. It returned in silence,
        # the app opened empty, its first save wrote a notes file, and the
        # old notebook was never looked at again.
        _pn_user = os.path.join(_pr_root, 'user_notes_held')
        os.environ['USERPROFILE'] = _pn_user
        os.environ['APPDATA'] = os.path.join(_pn_user, 'AppData', 'Roaming')
        _pn_old, _pn_home = NO_paths.get_appdata_dir(), NO_paths.get_user_notebook_dir()
        os.makedirs(_pn_old)
        os.makedirs(_pn_home)
        for _pn_name, _pn_text in (('notes_data.json', '[{"id": 1, "title": "A"}]'),
                                   ('settings.json', '{"app_version": "0.97.405"}')):
            with open(os.path.join(_pn_old, _pn_name), 'w', encoding='utf-8') as f:
                f.write(_pn_text)

        def _pn_held(src, dst, *a, **k):
            if os.path.basename(src) == 'notes_data.json':
                raise PermissionError('held by another program')
            return _pf_copy2(src, dst, *a, **k)
        NO_paths.shutil.copy2 = _pn_held
        NO_paths.time.sleep = lambda s: None
        try:
            _pn_msg = NO_paths.run_migrations(_pn_home) or ''
        finally:
            NO_paths.shutil.copy2 = _pf_copy2
            NO_paths.time.sleep = _pf_sleep
        _pn_notes = os.path.join(_pn_home, 'notes_data.json')
        check(f'a notes file held at the first start says the notebook could not '
              f'come, asks to close the app and open it again, and nothing is '
              f'written in its place ({_pn_msg[-90:]!r})',
              'could not be brought in' in _pn_msg
              and 'close Note Organizer and open it again' in _pn_msg
              and not os.path.exists(_pn_notes)
              and NO_paths.writes_held(_pn_notes)
              # The settings too: written at once, they made the run a first
              # one, with a welcome note and an "Export complete" over nothing.
              and NO_paths.writes_held(os.path.join(_pn_home, 'settings.json')))
        NO_paths.WRITES_HELD.clear()
        _pn_msg = NO_paths.run_migrations(_pn_home) or ''
        check('...and the next start brings it in',
              NO_paths.count_notes_in(_pn_notes) == 1 and 'Imported 1' in _pn_msg)
        # The settings file held instead: the notes must not come without it,
        # or the old Trash falls under the default window and is emptied.
        _ps_user = os.path.join(_pr_root, 'user_settings_held')
        os.environ['USERPROFILE'] = _ps_user
        os.environ['APPDATA'] = os.path.join(_ps_user, 'AppData', 'Roaming')
        _ps_old, _ps_home = NO_paths.get_appdata_dir(), NO_paths.get_user_notebook_dir()
        os.makedirs(_ps_old)
        os.makedirs(_ps_home)
        for _ps_name, _ps_text in (('notes_data.json', '[{"id": 1, "title": "A"}]'),
                                   ('settings.json', '{"app_version": "0.97.405"}')):
            with open(os.path.join(_ps_old, _ps_name), 'w', encoding='utf-8') as f:
                f.write(_ps_text)

        def _ps_held(src, dst, *a, **k):
            if os.path.basename(src) == 'settings.json':
                raise PermissionError('held by another program')
            return _pf_copy2(src, dst, *a, **k)
        NO_paths.shutil.copy2 = _ps_held
        NO_paths.time.sleep = lambda s: None
        try:
            _ps_msg = NO_paths.run_migrations(_ps_home) or ''
        finally:
            NO_paths.shutil.copy2 = _pf_copy2
            NO_paths.time.sleep = _pf_sleep
        _ps_notes = os.path.join(_ps_home, 'notes_data.json')
        check(f'a settings file held at the first start keeps the notes from coming '
              f'without it, and asks to close the app and open it again ({_ps_msg[-90:]!r})',
              'could not be brought in' in _ps_msg
              and 'close Note Organizer and open it again' in _ps_msg
              and not os.path.exists(_ps_notes) and NO_paths.writes_held(_ps_notes))
        NO_paths.WRITES_HELD.clear()
        _ps_msg = NO_paths.run_migrations(_ps_home) or ''
        check('...and the next start brings the notes and the settings in',
              NO_paths.count_notes_in(_ps_notes) == 1
              and os.path.exists(os.path.join(_ps_home, 'settings.json')))
        os.environ['USERPROFILE'] = _pr_user
        os.environ['APPDATA'] = os.path.join(_pr_user, 'AppData', 'Roaming')
    # The second barrier: even listed as a leftover, the profile's notebook
    # is never cleared. A run from source beside an empty notebook would
    # otherwise find an empty one "covered", and delete it.
    del sys.frozen
    # A run from source taking over from AppData brings the Trash and the
    # templates where it has none -- and never over a Trash of its own.
    if os.name == 'nt':
        _pr_take = os.path.join(_pr_root, 'take')
        os.makedirs(_pr_take)
        with open(os.path.join(_pr_take, 'trash.json'), 'w', encoding='utf-8') as f:
            f.write('[]')
        NO_paths.run_migrations(_pr_take)
        with open(os.path.join(_pr_take, 'trash.json'), encoding='utf-8') as f:
            _pr_own = f.read()
        check('a run from source keeps its own Trash, and takes the templates it lacks',
              _pr_own == '[]'
              and os.path.exists(os.path.join(_pr_take, 'templates.json'))
              and NO_paths.count_notes_in(os.path.join(_pr_take, 'notes_data.json')) == 2)
    _pr_src = os.path.join(_pr_root, 'source')
    os.makedirs(_pr_src)
    # Without the file brought in above: a folder holding a file the
    # source run lacks is spared for that reason alone, and proves nothing.
    shutil.rmtree(_pr_home, ignore_errors=True)
    os.makedirs(_pr_home)
    for _pr_dir in (_pr_src, _pr_home):
        with open(os.path.join(_pr_dir, 'notes_data.json'), 'w', encoding='utf-8') as f:
            f.write('[]')
        with open(os.path.join(_pr_dir, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump({'app_version': '0.97.405'}, f)
    _pr_legacy = NO_paths.get_legacy_dirs
    NO_paths.get_legacy_dirs = lambda app_dir: [_pr_home]
    try:
        NO_paths.purge_stale_copies(_pr_src)
    finally:
        NO_paths.get_legacy_dirs = _pr_legacy
    check("even listed as a leftover, the profile's notebook is never cleared",
          os.path.exists(os.path.join(_pr_home, 'notes_data.json'))
          and os.path.exists(os.path.join(_pr_home, 'settings.json')))
finally:
    for _pr_key, _pr_value in _pr_env.items():
        if _pr_value is None:
            os.environ.pop(_pr_key, None)
        else:
            os.environ[_pr_key] = _pr_value
    if _pr_frozen is None:
        if hasattr(sys, 'frozen'):
            del sys.frozen
    else:
        sys.frozen = _pr_frozen
    shutil.rmtree(_pr_root, ignore_errors=True)

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

    # Days a series' copy set aside become notes at the start, written at
    # once: unwritten, each start made them again under new identities and
    # said so again.
    with open(NO_paths.DATA_FILE, 'r', encoding='utf-8') as f:
        _sa_was = f.read()
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump([{'id': 1, 'uid': 'gym', 'title': 'Gym', 'body': 'x', 'date': '2026-11-02',
                    'recurrence': {'freq': 'weekly'},
                    '_set_aside': [{'day': '2026-11-09', 'body': 'Earlier words'},
                                   {'day': '2026-11-16', 'title': 'Own title', 'body': 'B'}]}], f)
    _sa_first, _sa_report = _storage.load_notes()
    _sa_again, _sa_report2 = _storage.load_notes()
    _sa_made = [(n['title'], n['date'], n['uid']) for n in _sa_first if n['id'] != 1]
    check('a start makes the days set aside notes of their own and writes them at once: the same '
          'notes at the next start, nothing made again (%s; %s, then %s)'
          % ([m[:2] for m in _sa_made], _sa_report['set_aside_made'], _sa_report2['set_aside_made']),
          [m[:2] for m in _sa_made] == [('Gym (earlier text)', '2026-11-09'),
                                        ('Own title (earlier text)', '2026-11-16')]
          and _sa_report['set_aside_made'] == 2 and _sa_report2['set_aside_made'] == 0
          and [(n['title'], n['date'], n['uid']) for n in _sa_again if n['id'] != 1] == _sa_made
          and not any('_set_aside' in n for n in _sa_again))
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        f.write(_sa_was)

    # A start that set the notes file aside unreadable holds none of its
    # notes: a file the Trash's entry shares with one of them is no one's to
    # delete. Only a held run spared them.
    with open(NO_paths.DATA_FILE, 'r', encoding='utf-8') as f:
        _nu_good = f.read()
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        f.write('{not json')
    os.makedirs(NO_paths.ATTACHMENTS_DIR, exist_ok=True)
    _nu_file = os.path.join(NO_paths.ATTACHMENTS_DIR, '20261029_shared.png')
    _nu_entry = [{'attachments': [{'stored_as': '20261029_shared.png'}]}]
    with open(_nu_file, 'wb') as f:
        f.write(b'png')
    _storage.load_notes()
    _storage._delete_attachment_files(_nu_entry)
    _nu_kept = os.path.isfile(_nu_file)
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        f.write(_nu_good)
    _storage.load_notes()
    _storage._delete_attachment_files(_nu_entry)
    check('a start that could not read the notes deletes no attached file; one '
          'that read them does (kept %s, then %s)' % (_nu_kept, os.path.isfile(_nu_file)),
          _nu_kept and not os.path.isfile(_nu_file))

    # The file keeps its exact shape: a two-space indent, and every
    # character written as itself rather than escaped, so a note in any
    # script stays readable in a text editor and two saves diff cleanly.
    # The write became one string instead of a stream of pieces, to be
    # quicker; this is what says it still writes the same file, compared
    # against the old way of writing it, line endings and all.
    _shape = [{'id': 1, 'title': 'Café ☕ naïve Ω 中文 \U0001F600',
               'body': 'a\n| x | y |\n| --- | --- |'}]
    _storage.save_notes(_shape)
    _old_way = os.path.join(_notes_dir, 'written_the_old_way.json')
    with open(_old_way, 'w', encoding='utf-8') as f:
        json.dump(_storage.mend_surrogates(_shape), f, indent=2,
                  ensure_ascii=False)
    with open(NO_paths.DATA_FILE, 'rb') as f:
        _written = f.read()
    with open(_old_way, 'rb') as f:
        _expected = f.read()
    check('save_notes writes the file byte for byte as it always has',
          _written == _expected)

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

# ---- the welcome note is for a notebook that did not exist ----
#
# load_notes calls a notebook fresh only when there was no notes file at
# all -- a first install. An emptied notebook, an unreadable one and one a
# migration copied in all have their file, and must never get a note added.
from noteorganizer.core.welcome import build_welcome_note, LINES as _WELCOME_LINES
from noteorganizer.core.model import normalize_note as _normalize_note

_fresh_dir = tempfile.mkdtemp()
_prev_app_dir = NO_paths.APP_DIR
try:
    NO_paths.configure(_fresh_dir)
    _w_notes, _w_report = _storage.load_notes()
    check('load_notes calls a folder with no notes file a fresh notebook',
          _w_report.get('fresh_notebook') is True and _w_notes == [])
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        f.write('[]')
    check('...an emptied notebook is not one',
          _storage.load_notes()[1].get('fresh_notebook') is False)
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        f.write('{not json')
    _w_notes, _w_report = _storage.load_notes()
    check('...nor an unreadable one, which is reported as unreadable instead',
          _w_report.get('fresh_notebook') is False
          and _w_report.get('notes_file_corrupt') is True)
finally:
    shutil.rmtree(_fresh_dir, ignore_errors=True)
    NO_paths.configure(_prev_app_dir)

# Stored as the editor itself would store it: normalize_note changes
# nothing, each bold span lies on its words, each bullet entry on a line
# that starts with its marker -- and no icon carries the emoji variation
# selector, which Tk draws as a blank two letters wide.
_welcome = build_welcome_note()
_welcome_kept = _normalize_note(dict(_welcome, id=1))
_welcome_lines = _welcome['body'].split('\n')
check('the welcome note passes normalize_note unchanged',
      all(_welcome_kept[k] == _welcome[k]
          for k in ('title', 'body', 'formatting', 'paragraphs')))
check('every bold span of the welcome note lies on its words',
      bool(_welcome['formatting'])
      and all(s['end'] > s['start'] and _welcome['body'][s['start']:s['end']]
              == _welcome['body'][s['start']:s['end']].strip()
              and '\n' not in _welcome['body'][s['start']:s['end']]
              for s in _welcome['formatting']))
check('every bullet of the welcome note is a line that starts with one',
      len(_welcome['paragraphs'])
      == sum(1 for line in _WELCOME_LINES if line.startswith('- '))
      and all(_welcome_lines[p['line']].startswith('• ')
              for p in _welcome['paragraphs']))
# The first thing a new notebook shows says what the app does with your data
# and where the privacy policy is, so nobody meets it only by chance -- under
# a heading of its own, the owner's call: a line inside another section did
# not catch the eye.
_privacy_heading = '🛡 Your privacy'
_privacy_section = []
if _privacy_heading in _welcome_lines:
    for _line in _welcome_lines[_welcome_lines.index(_privacy_heading) + 1:]:
        if not _line:
            break
        _privacy_section.append(_line)
check('the welcome note gives privacy a section of its own, which says the app '
      'collects nothing and points to the privacy policy in Settings → About',
      any(_welcome['body'][s['start']:s['end']] == _privacy_heading
          for s in _welcome['formatting'] if s['style'] == 'bold')
      and any('collects nothing' in line for line in _privacy_section)
      and any('Settings → About → Privacy policy' in line
              for line in _privacy_section))
check('no line of the welcome note leaves its bold open, and no icon '
      'carries the variation selector',
      all(line.count('**') % 2 == 0 for line in _WELCOME_LINES)
      and '\ufe0f' not in _welcome['title'] + _welcome['body'])
# Every heading's title starts in one column: its icon is from the emoji
# block, which only the emoji font draws. Tk found \u2139 and \u270d, older symbols,
# in the text font, as narrow as letters, and their titles started left of
# the others -- the owner saw it. qa5 measures the column itself, on Windows.
_welcome_heading_icons = [line[2:].split(' ', 1)[0] for line in _WELCOME_LINES
                          if line.startswith('# ')]
_welcome_narrow = [icon for icon in _welcome_heading_icons
                   if len(icon) != 1 or ord(icon) < 0x1F000]
check(f'every heading of the welcome note starts with an icon from the emoji '
      f'block ({_welcome_narrow or "all"})',
      len(_welcome_heading_icons) >= 5 and not _welcome_narrow)
# The note shows the app; an icon in it the emoji picker cannot give back
# is one the person cannot use. Six of its eleven were missing once. An icon
# is anything from U+2100 up but the arrows: by category alone, ℹ is a letter.
import unicodedata as _ud
_picker_emoji = {e for _g, items, _c in NO.NoteOrganizer.EMOJI_GROUPS for e in items}
_welcome_icons = sorted({ch for ch in _welcome['title'] + _welcome['body']
                         if ord(ch) >= 0x2100 and _ud.category(ch) != 'Sm'})
_welcome_unpickable = [ch for ch in _welcome_icons if ch not in _picker_emoji]
check(f'every icon of the welcome note ({len(_welcome_icons)}) is one the emoji '
      f'picker offers ({_welcome_unpickable or "all"})',
      len(_welcome_icons) >= 5 and not _welcome_unpickable)
# A day marked with a sign the picker lacks could not be written about in a
# note: nine of the calendar's eighteen once.
_marker_unpickable = [e for e, _c in NO.NoteOrganizer.DAY_MARKER_EMOJIS
                      if e not in _picker_emoji]
check(f'every calendar day marker is one the emoji picker offers too '
      f'({_marker_unpickable or "all"})',
      len(NO.NoteOrganizer.DAY_MARKER_EMOJIS) >= 10 and not _marker_unpickable)

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
    _moved = _storage.move_notes_to_trash(_trash, [_notes[1]])
    check('move_notes_to_trash says it wrote the trash file', _moved == (True, None))
    check('move_notes_to_trash puts the note in the trash', len(_trash) == 1)
    check('move_notes_to_trash stamps a deletion time', bool(_trash[0].get('deleted_at')))
    check('move_notes_to_trash writes the trash file', os.path.exists(NO_paths.TRASH_FILE))
    # A Trash that cannot be written keeps nothing, and says so: the caller
    # then keeps the note, which used to end up in neither file.
    os.makedirs(NO_paths.TRASH_FILE + '.tmp')
    _held = list(_trash)
    _refused = _storage.move_notes_to_trash(_trash, [{'id': 3, 'title': 'Doomed'}])
    os.rmdir(NO_paths.TRASH_FILE + '.tmp')
    check('a Trash that cannot be written is reported, and keeps nothing',
          _refused[0] is False and _trash == _held)

    check('days_left_in_trash counts from the stamp',
          _storage.days_left_in_trash(_trash[0]['deleted_at']) == NO.TRASH_RETENTION_DAYS)
    check('days_left_in_trash returns None for an unreadable stamp',
          _storage.days_left_in_trash('not a date') is None)
    check('days_left_in_trash returns None rather than raising on junk',
          _storage.days_left_in_trash(None) is None)
    # Deleted while the clock ran ahead, read after it was put right: the
    # row promised more days than the window has.
    check('a stamp in the future promises no more than the window',
          _storage.days_left_in_trash('2099-01-01 09:00:00') == NO.TRASH_RETENTION_DAYS)

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

# The words on a fill: letters_on picks white or near-black by WCAG contrast,
# for every fill of every theme, and the theme switch asks for them by name.
from noteorganizer.core.themes import (
    letters_on as _letters, palette_value as _pvalue,
    contrast_ratio as _ratio_fn, relative_luminance as _rel_lum)
_fills = [(t, role, pal[role]) for t, pal in NO.THEMES.items()
          for role in ('accent', 'accent_hover', 'danger', 'success')]
check('letters_on picks the side with more contrast on every fill',
      all(_ratio_fn(_letters(c), c)
          >= max(_ratio_fn('#ffffff', c), _ratio_fn('#1a1a1a', c))
          for _t, _r, c in _fills))
# A colour the person picks gets the same answer as a theme's fill. The two
# helpers once had two formulas, and white sat at 2.2:1 on #00bbf9, a colour
# a calendar day can be painted. 4.1 is the worst any colour can do.
from noteorganizer.core.themes import (
    PALETTE_COLORS as _pick_day, PRESET_NOTE_COLORS as _pick_note,
    HIGHLIGHT_COLOR_PALETTE as _pick_hl, DEFAULT_CATEGORY_COLORS as _pick_cat)
_picked = sorted(set(_pick_day) | set(_pick_note) | set(_pick_hl)
                 | set(_pick_cat.values()))
_picked_bad = [(c, _contrast(c), round(_ratio_fn(_contrast(c), c), 2))
               for c in _picked
               if _contrast(c) != _letters(c) or _ratio_fn(_contrast(c), c) < 4.1]
check(f'every pickable colour ({len(_picked)}) gets the letters that read on it '
      f'({_picked_bad or "all at 4.1:1 or better"})',
      len(_picked) >= 30 and not _picked_bad)
check('the on_* names give the words for that fill, other names the colour',
      all(_pvalue(pal, 'on_' + role) == _letters(pal[role])
          for pal in NO.THEMES.values()
          for role in ('accent', 'danger', 'success'))
      and _pvalue(NO.THEMES['dark'], 'card') == NO.THEMES['dark']['card'])
check('a held-down Save is a darker shade of its fill, so a press shows',
      all(_pvalue(pal, 'success_pressed') != pal['success']
          and _ratio_fn(_pvalue(pal, 'success_pressed'), pal['success']) >= 1.2
          for pal in NO.THEMES.values()))
check('a fill it cannot read gets white words',
      _letters(None) == _letters('#zz') == _letters('') == '#ffffff')
# Delete is the dark fill with white words and Save the light one with dark
# words in every theme: they differ in lightness, not only in a hue a
# colour-blind reader may not see.
check('Delete wears white words and Save dark ones, in every theme',
      all(_letters(pal['danger']) == '#ffffff'
          and _letters(pal['success']) == '#1a1a1a'
          for pal in NO.THEMES.values()))
check('...and Delete is the darker fill of the two, in every theme',
      all(_rel_lum(pal['danger']) < _rel_lum(pal['success'])
          for pal in NO.THEMES.values()))
check('every theme names a text shade for each fill role',
      all(all(pal.get(k) for k in ('accent_text', 'danger_text', 'success_text'))
          for pal in NO.THEMES.values()))
# A colour the person picks, shown as words on a card: every swatch the app
# offers, on every theme's card, reads at 4.5:1 once legible_on has had it,
# and a colour that already reads is left exactly as picked.
from noteorganizer.core.themes import legible_on as _legible
_swatches = sorted(set(NO.PALETTE_COLORS + NO.PRESET_NOTE_COLORS
                       + list(NO.DEFAULT_CATEGORY_COLORS.values())))
check('every swatch, as words on every theme\'s card, reads at 4.6:1',
      all(_ratio_fn(_legible(c, pal['card'], pal['text']), pal['card']) >= 4.6
          for pal in NO.THEMES.values() for c in _swatches))
check('...and a colour that already reads keeps its exact value',
      _legible('#5b2dd2', '#ffffff', '#22223a') == '#5b2dd2'
      and _legible('#f9c74f', '#ffffff', '#22223a') != '#f9c74f')
check('...and a colour it cannot read gives the theme\'s text colour',
      _legible('nope', '#ffffff', '#22223a') == '#22223a')
# Darkened for a light card, a colour keeps its hue and loses none of its
# saturation: mixed toward the theme's bluish text, the yellow went khaki.
import colorsys as _colorsys


def _hsv(hex_colour):
    return _colorsys.rgb_to_hsv(*(int(hex_colour[i:i + 2], 16) / 255.0
                                  for i in (1, 3, 5)))


_warm = [c for c in _swatches if _hsv(c)[1] > 0.3]
check('...darkened for a light card, a colour keeps its hue and saturation',
      all(abs(_hsv(_legible(c, '#ffffff', '#22223a'))[0] - _hsv(c)[0]) < 0.02
          and _hsv(_legible(c, '#ffffff', '#22223a'))[1] >= _hsv(c)[1] - 0.01
          for c in _warm))
# The "nothing found" tint is her pick from photographed boards; it is
# written down, so a change of the warning red cannot move it.
check('the find box\'s "nothing found" tint is the one chosen, in every theme',
      [NO.miss_surface(NO.THEMES[t]) for t in
       ('dark', 'dark_ocean', 'dark_forest', 'dark_slate', 'light',
        'light_sky', 'light_mint', 'light_warm')]
      == ['#522b33', '#522f2f', '#523333', '#522f2f'] + ['#f9dddd'] * 4)

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


def _first_title_on_disk():
    """The first note's title as the file holds it, or None when there is
    no readable file: a failed save must be one red check, not a crash
    that hides every check after it (a mutant that broke the mend used
    to end this suite here, before its footer, with no verdict)."""
    try:
        with open(_paths.DATA_FILE, encoding="utf-8") as fh:
            notes = _json.load(fh)
        return notes[0].get("title") if notes else None
    except (OSError, ValueError, AttributeError, IndexError):
        return None


_title_back = _first_title_on_disk() or ""
check("and it lands as the real character, not the pair",
      chr(0x1F600) in _title_back and len(_title_back) == 5)
check("no half-written .tmp is left beside the file",
      not os.path.exists(_paths.DATA_FILE + ".tmp"))

_ok2, _exc2 = _storage.save_notes([{"id": 992, "title": "l " + chr(0xD83D)}])
check("a lone surrogate is replaced rather than poisoning the file",
      _ok2 and chr(0xFFFD) in (_first_title_on_disk() or ""))

_ok3, _exc3 = _storage.save_notes([{"id": 993, "bad": {1, 2}}])
check("an unserializable note reports (False, exc) instead of raising",
      _ok3 is False and isinstance(_exc3, TypeError))
check("and cleans up its .tmp too",
      not os.path.exists(_paths.DATA_FILE + ".tmp"))
# The new file is on the disk before it replaces the old: a power cut just
# after a replace could otherwise leave an empty notes file.
_synced = []
_real_fsync = _storage.os.fsync
_storage.os.fsync = lambda fd: (_synced.append(fd), _real_fsync(fd))[1]
try:
    _storage.save_notes([{"id": 994, "title": "synced"}])
finally:
    _storage.os.fsync = _real_fsync
check("a save is flushed to the disk before it replaces the file", len(_synced) == 1)
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
], [])
check("purge removes the expired entry and keeps the fresh one",
      _nT == 1 and len(_keptT) == 1 and _keptT[0]["id"] == 2)
check("purge permanently deletes the expired entry's attachment file",
      not os.path.exists(_old_att))
check("while the kept entry's file is untouched",
      os.path.exists(_new_att))
os.remove(_new_att)

# The Trash written first, then the files: deleted first, a refused write left
# trash.json naming files that were gone.
_expired = {"id": 1, "deleted_at": _stampO,
            "attachments": [{"stored_as": "teeth_old.bin"}]}
with open(_old_att, "w") as _f:
    _f.write("x")
_refusedT = _storage.purge_expired_trash(
    [dict(_expired)], [], write=lambda kept: (False, OSError(28, "No space")))
check("a purge whose Trash write is refused purges nothing and keeps the file",
      _refusedT[1] == 0 and len(_refusedT[0]) == 1 and os.path.exists(_old_att))
_writtenT = []
_landedT = _storage.purge_expired_trash(
    [dict(_expired)], [],
    write=lambda kept: (_writtenT.append(list(kept)), (True, None))[1])
check("written first, the purge then takes the file",
      _landedT[1] == 1 and _writtenT == [[]] and not os.path.exists(_old_att))

# ---- The purge spares a file something still uses ----
# Two notes share one stored file when a duplicate or an import could not
# copy it and kept the name. Delete and Empty trash spared it; the startup
# purge, the one deletion nobody asks for, took it from the living note.
_shared = os.path.join(_paths.ATTACHMENTS_DIR, "shared_att.bin")
for _whose, _notesS, _trashS in (
        ("a living note", [{"id": 5, "attachments": [{"stored_as": "shared_att.bin"}]}], []),
        ("a kept Trash entry", [], [{"id": 6, "deleted_at": _stampN,
                                     "attachments": [{"stored_as": "shared_att.bin"}]}])):
    with open(_shared, "w") as _f:
        _f.write("x")
    _keptS, _nS = _storage.purge_expired_trash(
        [{"id": 7, "deleted_at": _stampO,
          "attachments": [{"stored_as": "shared_att.bin"}]}] + _trashS, _notesS)
    check("the purge keeps a file %s still uses" % _whose,
          _nS == 1 and os.path.exists(_shared))
# Only if still there: a regression deletes it, and the suite must still
# reach its footer to say so.
if os.path.exists(_shared):
    os.remove(_shared)

# ---- A window not known removes nothing ----
# An unreadable settings.json read as {}, the next write made "unknown"
# into "never chosen", and the startup purge emptied the Trash at 30 days
# what the person had kept for 90. A hand-edited 0 clamped to one day.
_settings_heldW = None
if os.path.exists(_paths.SETTINGS_FILE):
    with open(_paths.SETTINGS_FILE, "rb") as _f:
        _settings_heldW = _f.read()
_stamp40 = (_dtT.datetime.now()
            - _dtT.timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
_stamp31 = (_dtT.datetime.now()
            - _dtT.timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
_old40 = {"id": 8, "deleted_at": _stamp40, "attachments": []}
with open(_paths.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    _f.write("{not json")
check("an unreadable settings file leaves the window not known",
      _storage.trash_retention_days() is None)
_storage.save_setting("theme", "dark")
check("...and a write of another setting keeps it not known",
      _storage.trash_retention_days() is None
      and _storage.get_setting("theme") == "dark")
_keptW, _nW = _storage.purge_expired_trash([dict(_old40)], [])
check("...and a 40-day-old entry survives the purge", _nW == 0 and len(_keptW) == 1)
check("...nothing is named as past the window, nor given days left",
      _storage.trash_entries_past_window([_old40]) == []
      and _storage.days_left_in_trash(_stamp40) is None)
check("...and no promise names a number of days",
      _storage.trash_window_words("within") == "")
_storage.choose_trash_window(90)
check("choosing a window forgets that the last one was not known",
      _storage.trash_retention_days() == 90
      and _storage.TRASH_WINDOW_UNKNOWN not in _storage.load_settings()
      and _storage.trash_window_words("within") == " within 90 days")
_storage.save_settings({})
check("a window never chosen is still the default",
      _storage.trash_retention_days() == _storage.TRASH_RETENTION_DAYS)
_keptW, _nW = _storage.purge_expired_trash(
    [{"id": 9, "deleted_at": _stamp31, "attachments": []}], [])
check("...and the default still empties a 31-day-old entry", _nW == 1)
for _bad in (0, -3, 400, "forever", True, 7.5, None):
    _storage.save_settings({"trash_retention_days": _bad})
    _keptW, _nW = _storage.purge_expired_trash([dict(_old40)], [])
    check("a stored window of %r is not known, and purges nothing" % (_bad,),
          _storage.trash_retention_days() is None and _nW == 0)
# What was here goes back, and the copy this block's damage left goes.
if _settings_heldW is None:
    os.remove(_paths.SETTINGS_FILE)
else:
    with open(_paths.SETTINGS_FILE, "wb") as _f:
        _f.write(_settings_heldW)
for _name in os.listdir(os.path.dirname(_paths.SETTINGS_FILE)):
    if _name.startswith("settings_corrupt_"):
        _pathW = os.path.join(os.path.dirname(_paths.SETTINGS_FILE), _name)
        with open(_pathW, "rb") as _f:
            _heldW = _f.read()
        if _heldW == b"{not json":
            os.remove(_pathW)

# ---- The window is counted in real time, not on the wall clock ----
# deleted_at is wall-clock time, and an age measured on the wall clock is
# an hour off across a change to summer time: in spring the purge took a
# note an hour before its window was up, where the phone (counting real
# time) kept it. A zone that springs forward on 29 March at 03:00 is
# played here, since the machine's own may have none -- CI's is UTC.
import calendar as _calD
_settings_heldD = None
if os.path.exists(_paths.SETTINGS_FILE):
    with open(_paths.SETTINGS_FILE, "rb") as _f:
        _settings_heldD = _f.read()


def _zoneD(when):
    hours = 3 if when >= _dtT.datetime(2026, 3, 29, 3) else 2
    return _calD.timegm(when.timetuple()) - hours * 3600


_clockD = (_storage._now_epoch, _storage._local_epoch)
_storage._local_epoch = _zoneD
_storage._now_epoch = lambda: _zoneD(_dtT.datetime(2026, 3, 31, 12, 30))
try:
    _storage.save_settings({"trash_retention_days": 30})
    # 30 days and half an hour ago on the wall clock, half an hour short
    # of 30 days in real time; and one that is really past.
    _shyD = {"id": 11, "deleted_at": "2026-03-01 12:00:00", "attachments": []}
    _pastD = {"id": 12, "deleted_at": "2026-03-01 11:00:00", "attachments": []}
    _keptD, _nD = _storage.purge_expired_trash([dict(_shyD), dict(_pastD)], [])
    check("across the spring clock change, a note not yet 30 real days in the Trash is kept",
          [e["id"] for e in _keptD] == [11] and _nD == 1)
    check("...and the shorter-window warning names what the purge removes",
          [e["id"] for e in _storage.trash_entries_past_window([_shyD, _pastD], 30)] == [12])
    # 3 days on the wall clock, 2 days and 23.5 hours really: 28 left.
    check("...and the days left are counted in real days too",
          _storage.days_left_in_trash("2026-03-28 12:00:00") == 28)
    # The control: with no clock change in between, the same 30 days and
    # half an hour IS past, so the keeping above is the change's doing.
    _storage._local_epoch = lambda when: _calD.timegm(when.timetuple()) - 3 * 3600
    check("...while with no clock change in between, the same note is past",
          _storage.purge_expired_trash([dict(_shyD)], [])[1] == 1)
finally:
    _storage._now_epoch, _storage._local_epoch = _clockD
    # On the real clock: a hand-edited stamp before 1970, which Windows'
    # mktime refuses, is still past every window -- not kept for good as
    # unreadable.
    check("a deleted_at before 1970 is still past the window",
          len(_storage.trash_entries_past_window(
              [{"id": 13, "deleted_at": "1900-01-01 00:00:00"}], 365)) == 1)
    if _settings_heldD is None:
        if os.path.exists(_paths.SETTINGS_FILE):
            os.remove(_paths.SETTINGS_FILE)
    else:
        with open(_paths.SETTINGS_FILE, "wb") as _f:
            _f.write(_settings_heldD)

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
# One file, one name. NTFS answers other strings for the same file -- an
# 8.3 short name, a "::$DATA" stream suffix -- while every check upstream
# compares names: a backup's Trash entry deleted a note's photo by its short
# name, and "x.exe::$DATA" opened with no unsafe-file warning. A symlink is
# the same alias on Linux.
_two_names = os.path.join(_paths.ATTACHMENTS_DIR, "20261003091512345678_holiday.jpg")
with open(_two_names, "w") as _f:
    _f.write("photo")
_aliases = []
if os.name == "nt":
    import ctypes
    _aliases.append("20261003091512345678_holiday.jpg::$DATA")
    _short_buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(_two_names, _short_buf, 1024):
        _short = os.path.basename(_short_buf.value)
        if _short.lower() != os.path.basename(_two_names):
            _aliases.append(_short)   # absent where the volume makes no short names
    # Another case, which Windows opens as the same file: every spare and
    # claimed set compares names exactly, so a backup's Trash entry naming a
    # kept note's photo in capitals was spared by none and deleted it.
    _aliases.append("20261003091512345678_HOLIDAY.JPG")
    _aliases.append("zz\\..\\20261003091512345678_holiday.jpg")
else:
    os.symlink(_two_names, os.path.join(_paths.ATTACHMENTS_DIR, "202610~1.JPG"))
    _aliases.append("202610~1.JPG")
# A path that comes back to the same name, which the guard's own tidying
# used to collapse before it compared.
_aliases += ["zz/../20261003091512345678_holiday.jpg",
             "./20261003091512345678_holiday.jpg"]
check("a name that reaches a file under another name is refused (%s)" % _aliases,
      bool(_aliases) and all(_storage._attachment_path_within(a) is None for a in _aliases))
check("...while the file's own name still resolves",
      _storage._attachment_path_within("20261003091512345678_holiday.jpg") is not None)
_storage._delete_attachment_files([{"attachments": [{"stored_as": a} for a in _aliases]}])
check("...and a delete by an alias leaves the file", os.path.exists(_two_names))
# A named stream of the file is a name for something else again: realpath
# hands "x.jpg:Zone.Identifier" back unchanged, so it passed the exact-name
# test, and a backup's Trash entry naming it deleted the Mark of the Web
# the import had just written.
# Refused on every system, so the check runs on each: on Linux the
# "stream" is a file of its own, which the rule keeps all the same.
_zone = b"[ZoneTransfer]\r\nZoneId=3\r\n"
with open(_two_names + ":Zone.Identifier", "wb") as _f:
    _f.write(_zone)
_streams = ["20261003091512345678_holiday.jpg:Zone.Identifier",
            "20261003091512345678_holiday.jpg:Zone.Identifier:$DATA",
            "20261003091512345678_holiday.jpg:s.pdf",
            "20261003091512345678_holiday.jpg:",
            "20261003091512345678_holiday.jpg:$DATA"]
check("a name that reaches a stream of a file is refused (%s)"
      % [s for s in _streams if _storage._attachment_path_within(s) is not None],
      all(_storage._attachment_path_within(s) is None for s in _streams))
# What the start-up purge, Empty Trash and Delete forever all call.
_storage._delete_attachment_files([{"attachments": [{"stored_as": s}]}
                                   for s in _streams])
try:
    with open(_two_names + ":Zone.Identifier", "rb") as _f:
        _zone_after = _f.read()
except OSError:
    _zone_after = None
check("...and a Trash entry naming the file's mark leaves the mark",
      _zone_after == _zone and os.path.exists(_two_names))
for _left in (_two_names, os.path.join(_paths.ATTACHMENTS_DIR, "202610~1.JPG"),
              _two_names + ":Zone.Identifier"):
    if os.path.lexists(_left):
        os.remove(_left)
# Trash entries come in as trash.json held them, and a hand-edited or
# damaged one held attachments as 7, true, a string, or a file name that is
# a list: the start-up purge read them and stopped the app at every start.
_odd_trash = [{"id": 1, "deleted_at": "2001-01-01 00:00:00", "attachments": 7},
              {"id": 2, "deleted_at": "2001-01-01 00:00:00", "attachments": True},
              {"id": 3, "deleted_at": "2001-01-01 00:00:00", "attachments": "x.png"},
              {"id": 4, "deleted_at": "2001-01-01 00:00:00",
               "attachments": [{"stored_as": ["x"]}, 5, {"stored_as": "kept.png"}]}]
try:
    _odd_names = _storage.attachment_names_in(_odd_trash)
    _storage._delete_attachment_files(_odd_trash, spare={"kept.png"})
    _storage.purge_expired_trash([dict(e) for e in _odd_trash], [])
    _odd_ok = _odd_names == {"kept.png"}
except Exception as _odd_exc:   # the start-up crash this guards against
    _odd_ok = False
    print("   raised:", repr(_odd_exc))
check("Trash entries whose attachments are not a list of files neither "
      "stop the purge nor hide the files that are named", _odd_ok)
# JSON's 1e999 reads as infinity, and int() of it raised OverflowError in the
# recurrence's clamps: one such number in notes_data.json -- or in a leftover
# notebook the start-up purge reads -- stopped the app at every start. So did
# raw notes nested 990 lists deep, through the purge's content signature.
from noteorganizer.core import model as _model_nf, recurrence as _rec_nf
_nf_ok = True
for _nf_v in (float("inf"), float("-inf")):
    try:
        _nf_rule = _rec_nf.normalize_recurrence(
            {"freq": "daily", "interval": _nf_v, "count": _nf_v})
        _nf_ok = _nf_ok and _nf_rule["interval"] == 1 and _nf_rule["count"] == 0
        _model_nf.normalize_note({"id": 1, "title": "t", "date": "2026-10-01",
                                  "recurrence": {"freq": "daily", "interval": _nf_v}})
    except Exception as _nf_exc:
        _nf_ok = False
        print("   raised:", repr(_nf_exc))
check("an infinite repeat interval or count reads as the default, not a crash", _nf_ok)
_nf_deep = []
_nf_cur = _nf_deep
for _ in range(985):
    _nf_cur.append([])
    _nf_cur = _nf_cur[0]
_nf_file = os.path.join(_paths.APP_DIR, "nf_stale_notes.json")
with open(_nf_file, "w", encoding="utf-8") as _f:
    json.dump([{"id": 1, "title": "t", "paragraphs": _nf_deep}], _f)
try:
    _nf_judged = _paths.is_redundant_copy(_nf_file, [{"id": 1, "title": "t"}])
except Exception as _nf_exc:
    _nf_judged = "raised %r" % _nf_exc
os.remove(_nf_file)
check("a leftover notebook too deep to sign is kept, never a crash (%s)" % _nf_judged,
      _nf_judged is False)
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
# A record with no stored name takes its display name as the stored one --
# taken as it was, a filename of "../../x" kept the very path the rule
# above removes. A name that flattens to nothing names no file at all.
_side = _nn_att({"id": 1, "title": "x", "attachments": [
    {"filename": "../../side.exe"}, {"filename": ".."},
    {"filename": "C:\\Windows\\w.txt", "stored_as": 7}]})
check("a record with no stored name takes the display name, flattened (%s)"
      % [a.get("stored_as") for a in _side["attachments"]],
      [a["stored_as"] for a in _side["attachments"]] == ["side.exe", "w.txt"])
# The two names are all a record is. Copied whole, a crafted record kept
# whatever else it carried, and a value nested a few hundred deep made
# Duplicate (a deep copy of the note) fail with "Something went wrong".
_nest = []
for _ in range(900):
    _nest = [_nest]
_extra = _nn_att({"id": 1, "title": "x", "attachments": [
    {"filename": "a.txt", "stored_as": "a.txt", "smuggled": _nest}]})
check("an attachment record keeps its two names and nothing else",
      _extra["attachments"] == [{"filename": "a.txt", "stored_as": "a.txt"}])
import copy as _copy_att
try:
    _copy_ok = _copy_att.deepcopy(_extra) == _extra
except RecursionError:
    _copy_ok = False
check("so a note carrying one can still be duplicated", _copy_ok)
# The label is only a label. A backup can write "Holiday photo.jpg" over
# an .rdp, and the row showed a photo while Windows opened a remote
# connection. normalize_note makes the shown name end in the type of the
# file that opens, and takes out what reorders or hides text.
# ISSUES_LOG: "The photo that was a remote connection".
from noteorganizer.core.model import attachment_display_name as _dn
_label = _nn_att({"id": 1, "title": "x", "attachments": [
    {"filename": "Holiday photo.jpg", "stored_as": "20261001120000000001_trip.rdp"},
    {"filename": "photo.tar.jpg", "stored_as": "20261001_photo"},
    {"filename": "x", "stored_as": ".rdp"}]})
check("a backup's label ends in the type of the file that opens (%s)"
      % [a["filename"] for a in _label["attachments"]],
      [a["filename"] for a in _label["attachments"]]
      == ["Holiday photo.rdp", "photo", "x.rdp"])
_hidden = ("\x00\x07\x1b\x7f\x85\x9f\u061c\u200e\u200f\u202a\u202b\u202c"
           "\u202d\u202e\u2066\u2067\u2068\u2069\u2028\u2029\ufeff")
_bidi = _nn_att({"id": 1, "title": "x", "attachments": [
    {"filename": "Invoice\u202efdp.exe", "stored_as": "20261001_inv.exe"},
    {"filename": "a" + _hidden + "b.txt", "stored_as": "20261001_ab.txt"}]})
check("a shown name keeps no character that reorders or hides text (%r)"
      % [a["filename"] for a in _bidi["attachments"]],
      [a["filename"] for a in _bidi["attachments"]] == ["Invoicefdp.exe", "ab.txt"])
_own = ["report.pdf", "Photo.JPG", "README", ".bashrc", "Ünïcödé €.docx",
        "a b.tar.gz", "שלום.txt",
        "family \U0001F468\u200d\U0001F469\u200d\U0001F467.png"]
check("...while a name the app stored itself is shown as it was, every time",
      all(_dn(n, "20261028120000000000_" + n) == n
          and _dn(_dn(n, "20261028120000000000_" + n), "20261028120000000000_" + n) == n
          for n in _own)
      and _nn_att(_label)["attachments"] == _label["attachments"])
# What a click does is judged from the stored file, and only kinds whose
# usual app just shows them open unasked. A list of dangerous kinds is never
# complete: .pyw, .rdp, .theme, .xll and the macro documents went straight
# to Windows. Anything not on the short list asks.
from noteorganizer.core import model as _kinds
_how = {name: _kinds.how_to_open("20261001_" + name) for name in [
    "photo.jpg", "scan.PNG", "anim.gif",
    "minutes.docx", "sheet.xlsx", "slides.pptx", "scan.pdf", "notes.txt",
    "list.csv", "clip.mp4", "song.mp3", "film.mov",
    "run.exe", "link.lnk", "evil.lnk. ", "n.pyw", "budget.py", "trip.rdp",
    "wall.theme", "report.xll", "minutes.docm", "sum.xlsm", "upd.msu",
    "app.msixbundle", "c.iqy", "w.wsc", "m.psm1", "nb.one",
    "old.doc", "old.xls", "page.html", "drawing.svg", "data.json",
    "archive.zip", "text.odt", "noext", "odd.xyz",
    "x.r" + chr(0x202e) + "dp"]}
_wrong = {n: k for n, k in _how.items() if k != (
    "preview" if n in ("photo.jpg", "scan.PNG", "anim.gif")
    else "open" if n.rsplit(".", 1)[-1] in ("docx", "xlsx", "pptx", "pdf", "txt",
                                            "csv", "mp4", "mp3", "mov")
    else "ask" if n in ("old.doc", "old.xls", "page.html", "drawing.svg",
                        "data.json", "archive.zip", "text.odt", "noext",
                        "odd.xyz", "x.r" + chr(0x202e) + "dp")
    else "warn")}
check("only kinds whose usual app just shows them open unasked; the rest ask, "
      "those that run code with the warning (%r)" % _wrong, not _wrong)
check("...a bare '.rdp' is an .rdp, as Windows reads it",
      _kinds.how_to_open(".rdp") == "warn")
_old_list = {".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".msi", ".msp",
             ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta",
             ".cpl", ".jar", ".reg", ".ps2", ".msc", ".gadget", ".lnk", ".url",
             ".scf", ".iso", ".img", ".vhd", ".vhdx", ".chm", ".inf", ".sct",
             ".appref-ms", ".settingcontent-ms", ".msix", ".appx",
             ".appinstaller", ".library-ms", ".search-ms", ".application",
             ".diagcab", ".ws", ".vb", ".mht", ".mhtml"}
check("...every kind that had the warning still has it, and none of them opens unasked",
      _old_list <= _kinds.DANGEROUS_EXTENSIONS
      and not (_kinds.DANGEROUS_EXTENSIONS & _kinds.OPENS_WITHOUT_ASKING))
# An exported note's file is named from its title, and Windows refuses a
# name holding any control character: a title with a bell in it (from a
# share code, say) failed to export with "1 failed to write" and no name.
_stems = {t: _kinds.export_file_stem(t) for t in [
    "bell\x07title", "tab\there", "Export <trial>", "a" + chr(0x202e) + "b",
    "c1\x85\x9fend", "del\x7fete", "...", "\x01\x02", "  .x.  ", "y" * 80]}
check("a file named from a title holds nothing Windows refuses or hides (%r)" % _stems,
      _stems == {"bell\x07title": "bell_title", "tab\there": "tab_here",
                 "Export <trial>": "Export _trial", "a" + chr(0x202e) + "b": "ab",
                 "c1\x85\x9fend": "c1end", "del\x7fete": "delete", "...": "note",
                 "\x01\x02": "note", "  .x.  ": "x", "y" * 80: "y" * 60})
# Windows' Mark of the Web travels with what the app brings in. A backup
# downloaded from the internet is marked, and the import took files out of
# it unmarked, so SmartScreen and Office's Protected View never saw them. A
# file attached by hand keeps its own (shutil.copy2 copies the stream on
# Windows), and so does a duplicate's copy. Windows only: nowhere else keeps
# the stream.
if os.name == "nt":
    import types as _types_m
    import zipfile as _zip_m
    import tkinter.filedialog as _tkfd_m
    _m_dir = tempfile.mkdtemp(prefix="notesorg-motw-")
    _m_mark = (b"[ZoneTransfer]\r\nZoneId=3\r\n"
               b"HostUrl=https://example.invalid/NotesBackup.zip\r\n")

    def _m_read(path):
        try:
            with open(path + ":Zone.Identifier", "rb") as _fh:
                return _fh.read()
        except OSError:
            return None

    class _Quiet:
        """A progress widget that is not there: every call does nothing."""
        def __getattr__(self, _name):
            return lambda *a, **k: None

    _m_zip = os.path.join(_m_dir, "NotesBackup.zip")
    with _zip_m.ZipFile(_m_zip, "w") as _z:
        _z.writestr("notes_data.json", "[]")
        _z.writestr("attachments/20261001120000000001_m_minutes.docm", b"PK macro")
    with open(_m_zip + ":Zone.Identifier", "wb") as _f:
        _f.write(_m_mark)
    os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
    _m_app = _types_m.SimpleNamespace(
        _export_state=None, _import_state=None, set_status=lambda *a: None,
        ask_yes_no=lambda *a, **k: True, export_progress_bar=_Quiet(),
        export_progress_lbl=_Quiet(), export_progress_frame=_Quiet(),
        _start_io_worker=lambda work: work(), _poll_import_progress=lambda: None,
        _while_native=lambda show: show())
    _m_real_open = NO.filedialog.askopenfilename
    NO.filedialog.askopenfilename = lambda **k: _m_zip
    try:
        NO.NoteOrganizer.import_data(_m_app)
    finally:
        NO.filedialog.askopenfilename = _m_real_open
    _m_state = _m_app._import_state or {}
    _m_dest = os.path.join(NO.ATTACHMENTS_DIR, "20261001120000000001_m_minutes.docm")
    check("an attachment restored from a downloaded backup keeps the backup's "
          "mark of the web (%r, %r)" % (_m_state.get("error"), _m_read(_m_dest)),
          _m_state.get("error") is None and _m_read(_m_dest) == _m_mark)

    _m_src = os.path.join(_m_dir, "Downloads", "minutes.docx")
    os.makedirs(os.path.dirname(_m_src))
    with open(_m_src, "wb") as _f:
        _f.write(b"PK docx")
    with open(_m_src + ":Zone.Identifier", "wb") as _f:
        _f.write(_m_mark)
    os.makedirs(_paths.ATTACHMENTS_DIR, exist_ok=True)
    _m_editor = _types_m.SimpleNamespace(
        current_attachments=[], selected_note_id=None,
        show_warning=lambda *a, **k: None, show_error=lambda *a, **k: None,
        ask_yes_no=lambda *a, **k: True, refresh_attachments_list=lambda: None,
        _schedule_autosave=lambda: None, _while_native=lambda show: show())
    _m_real_many = _tkfd_m.askopenfilenames
    _tkfd_m.askopenfilenames = lambda **k: (_m_src,)
    try:
        NO.NoteOrganizer.add_attachment(_m_editor)
    finally:
        _tkfd_m.askopenfilenames = _m_real_many
    _m_added = [os.path.join(_paths.ATTACHMENTS_DIR, a["stored_as"])
                for a in _m_editor.current_attachments]
    check("a file attached by hand keeps its own mark of the web",
          len(_m_added) == 1 and _m_read(_m_added[0]) == _m_mark)
    _m_dup = (_storage.copy_attachment_file(os.path.basename(_m_added[0]))
              if _m_added else None)
    _m_dup_path = os.path.join(_paths.ATTACHMENTS_DIR, _m_dup) if _m_dup else None
    check("...and so does the copy a duplicated note gets",
          bool(_m_dup) and _m_read(_m_dup_path) == _m_mark)
    try:
        _m_nowhere = NO.put_zone_mark(os.path.join(_m_dir, "no folder", "x.docx"), _m_mark)
    except Exception as _exc:
        _m_nowhere = "raised %r" % _exc
    check("...while a place that cannot hold the mark goes without it and never fails (%r)"
          % (_m_nowhere,), _m_nowhere is False)
    for _left in [_m_dest, _m_dup_path] + _m_added:
        if _left and os.path.exists(_left):
            os.remove(_left)
    if _m_state.get("temp_dir"):
        shutil.rmtree(_m_state["temp_dir"], ignore_errors=True)
    shutil.rmtree(_m_dir, ignore_errors=True)
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

# A file of 20,000 templates (a backup's, or a hand-edited one) took
# fourteen seconds to import and five for the picker to open: a load keeps
# the first MAX_TEMPLATES, which no one reaches by hand -- the doors refuse
# the next one (2026-10-28).
with open(_paths.TEMPLATES_FILE, "w", encoding="utf-8") as _f:
    json.dump([{"name": "t%05d" % _i, "body": "b"}
               for _i in range(_storage.MAX_TEMPLATES + 500)], _f)
_tpMany = _storage.load_templates()
check(f"a templates file past the ceiling loads its first "
      f"{_storage.MAX_TEMPLATES:,} ({len(_tpMany):,})",
      len(_tpMany) == _storage.MAX_TEMPLATES
      and _tpMany[-1]["name"] == "t%05d" % (_storage.MAX_TEMPLATES - 1))
os.remove(_paths.TEMPLATES_FILE)

# Half an emoji, spelled as a JSON escape: a lone surrogate, which Tk will
# not draw -- one in a note's title stopped the app starting, at every
# launch (2026-10-28). Every data file, and a share code, reads it mended.
_LONE = '"t' + chr(92) + 'ud83d x"'


def _encodes(value):
    try:
        json.dumps(value, ensure_ascii=False).encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


_lnKept = {}
for _p in (_paths.DATA_FILE, _paths.TEMPLATES_FILE, _paths.SETTINGS_FILE,
           _paths.TRASH_FILE):
    if os.path.exists(_p):
        with open(_p, "rb") as _f:
            _lnKept[_p] = _f.read()
with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    _f.write('[{"id": 1, "title": %s, "body": %s}]' % (_LONE, _LONE))
_lnNotes, _lnReport = _storage.load_notes(None)
with open(_paths.TEMPLATES_FILE, "w", encoding="utf-8") as _f:
    _f.write('[{"name": %s, "body": "b"}]' % _LONE)
with open(_paths.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    _f.write('{"username": %s}' % _LONE)
with open(_paths.TRASH_FILE, "w", encoding="utf-8") as _f:
    _f.write('[{"id": 2, "title": %s, "deleted_at": "2026-10-28 00:00:00"}]' % _LONE)
_lnAll = [_lnNotes, _storage.load_templates(), _storage.load_settings(),
          _storage.load_trash()]
check("a lone surrogate spelled in a data file is mended as each file is "
      "read: notes, templates, settings, Trash",
      all(_encodes(v) for v in _lnAll) and len(_lnNotes) == 1
      and _lnNotes[0]["title"] == "t� x"
      and _lnAll[1][0]["name"] == "t� x")
import base64 as _b64
import zlib as _zlib
from noteorganizer.core import sharing as _sharingL
_lnCode = "NOTE1:" + _b64.urlsafe_b64encode(_zlib.compress(
    ('{"v": 1, "notes": [{"title": %s, "body": "b"}]}' % _LONE).encode("utf-8"))).decode()
try:
    _lnShared = _sharingL.decode_share_code(_lnCode)
except ValueError as _e:
    _lnShared = _e
check(f"...and in a share code ({type(_lnShared).__name__})",
      _encodes(_lnShared) if not isinstance(_lnShared, Exception) else False)
# Each file put back as it was before these checks, or taken away again.
for _p in (_paths.DATA_FILE, _paths.TEMPLATES_FILE, _paths.SETTINGS_FILE,
           _paths.TRASH_FILE):
    if _p in _lnKept:
        with open(_p, "wb") as _f:
            _f.write(_lnKept[_p])
    elif os.path.exists(_p):
        os.remove(_p)

# ---- Damage the parser does not call JSON is damage all the same ----
# Two more ways a file can be unreadable, and neither raised the
# JSONDecodeError the loaders caught: bytes that are not UTF-8 (a file
# another program saved in a Windows code page, where "e" with an acute
# accent is the one byte 0xE9) raised UnicodeDecodeError, and nesting
# deeper than the parser follows raised RecursionError. Both flew past the
# loaders, and the app would not start while any of its four files held one.
_DAMAGED = {
    "not-UTF-8": b'[{"id": 1, "title": "caf\xe9"}]',
    "nested-too-deep": b"[" * 100000 + b"]" * 100000,
}


def _answer(call):
    """What *call* returns -- or which exception escaped it. The defect
    under test is the escape, and a mutant bringing it back must be one red
    check, not a crash that ends the suite before its footer."""
    try:
        return call()
    except Exception as exc:
        return "ESCAPED " + type(exc).__name__


def _kept_aside(prefix, data):
    """True if a preserved copy named *prefix*... holds exactly *data*."""
    for name in os.listdir(_paths.APP_DIR):
        if name.startswith(prefix):
            with open(os.path.join(_paths.APP_DIR, name), "rb") as fh:
                if fh.read() == data:
                    return True
    return False


_DATA_FILES = (_paths.DATA_FILE, _paths.SETTINGS_FILE, _paths.TRASH_FILE,
               _paths.TEMPLATES_FILE)
_before_damage = {}
for _file in _DATA_FILES:
    try:
        with open(_file, "rb") as _f:
            _before_damage[_file] = _f.read()
    except OSError:
        _before_damage[_file] = None
for _how, _bytes in _DAMAGED.items():
    with open(_paths.DATA_FILE, "wb") as _f:
        _f.write(_bytes)
    _dmg = _answer(lambda: _storage.load_notes(None))
    check("a %s notes file loads as damaged: empty, flagged, bytes kept (%s)"
          % (_how, _dmg if isinstance(_dmg, str) else "returned"),
          isinstance(_dmg, tuple) and _dmg[0] == []
          and _dmg[1]["notes_file_corrupt"]
          and _kept_aside("notes_data_corrupt_", _bytes))
    for _file, _load, _empty, _prefix in (
            # Empty but for the one thing the file's loss means: the
            # Trash's window went with it (TRASH_WINDOW_UNKNOWN).
            (_paths.SETTINGS_FILE, _storage.load_settings,
             {_storage.TRASH_WINDOW_UNKNOWN: True}, "settings_corrupt_"),
            (_paths.TRASH_FILE, _storage.load_trash, [], "trash_corrupt_"),
            (_paths.TEMPLATES_FILE, _storage.load_templates, [],
             "templates_corrupt_")):
        with open(_file, "wb") as _f:
            _f.write(_bytes)
        _dmg = _answer(_load)
        check("a %s %s loads as damaged: empty, bytes kept (%s)"
              % (_how, os.path.basename(_file),
                 _dmg if isinstance(_dmg, str) else "returned"),
              _dmg == _empty and _kept_aside(_prefix, _bytes))
# What was here goes back, and this block's own copies go: the checks
# below read every preserved copy as UTF-8 text.
for _file, _held in _before_damage.items():
    if _held is None:
        if os.path.exists(_file):
            os.remove(_file)
        continue
    with open(_file, "wb") as _f:
        _f.write(_held)
for _name in os.listdir(_paths.APP_DIR):
    if "_corrupt_" in _name:
        with open(os.path.join(_paths.APP_DIR, _name), "rb") as _f:
            _held = _f.read()
        if _held in _DAMAGED.values():
            os.remove(os.path.join(_paths.APP_DIR, _name))

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

# A cleanup whose write did not land (the file held by another program)
# was marked done anyway: its renumbered ids lived only in the running
# app, against a file and a remembered open note with the old ones.
_setW = _storage.load_settings()
_setW.pop("cleanup_done", None)
_setW["last_open_note_id"] = 7
_storage.save_settings(_setW)
_rawW = [{"id": 3, "title": "", "body": ""}, {"id": 7, "title": "Kept", "body": "x"}]
with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    json.dump(_rawW, _f)
_writeW = _storage._write_json_atomic


def _held_notes_file(path, value):
    if os.path.abspath(path) == os.path.abspath(_paths.DATA_FILE):
        return False, PermissionError(13, "held by another program", path)
    return _writeW(path, value)


_backupsW = os.path.join(os.path.dirname(_paths.DATA_FILE), "notes_data_backup_*.json")
_beforeW = set(glob.glob(_backupsW))
_storage._write_json_atomic = _held_notes_file
try:
    _notesW, _reportW = _storage.load_notes(None)
finally:
    _storage._write_json_atomic = _writeW
_afterW = _storage.load_settings()
check("a cleanup whose write does not land is not marked done, and says nothing",
      not _afterW.get("cleanup_done") and _reportW.get("cleanup_report") is None)
# Its copy went too: the file was untouched, and a file held for a week
# left a full copy of the notebook at every launch.
check("...and leaves no copy of the notes behind, the file being as it was",
      set(glob.glob(_backupsW)) == _beforeW)
# Stamped by the second, a copy made the same second wrote over the one
# before it -- and the copy above, removed, took that one with it.
_clockW = _storage.datetime


class _OneSecond(_clockW):
    """The same second for both copies, whatever the machine's speed."""
    @classmethod
    def now(cls, tz=None):
        return _clockW(2026, 11, 13, 9, 0, 0)


_storage.datetime = _OneSecond
try:
    _twiceA, _twiceB = _storage.backup_notes_file(), _storage.backup_notes_file()
finally:
    _storage.datetime = _clockW
check(f"two copies of the notes in the same second are two files ({_twiceA!r}, {_twiceB!r})",
      _twiceA and _twiceB and _twiceA != _twiceB
      and os.path.isfile(_twiceA) and os.path.isfile(_twiceB))
for _p in (_twiceA, _twiceB):
    if _p and os.path.isfile(_p):
        os.remove(_p)
check("...the notes keep the ids their file and the remembered note still name",
      [n["id"] for n in _notesW] == [3, 7] and _afterW.get("last_open_note_id") == 7)
_notesW2, _reportW2 = _storage.load_notes(None)
check("...and the next launch that can write does the cleanup, the open note followed",
      _reportW2.get("cleanup_report") is not None
      and [n["id"] for n in _notesW2] == [1]
      and _storage.load_settings().get("last_open_note_id") == 1
      and _storage.load_settings().get("cleanup_done") is True)
# A settings file that refused the mark ran the cleanup at every start,
# each keeping a full copy of a notebook it had nothing left to change.
_setR = _storage.load_settings()
_setR.pop("cleanup_done", None)
_storage.save_settings(_setR)
_beforeR = set(glob.glob(_backupsW))
_notesR, _reportR = _storage.load_notes(None)
check(f"a cleanup run again with nothing to change leaves no copy behind "
      f"({sorted(set(glob.glob(_backupsW)) - _beforeR)!r})",
      set(glob.glob(_backupsW)) == _beforeR and [n["id"] for n in _notesR] == [1]
      and (_reportR.get("cleanup_report") or (None, "kept"))[1] is None)
# ...but a file it rewrites only by reshaping what the read takes in
# another shape (a body written as a list) keeps its copy: compared with
# the notes as read, it went, the one place that shape was left. A field
# the read does not know rides along in the copy (and stays in the notes).
_setU = _storage.load_settings()
_setU.pop("cleanup_done", None)
_storage.save_settings(_setU)
with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
    json.dump([{"id": 1, "uid": "u1", "title": "Kept", "body": ["words", "in a list"],
                "extra": "theirs"}], _f)
_beforeU = set(glob.glob(_backupsW))
_notesU, _ = _storage.load_notes(None)
_newU = sorted(set(glob.glob(_backupsW)) - _beforeU)
_heldU = open(_newU[0], encoding="utf-8").read() if len(_newU) == 1 else ""
check(f"...but one whose file the read reshapes keeps its copy, with what it held in ({_newU!r})",
      len(_newU) == 1 and '"extra"' in _heldU and "in a list" in _heldU)
check(f"...and the field the read does not know stays in the notes too "
      f"({[n.get('extra') for n in _notesU]!r})",
      [n.get("extra") for n in _notesU] == ["theirs"])

# The two loaders without a corrupt fixture yet: settings (unparsable)
# and trash (wrong shape). Content-matched rather than counted, so a
# same-second timestamp collision cannot fake a pass or a fail.
with open(_paths.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    _f.write("{broken settings")
_setP = _storage.load_settings()
check("corrupt settings.json -> only the window's marker, plus a preserved copy",
      _setP == {_storage.TRASH_WINDOW_UNKNOWN: True} and any(
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

# Junk beside real entries -- a hand edit -- kept Recently deleted from
# opening at all: the panel asks every entry .get(). Only notes come in,
# and the file's bytes are kept aside first.
_JUNK = '[{"id": 7, "title": "real"}, "junk", null]'
with open(_paths.TRASH_FILE, "w", encoding="utf-8") as _f:
    _f.write(_JUNK)
_trJ = _storage.load_trash()
# Read whatever came back, junk included: a check that raised on the very
# failure it is there to see would stop the suite instead of naming it.
check("a trash.json holding junk beside its notes loads the notes alone "
      "(%r)" % (_trJ,),
      [e.get("title") if isinstance(e, dict) else e for e in _trJ] == ["real"])
check("...and keeps the file's bytes aside first",
      any(open(os.path.join(_paths.APP_DIR, p), encoding="utf-8").read() == _JUNK
          for p in os.listdir(_paths.APP_DIR) if p.startswith("trash_corrupt_")))
# Read again at the next launch, with nothing having rewritten the file:
# each launch kept one more copy of the same bytes, never deleted. Kept
# once is enough. The copy above is dated as an earlier launch would have
# left it -- copies are stamped to the second, and a test runs in one.
def _junk_copies():
    return [p for p in os.listdir(_paths.APP_DIR)
            if p.startswith("trash_corrupt_")
            and open(os.path.join(_paths.APP_DIR, p), encoding="utf-8").read() == _JUNK]


for _jk in _junk_copies()[:1]:
    os.replace(os.path.join(_paths.APP_DIR, _jk),
               os.path.join(_paths.APP_DIR, "trash_corrupt_20000101_000000.json"))
_storage.load_trash()
check("...once: the next launch reading the same file keeps no second copy "
      "(%s)" % _junk_copies(), len(_junk_copies()) == 1)

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
    # The file's name and the kind of error, never its folder: the folder's
    # path holds the person's name (core/diagnostics' own promise).
    _wf_said = open(_wf_log, encoding="utf-8").read()
    check("the crash log names the file that failed, not the folder it is in",
          "trash.json" in _wf_said and _wf_dir not in _wf_said
          and os.path.basename(_wf_dir) not in _wf_said)
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

# ---- What the app says about itself (core/diagnostics, 2026-10-15) ----
# Every crash_log.txt entry carries the same details: the version, how the
# app draws, how big the notebook is, the Windows -- never what a note says,
# never a path (a folder's path holds the person's name).
from noteorganizer.core import diagnostics as _diag
_dg_dir = tempfile.mkdtemp()
_real_dg = (NO_paths.APP_DIR, NO_paths.DATA_FILE, _diag.app_details, _diag.version)


def _dg_try(fn):
    try:
        return fn()
    except Exception as _exc:  # a broken writer is a FAIL line, not a crash
        return _exc


def _dg_read(path):
    return open(path, encoding="utf-8").read() if isinstance(path, str) else ""


try:
    NO_paths.APP_DIR = _dg_dir
    NO_paths.DATA_FILE = os.path.join(_dg_dir, "notes_data.json")
    _dg_notes = [{"id": 1, "title": "SECRET-TITLE", "body": "SECRET-BODY",
                  "attachments": [{"name": "SECRET.pdf", "stored_as": "1_SECRET.pdf"}]},
                 {"id": 2, "title": "two", "body": "x", "attachments": []},
                 "not a note"]
    with open(NO_paths.DATA_FILE, "w", encoding="utf-8") as _fh:
        json.dump(_dg_notes, _fh)
    _diag.version = "9.9.9"
    # A provider that hands over more than it should: a path and a title.
    _diag.app_details = lambda: ([("scale", "150%"), ("sharp", "on"),
                                  ("theme", "Midnight Purple")]
                                 + _diag.notebook(_dg_notes)
                                 + [("path", _dg_dir), ("title", "SECRET-TITLE")])
    _dg_said = dict(_diag.details())
    check("the details carry the version, how the app draws and how big the notebook is",
          _dg_said.get("version") == "9.9.9" and _dg_said.get("notes") == 2
          and _dg_said.get("files") == 1 and _dg_said.get("scale") == "150%"
          and "windows" in _dg_said and _dg_said.get("build") in ("exe", "source"))
    check("...and nothing else: no note's words, no file name, no path, whatever the "
          "app hands it",
          set(_dg_said) <= set(_diag.DETAIL_KEYS) and "SECRET" not in repr(_dg_said)
          and os.path.basename(_dg_dir) not in repr(_dg_said))
    _dg_text = _dg_read(_dg_try(lambda: _diag.append_crash_log("test", "the trace")))
    _dg_head = _dg_text.split("the trace")[0]
    check("a crash log entry names the version, the notebook's size and the Windows, "
          "above its trace",
          "(test)" in _dg_head and "version: 9.9.9" in _dg_head and "notes: 2" in _dg_head
          and "files: 1" in _dg_head and "windows: " in _dg_head
          and _dg_text.rstrip().endswith("the trace"))
    check("...and no note's words or path in its line of details",
          "SECRET" not in _dg_head and os.path.basename(_dg_dir) not in _dg_head)
    _diag.app_details = lambda: 1 / 0
    _dg_text = _dg_read(_dg_try(lambda: _diag.append_crash_log("broken", "trace two")))
    check("a details provider that breaks cannot stop a crash being logged",
          "trace two" in _dg_text)
    NO_paths.APP_DIR = None
    check("before the data folder is known, a crash log writes nothing instead of raising",
          _dg_try(lambda: _diag.append_crash_log("crash", "early")) is None)
finally:
    NO_paths.APP_DIR, NO_paths.DATA_FILE, _diag.app_details, _diag.version = _real_dg
    shutil.rmtree(_dg_dir, ignore_errors=True)

# One writer for crash_log.txt: every other place in the app hands its entry
# to diagnostics.append_crash_log, so every entry carries the same details.
# Four places wrote it by hand, each in its own format.
import tokenize as _dg_tok
_dg_writers = []
_dg_sources = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "note_organizer.py")]
for _dg_root, _dg_dirs, _dg_files in os.walk(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "noteorganizer")):
    _dg_sources += [os.path.join(_dg_root, _f) for _f in _dg_files if _f.endswith(".py")]
for _dg_src in _dg_sources:
    if os.path.basename(_dg_src) == "diagnostics.py":
        continue
    with open(_dg_src, "rb") as _fh:
        for _t in _dg_tok.tokenize(_fh.readline):
            if _t.type == _dg_tok.STRING and _t.string.strip("\"'") == "crash_log.txt":
                _dg_writers.append("%s:%d" % (os.path.basename(_dg_src), _t.start[0]))
check("crash_log.txt is written in one place only (%s)" % (_dg_writers or "none other"),
      _dg_writers == [])

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
# Every checklist item becomes five widgets at render time and nothing
# capped the count: 20,000 items is a 60KB code that passes every decoder
# guard, and the app never starts again once the note is saved.
_bomb = _model.normalize_note(
    {"id": 1, "title": "bomb",
     "checklist": [{"text": "x", "done": False}] * 20000})
check("normalize_note caps the checklist at the data choke point",
      len(_bomb["checklist"]) == _model.MAX_CHECKLIST_ITEMS)
check("and the cap is far above any real list",
      _model.MAX_CHECKLIST_ITEMS >= 500)
# ...and each item's length: one item is drawn as one wrapped label as tall as
# its text, and a 490-character share code carried a 60,000-character item in.
# The boxes refuse one past the
# limit (qa1, qa6); one already longer is a person's words, kept whole by every
# load, and drawn cut.
from noteorganizer.core import model as _coreCL, sharing as _sharingCL
from noteorganizer.core.storage import normalize_template as _ntCL
_cl_long = "w" * 60000
_cl_note = _model.normalize_note(
    {"id": 1, "title": "long", "checklist": [{"text": _cl_long, "done": True},
                                             {"text": "short", "done": False}]})
_cl_tpl = _ntCL({"name": "t", "checklist": [{"text": _cl_long, "done": False}]})
_cl_shared = _sharingCL.decode_share_code(_sharingCL.encode_share_code(
    [{"id": 1, "title": "long", "checklist": [{"text": _cl_long, "done": False}]}]))
_cl_in = _model.normalize_note(_cl_shared[0]) if _cl_shared else {"checklist": []}
check("normalize_note, normalize_template and a share code keep a long "
      "checklist item whole (%s)"
      % [len(i["text"]) for i in _cl_note["checklist"] + _cl_tpl["checklist"]
         + _cl_in["checklist"]],
      [i["text"] for i in _cl_note["checklist"]] == [_cl_long, "short"]
      and _cl_note["checklist"][0]["done"] is True
      and [i["text"] for i in _cl_tpl["checklist"] + _cl_in["checklist"]]
      == [_cl_long] * 2)
_cl_shown = [_model.checklist_shown(t) for t in (
    _cl_long, "x\n" * 999, "two\nlines", "v" * _model.MAX_CHECKLIST_ITEM_CHARS,
    None)]
check("...and a row draws it cut, by characters and by lines, leaving a "
      "shorter item as it is (%s)" % [(len(t), t.count("\n")) for t in _cl_shown],
      _cl_shown[0] == "w" * _model.MAX_CHECKLIST_ITEM_CHARS + "…"
      and _cl_shown[1].endswith("…")
      and _cl_shown[1].count("\n") == _coreCL.CHECKLIST_SHOWN_LINES - 1
      and _cl_shown[2:] == ["two\nlines", "v" * _model.MAX_CHECKLIST_ITEM_CHARS, ""])
check("...and the limit is far above any real item",
      _model.MAX_CHECKLIST_ITEM_CHARS >= 1000)

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
                  text=True, cwd=_lock_dir, timeout=120)
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

    # A lock file another program holds a moment (a sharing violation) is
    # tried again: failing open at once let a second window in once it was
    # let go. Raised twice, then the file opens: the lock is taken.
    # Raised as open() raises it on Windows: EACCES, with no winerror.
    _Sharing = PermissionError

    _sh_left = {"n": 2}
    _sh_real_open, _sh_real_sleep = open, _si_mod.time.sleep

    def _sh_open(path, *a, **k):
        if path.endswith("sharing_probe.lock") and _sh_left["n"] > 0:
            _sh_left["n"] -= 1
            raise _Sharing(13, "held by another program")
        return _sh_real_open(path, *a, **k)

    _si_mod.open = _sh_open
    _si_mod.time.sleep = lambda s: None
    try:
        _sh_got = _si_mod.acquire(os.path.join(_lock_dir, "sharing_probe.lock"))
        _sh_held = _si_mod.held()
    finally:
        del _si_mod.open
        _si_mod.time.sleep = _sh_real_sleep
        try:
            _si_mod.release()
        except Exception:
            pass
    check("a lock file held a moment by another program is taken on a later try "
          "(got %s, held %s)" % (_sh_got, _sh_held),
          _sh_got is True and _sh_held is True and _sh_left["n"] == 0)

    if os.name == "nt":
        # The same, held for real: opened with no sharing, let go 0.3 s later.
        # A simulated error once carried a winerror open() never sets, and
        # the retry it proved never ran on Windows.
        import ctypes as _sh_ct
        import threading as _sh_th
        _sh_k32 = _sh_ct.WinDLL("kernel32", use_last_error=True)
        _sh_k32.CreateFileW.restype = _sh_ct.c_ssize_t     # -1: it failed
        _sh_k32.CreateFileW.argtypes = [_sh_ct.c_wchar_p, _sh_ct.c_uint32, _sh_ct.c_uint32,
                                        _sh_ct.c_void_p, _sh_ct.c_uint32, _sh_ct.c_uint32,
                                        _sh_ct.c_void_p]
        _sh_k32.CloseHandle.argtypes = [_sh_ct.c_ssize_t]
        _sh_path = os.path.join(_lock_dir, "sharing_real.lock")
        # GENERIC_READ | GENERIC_WRITE, no sharing, OPEN_ALWAYS.
        _sh_hold = _sh_k32.CreateFileW(_sh_path, 0xC0000000, 0, None, 4, 0x80, None)
        _sh_timer = _sh_th.Timer(0.3, lambda: _sh_k32.CloseHandle(_sh_hold))
        _sh_timer.start()
        try:
            _sh_real_got = _si_mod.acquire(_sh_path)
            _sh_real_held = _si_mod.held()
        finally:
            _sh_timer.join()
            try:
                _si_mod.release()
            except Exception:
                pass
        check("a lock file another program holds for real is taken once let go "
              "(got %s, held %s)" % (_sh_real_got, _sh_real_held),
              _sh_hold != -1 and _sh_real_got is True and _sh_real_held is True)

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
    _ta = _legacy_file([dict(_base, title="ATitle")])
    _real_sig = _model_mod.content_signature
    try:
        _model_mod.content_signature = lambda n: ("bent",)
        check("the purge consults model.content_signature, not a private copy",
              _paths_mod.is_redundant_copy(_ta, [dict(_base, title="OtherTitle")])
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

# ONE answer, and it is the strict one. Styling, layout, per-day edits
# and skipped dates are real work, and a leftover notebook differing only
# in those was once judged "already covered" and deleted. The startup
# duplicate collapse kept a looser answer for years -- "a stray bold word
# does not make a duplicate" -- until two copies of a weekly routine, one
# edited on a single day and pinned, were merged and the edited copy
# removed under a dialog calling it an exact duplicate. Every automatic
# removal asks the same strict question now, pin and colour included.
_fmt_a = dict(_base, title="The same", body="text",
              formatting=[{"start": 0, "end": 4, "style": "bold"}])
_fmt_b = dict(_base, title="The same", body="text")
check("styling splits a duplicate -- for the startup collapse too",
      _model_mod.content_signature(_fmt_a)
      != _model_mod.content_signature(_fmt_b))
for _field, _value in (("paragraphs", [{"line": 0, "kind": "bullet"}]),
                       ("overrides", {"2026-01-01": {"title": "day"}}),
                       ("exceptions", ["2026-01-02"]),
                       ("pinned", True),
                       ("color", "#ff0000")):
    check("the signature sees %s" % _field,
          _model_mod.content_signature(dict(_fmt_b, **{_field: _value}))
          != _model_mod.content_signature(_fmt_b))
# The scenario itself, end to end through the cleanup.
_gym = {"title": "Gym", "body": "Leg day", "date": "2026-09-01",
        "recurrence": {"freq": "weekly"}}
_gym_a = _model_mod.normalize_note(dict(_gym, id=1, exceptions=["2026-09-08"]))
_gym_b = _model_mod.normalize_note(dict(
    _gym, id=2, exceptions=["2026-09-08"], pinned=True,
    overrides={"2026-09-15": {"body": "Rest week"}}))
_gym_kept, _gym_stats = _model_mod.clean_notes([_gym_a, _gym_b])
check("the startup cleanup keeps a routine's copy that was edited on one day",
      len(_gym_kept) == 2 and _gym_stats["duplicates_removed"] == 0
      and any(n["overrides"] for n in _gym_kept))
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
check("the signature tolerates raw junk shapes",
      _model_mod.content_signature(
          {"formatting": {"a": [1, {"b": None}]}, "overrides": 7,
           "exceptions": "nope", "paragraphs": object(), "pinned": "yes",
           "color": ["#fff"]}) is not None)

# Find-duplicates and the import scans share _dup_key; checklist and
# recurrence joined its key (they are never merged, so a grouping there
# destroys whichever copy is dropped), attachments deliberately did NOT
# (cleanup hands the kept note the group's combined files).
_t1 = dict(_base, title="Groceries", checklist=[{"text": "milk", "done": False}])
_t2 = dict(_base, title="Groceries", checklist=[{"text": "gym", "done": False}])
check("different checklists keep two same-text notes apart",
      _fdg([_t1, _t2]) == [])
# A series' own days are never merged either: a copy holding a deleted, an
# edited or a moved day grouped with one that did not. The same days, or
# none on both, still group.
_sd = dict(_base, title="Gym", date="2026-01-05", recurrence={"freq": "weekly"})
check("a series' own days -- deleted, edited, moved -- keep two copies apart",
      _fdg([_sd, dict(_sd, exceptions=["2026-01-12"])]) == []
      and _fdg([_sd, dict(_sd, overrides={"2026-01-12": {"body": "legs"}})]) == []
      and _fdg([_sd, dict(_sd, moved={"2026-01-12": "2026-01-13"})]) == [])
check("...and the same days, or none on either, still group",
      len(_fdg([dict(_sd, exceptions=["2026-01-12"]),
                dict(_sd, exceptions=["2026-01-12"])])) == 1
      and len(_fdg([dict(_sd, overrides={}), dict(_sd)])) == 1)
# Every question about duplicates says what is compared through SAME_AS;
# a field the key gains and the phrase lacks is the drift it stops.
from noteorganizer.core.duplicates import SAME_AS as _same_as, _dup_key as _dk
# Each part the words name, and a change to it the key must see: counting
# the parts alone passed a phrase that swapped "repeat rule" for "date".
_sa_parts = {"same title": ("title", "Other"), "text": ("body", "other"),
             "comments": ("comments", "x"), "category": ("category", "Work"),
             "checklist": ("checklist", [{"text": "a", "done": False}]),
             "repeat rule": ("recurrence", {"freq": "weekly"}),
             "a series' own days": ("exceptions", ["2026-01-12"])}
_sa_named = _same_as.replace(" and ", ", ").split(", ")
# ...but its last part, the fields a version does not know, which no person
# sees and the words do not name (D2; its own check is at the file's end).
check("the words every duplicate question uses name each part of the key, "
      "and each part they name is one the key sees",
      len(_sa_named) + 1 == len(_dk(_t1)) and sorted(_sa_named) == sorted(_sa_parts)
      and all(_dk(dict(_t1, **{f: v})) != _dk(_t1) for f, v in _sa_parts.values()))
_r1 = dict(_base, title="Sport", date="2026-01-01",
           recurrence={"freq": "weekly", "weekdays": [0]})
_r2 = dict(_base, title="Sport", date="2026-01-01", recurrence={})
check("a repeat rule keeps a series apart from its one-off twin",
      _fdg([_r1, _r2]) == [])
_a1 = dict(_base, title="Documents", attachments=[{"stored_as": "a.pdf"}])
_a2 = dict(_base, title="Documents", attachments=[{"stored_as": "b.pdf"}])
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
                        categories={"Projects": "#112233"}))
    check("...while an ordinary name is kept exactly as written",
          "Projects" in _cats_mod.load_categories())
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
      _sc("#A1B2C3") == "#A1B2C3" and _sc(" #ff0000 ") == "#ff0000")
# ...and the short one comes back long: every reader that works a colour
# out by hand reads six digits, and a #abc day colour from a hand-edited
# settings.json stopped its whole month drawing.
check("sanitize_color gives #rgb back as #rrggbb, the same colour (%r)"
      % _sc("#abc"), _sc("#abc") == "#aabbcc" and _sc("#F0a") == "#FF00aa")
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

_MAIN_GUARD_DRIVER = '"""Drive the REAL _main() with the heavy parts stubbed to recorders.\n\nWritten and launched by test_data_safety to prove the single-instance\nguard is WIRED, not merely implemented: _main must consult acquire() and\nhonour the answer. The adversarial review caught the gap this closes --\ndeleting the whole guard from _main left every suite green, because the\nlock primitive was tested end-to-end while the one call site a user ever\ntravels through was tested by nobody.\n"""\nimport json\nimport os\nimport sys\n\nHERE = os.path.dirname(os.path.abspath(__file__))\nos.chdir(HERE)\nsys.path.insert(0, HERE)\n\n# Hermetic seed BEFORE the note_organizer import: the module resolves its\n# data directory and runs migrations at import time, and an unseeded dir\n# invites the adoption of the machine\'s real notebook.\nif not os.path.exists("notes_data.json"):\n    with open("notes_data.json", "w", encoding="utf-8") as f:\n        f.write("[]")\ntry:\n    with open("settings.json", "r", encoding="utf-8") as f:\n        _settings = json.load(f)\nexcept Exception:\n    _settings = {}\nif not isinstance(_settings, dict):\n    _settings = {}\n_settings.setdefault("reclaimed_from_appdata", True)\nwith open("settings.json", "w", encoding="utf-8") as f:\n    json.dump(_settings, f)\n\nimport tkinter.messagebox as mb  # noqa: E402\n\nimport note_organizer as NO  # noqa: E402\nfrom noteorganizer.core import paths  # noqa: E402\n\nevents = []\nfolders = {}\n\n\ndef _recording_initialise(app_dir=None, resolved=None):\n    paths.configure(HERE)\n    events.append("init")\n    folders["opened"] = resolved[0] if resolved else None\n\n\nNO.initialise = _recording_initialise\n_real_acquire = NO.single_instance.acquire\n\n\ndef _recording_acquire(path=None):\n    events.append("acquire")\n    folders["locked"] = os.path.dirname(path) if path else None\n    return _real_acquire(path)\n\n\nNO.single_instance.acquire = _recording_acquire\n\n\nclass FakeApp:\n    def __init__(self):\n        events.append("app")\n\n    def protocol(self, *a, **k):\n        pass\n\n    def on_app_close(self):\n        pass\n\n    def on_session_end(self):\n        pass\n\n    def mainloop(self):\n        events.append("loop")\n\n\nclass FakeRoot:\n    def withdraw(self):\n        pass\n\n    def destroy(self):\n        pass\n\n\nNO.NoteOrganizer = FakeApp\nNO.tk.Tk = FakeRoot\nmb.showinfo = lambda *a, **k: events.append("refused-dialog")\n\nNO._main()\nprint("EVENTS:" + json.dumps(events))\nprint("FOLDERS:" + json.dumps(folders))\n'

# ---- The guard is WIRED, not merely implemented ----
# The primitive above is proven end-to-end; this proves _main() actually
# consults it and honours the answer. Without this, deleting the whole
# guard from _main left every suite green (adversarial review, 2026-09-11)
# -- the classic tested-library-untested-call-site gap, on the one call
# site a user ever travels through.
_driver_path = os.path.join(os.getcwd(), "_main_guard_driver.py")
with open(_driver_path, "w", encoding="utf-8") as _f:
    _f.write(_MAIN_GUARD_DRIVER)


_driver_folders = {}


def _run_main_driver():
    out = _sp.run([sys.executable, _driver_path], capture_output=True,
                  text=True, cwd=os.getcwd(), timeout=120)
    _driver_folders.clear()
    for line in (out.stdout or "").splitlines():
        if line.startswith("FOLDERS:"):
            try:
                _driver_folders.update(json.loads(line[len("FOLDERS:"):]))
            except ValueError:
                pass
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
    # The folder locked and the folder opened are ONE answer. _main used
    # to resolve the data folder, lock it, and let initialise() resolve
    # again -- two launches at the same instant made the first answer
    # "not writable", so a launch locked a fallback folder and then
    # opened the notebook its twin was holding, unlocked.
    _locked = _driver_folders.get("locked")
    _opened = _driver_folders.get("opened")
    check("initialise opens the very folder _main locked, not a second answer",
          bool(_locked) and bool(_opened)
          and os.path.normcase(os.path.abspath(_locked))
          == os.path.normcase(os.path.abspath(_opened)))
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

# ======================================================================
# The "try to break it" audit of 2026-09-29: nothing moves a user's notes
# behind their back. Each block names the finding it closes.
# ======================================================================

# ---- A share code's version field is checked before it is compared ----
# Compared unchecked, a string/null/list version raised TypeError, which
# the import box does not catch: an internal error instead of the
# damaged-code message. The check lives where the decoder is, not at the
# one caller, so any future caller gets the ValueError it expects.
from noteorganizer.core import sharing as _sharing_mod
import base64 as _b64
import copy as copy_mod
import zlib as _zlib


def _code_with_version(version):
    raw = json.dumps({"v": version, "notes": [{"title": "x"}]}).encode()
    return "NOTE1:" + _b64.urlsafe_b64encode(_zlib.compress(raw)).decode()


def _decode_answer(code):
    try:
        _sharing_mod.decode_share_code(code)
        return "accepted"
    except ValueError as exc:
        return "ValueError: " + str(exc)
    except Exception as exc:  # the defect under test is a crash
        return "CRASH: " + type(exc).__name__


for _bad in ("2", None, [1], {"major": 1}):
    check("a share code whose version is %r is refused as damaged, not crashed on"
          % (_bad,),
          _decode_answer(_code_with_version(_bad)).startswith("ValueError")
          and "damaged" in _decode_answer(_code_with_version(_bad)))
check("an ordinary version still imports, and a newer one is still refused",
      _decode_answer(_code_with_version(1)) == "accepted"
      and "newer version" in _decode_answer(_code_with_version(2)))
# Nesting deeper than the parser follows raised RecursionError, which the
# decoder did not catch: "Something went wrong" instead of the message
# that tells the person what to do.
_deep_code = "NOTE1:" + _b64.urlsafe_b64encode(
    _zlib.compress(b"[" * 100000 + b"]" * 100000)).decode()
check("a share code nested too deep to read is refused as damaged (%s)"
      % _decode_answer(_deep_code)[:40],
      _decode_answer(_deep_code).startswith("ValueError")
      and "damaged" in _decode_answer(_deep_code))

# ---- One rule for every door a category name comes in by ----
# Add and Rename accepted any length and any count; the loader then
# dropped a name over 80 characters and the 201st category, and every
# note filed under them was in General from the next launch on.
from noteorganizer.core import categories as _cats2
_cat_keep = dict(_cats2.CATEGORY_COLORS)
try:
    check("an 80-character name is a fine category name",
          _cats2.category_name_refusal("x" * _cats2.MAX_CATEGORY_NAME) is None)
    _long_answer = _cats2.category_name_refusal(
        "x" * (_cats2.MAX_CATEGORY_NAME + 1))
    check("an 81-character one is refused, and the refusal says why",
          bool(_long_answer) and str(_cats2.MAX_CATEGORY_NAME) in _long_answer)
    _cats2.CATEGORY_COLORS.clear()
    _cats2.CATEGORY_COLORS.update({"General": "#888888"})
    _cats2.CATEGORY_COLORS.update(
        {"Cat%03d" % i: "#123456" for i in range(_cats2.MAX_CATEGORIES - 1)})
    check("the 201st category is refused at the door...",
          _cats2.category_name_refusal("One too many") is not None)
    check("...while renaming one of the 200 is not about the count",
          _cats2.category_name_refusal("Renamed", adding=False) is None)
finally:
    _cats2.CATEGORY_COLORS.clear()
    _cats2.CATEGORY_COLORS.update(_cat_keep)

# ---- The notes are believed: categories come back from them ----
# Categories live in settings.json and a note stores only the name, so
# deleting settings.json (a common way to "reset the preferences") or
# copying only notes_data.json to a new PC used to re-file every note
# into General at the next launch -- written to disk before any user
# action, with no word said.
_cat_keep = dict(_cats2.CATEGORY_COLORS)
try:
    _cats2.CATEGORY_COLORS.clear()
    _cats2.CATEGORY_COLORS.update({"General": "#888888"})
    _adopted = _cats2.adopt_categories_of([
        {"category": "Clients 2026"},
        {"category": "General"},
        {"category": "Gym", "overrides": {"2026-09-15": {"category": "Travel"}}},
        {"category": " padded "},                       # normalize would miss it
        {"category": "y" * (_cats2.MAX_CATEGORY_NAME + 1)},  # the ceiling holds
        {"category": 7},
        "not a note",
    ])
    check("categories the notes are filed under come back into the map",
          _adopted == ["Clients 2026", "Gym", "Travel"]
          and all(n in _cats2.CATEGORY_COLORS for n in _adopted))
    check("...each with a real colour",
          all(_sc(_cats2.CATEGORY_COLORS[n]) for n in _adopted))
    check("...and not a padded or over-long name normalize_note would not match",
          " padded " not in _cats2.CATEGORY_COLORS
          and not any(len(n) > _cats2.MAX_CATEGORY_NAME
                      for n in _cats2.CATEGORY_COLORS))
finally:
    _cats2.CATEGORY_COLORS.clear()
    _cats2.CATEGORY_COLORS.update(_cat_keep)

# The whole route: a notebook whose settings.json has gone.
_rt_prev_dir = _paths.APP_DIR
_rt_dir = tempfile.mkdtemp(prefix="nd_adopt_")
_cat_keep = dict(_cats2.CATEGORY_COLORS)
try:
    _paths.configure(_rt_dir)
    with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
        json.dump([{"id": 1, "uid": "u1", "title": "Invoice",
                    "category": "Clients 2026"},
                   {"id": 2, "uid": "u2", "title": "Plain",
                    "category": "General"}], _f)
    # No settings.json at all -- exactly what "reset the preferences" is.
    _cats2.CATEGORY_COLORS.clear()
    _cats2.CATEGORY_COLORS.update(_cats2.load_categories())
    _rt_notes, _rt_report = _storage.load_notes(None)
    check("with settings.json gone, a note keeps the category it was filed under",
          next((n for n in _rt_notes if n.get("uid") == "u1"), {}).get("category")
          == "Clients 2026")
    with open(_paths.DATA_FILE, encoding="utf-8") as _f:
        _rt_disk = json.load(_f)
    check("...on disk too, after the startup cleanup rewrote the file",
          next((n for n in _rt_disk if n.get("uid") == "u1"), {}).get("category")
          == "Clients 2026")
    check("...the category is saved back into the settings",
          "Clients 2026" in (_storage.load_settings().get("categories") or {}))
    check("...and the load reports it, so the app can say what happened",
          _rt_report.get("categories_adopted") == ["Clients 2026"]
          and _rt_report.get("categories_unsaved") is False)
    # ...and a settings file that refuses them is reported too: "added back"
    # came again at every start, with no word of why.
    os.remove(_paths.SETTINGS_FILE)
    _cats2.CATEGORY_COLORS.clear()
    _cats2.CATEGORY_COLORS.update(_cats2.load_categories())
    _rt_save_was = _cats2.save_settings
    _cats2.save_settings = lambda _s: (False, OSError(28, "No space left on device"))
    try:
        _rt_notes, _rt_report = _storage.load_notes(None)
    finally:
        _cats2.save_settings = _rt_save_was
    check("...and when the settings file refuses them, the load says they were not saved",
          _rt_report.get("categories_adopted") == ["Clients 2026"]
          and _rt_report.get("categories_unsaved") is True)
finally:
    _paths.configure(_rt_prev_dir)
    _cats2.CATEGORY_COLORS.clear()
    _cats2.CATEGORY_COLORS.update(_cat_keep)
    shutil.rmtree(_rt_dir, ignore_errors=True)

# ---- Every note's id is its own, on every load ----
# find_note returns the FIRST match and delete filters by id, so two notes
# sharing an id (two notebooks merged by hand both number from 1) meant
# editing one silently overwrote the other, and deleting one took both.
_dups = [_model_mod.normalize_note(n) for n in (
    {"id": 1, "title": "Mortgage"}, {"id": 1, "title": "Car service"},
    {"id": 2, "title": "Holiday"}, {"id": 0, "title": "Zero"},
    {"id": -4, "title": "Negative"}, {"id": "junk", "title": "Junk"})]
check("colliding and unusable ids are repaired",
      _model_mod.repair_note_ids(_dups) is True)
check("...every note ends up with an id of its own, all positive",
      len({n["id"] for n in _dups}) == len(_dups)
      and all(n["id"] > 0 for n in _dups))
check("...and the first holder of a number keeps it",
      _dups[0]["title"] == "Mortgage" and _dups[0]["id"] == 1
      and _dups[2]["id"] == 2)
check("a list that was already fine is left exactly as it was",
      _model_mod.repair_note_ids(
          [_model_mod.normalize_note({"id": i}) for i in (3, 1, 2)]) is False)

_ids_prev_dir = _paths.APP_DIR
_ids_dir = tempfile.mkdtemp(prefix="nd_ids_")
try:
    _paths.configure(_ids_dir)
    _storage.save_settings({"cleanup_done": True})
    with open(_paths.DATA_FILE, "w", encoding="utf-8") as _f:
        json.dump([{"id": 1, "uid": "a1", "title": "Mortgage"},
                   {"id": 1, "uid": "b1", "title": "Car service"}], _f)
    _ids_notes, _ = _storage.load_notes(None)
    with open(_paths.DATA_FILE, encoding="utf-8") as _f:
        _ids_disk = json.load(_f)
    check("the load repairs a collision even after the one-time cleanup has run",
          len({n["id"] for n in _ids_notes}) == 2)
    check("...and writes the repair down, so the next launch agrees",
          len({n["id"] for n in _ids_disk}) == 2)
finally:
    _paths.configure(_ids_prev_dir)
    shutil.rmtree(_ids_dir, ignore_errors=True)

# ---- "Restore previous" brings back everything an update replaced ----
# The update dialog promised each update "can be undone with ↩ Restore
# previous", while the rescue copy held the text alone: a ticked
# checklist, a date, a yearly repeat and a colour were gone for good.
_up_note = _model_mod.normalize_note({
    "id": 1, "title": "Passport", "body": "renew",
    "checklist": [{"text": "photo", "done": True},
                  {"text": "form", "done": True},
                  {"text": "fee", "done": False}],
    "date": "2026-10-01", "recurrence": {"freq": "yearly"},
    "color": "#ff0000"})
_up_before = {k: copy_mod.deepcopy(_up_note[k])
              for k in _model_mod.UPDATABLE_FROM_SHARED}
_model_mod.apply_shared_update(_up_note, {
    "title": "Passport", "body": "renew (from phone)",
    "checklist": [{"text": "photo", "done": False}]})
check("a share-code update snapshots every field it replaces",
      all((_up_note.get("_prev") or {}).get(k) == _up_before[k]
          for k in _model_mod.UPDATABLE_FROM_SHARED))
_up_reloaded = _model_mod.normalize_note(json.loads(json.dumps(_up_note)))
check("...and the snapshot survives a save and a reload",
      all((_up_reloaded.get("_prev") or {}).get(k) == _up_before[k]
          for k in _model_mod.UPDATABLE_FROM_SHARED))
check("a text-only rescue copy stays text-only across a reload",
      set(_model_mod.normalize_note(
          {"id": 1, "_prev": {"title": "t", "body": "b"}}).get("_prev") or {})
      == set(_model_mod.PREV_TEXT_FIELDS))
_junk_prev = _model_mod.normalize_note({"id": 1, "_prev": {
    "title": "t", "body": "b", "color": "#nope!!", "pinned": "yes",
    "checklist": [{"text": "x"}] * 5000, "exceptions": ["junk", "2026-01-02"]}})
# .get throughout: a copy that lost these keys must FAIL here, not raise
# and take the suite down before its footer (the mutant that removes the
# shaping did exactly that, and read as a run that had not finished).
_junk_p = _junk_prev.get("_prev") or {}
check("the extra fields of a rescue copy pass the note's own validators",
      _junk_p.get("color") == ""
      and _junk_p.get("pinned") is False
      and len(_junk_p.get("checklist") or []) == _model_mod.MAX_CHECKLIST_ITEMS
      and _junk_p.get("exceptions") == ["2026-01-02"])
# Only true pins and ticks: bool() read a hand-edited "false" as a pin and
# "no" as ticked, where the phone, reading true alone, said neither.
_pin_rule = _model_mod.normalize_note({
    "id": 1, "pinned": "false",
    "checklist": [{"text": "a", "done": "no"}, {"text": "b", "done": True}]})
check("only true pins and ticks: a hand-edited \"false\" is neither, as on the phone",
      _pin_rule.get("pinned") is False
      and [i["done"] for i in _pin_rule["checklist"]] == [False, True])

# A backup is the user's own notebook: its copy owns the timeline and the
# pin as well, and dropping them was silent.
_bk_note = _model_mod.normalize_note({
    "id": 1, "title": "Gym", "date": "2026-09-01",
    "recurrence": {"freq": "weekly"}})
_model_mod.apply_shared_update(_bk_note, {
    "title": "Gym", "date": "2026-09-01", "recurrence": {"freq": "weekly"},
    "exceptions": ["2026-09-08"], "pinned": True,
    "overrides": {"2026-09-15": {"body": "moved to Wed"}}},
    _model_mod.UPDATABLE_FROM_BACKUP)
check("a backup's update brings its skipped days, per-day edits and pin",
      _bk_note["exceptions"] == ["2026-09-08"] and _bk_note["pinned"] is True
      and _bk_note["overrides"].get("2026-09-15", {}).get("body")
      == "moved to Wed")
check("...and its rescue copy holds what they replaced",
      (_bk_note.get("_prev") or {}).get("exceptions") == []
      and (_bk_note.get("_prev") or {}).get("pinned") is False
      and (_bk_note.get("_prev") or {}).get("overrides") == {})

# A share code turning a series' repeat off kept the series' own days in
# the note, out of sight, and its rescue copy without them: the next save
# dropped the days with no copy anywhere, and Restore previous brought the
# repeat back empty.
_off_days = {"2026-10-12": {"body": "Leg day: squats"}}
_off_note = _model_mod.normalize_note({
    "id": 1, "title": "Gym", "body": "Warm up", "date": "2026-10-05",
    "recurrence": {"freq": "weekly"}, "exceptions": ["2026-10-26"],
    "overrides": copy_mod.deepcopy(_off_days)})
_model_mod.apply_shared_update(_off_note, {
    "title": "Gym", "body": "Warm up!", "date": "2026-10-05", "recurrence": {}})
_off_prev = _off_note.get("_prev") or {}
check("a share code that ends a repeat keeps the series' days in the rescue copy",
      _off_prev.get("overrides") == _off_days
      and _off_prev.get("exceptions") == ["2026-10-26"]
      and (_off_prev.get("recurrence") or {}).get("freq") == "weekly")
# ...COPIED, and kept in the note too: moved into the one copy slot, the
# next copy made over it -- a second update, a big rewrite -- erased them.
check("...and the note keeps them too, so no later copy can take them",
      _off_note["overrides"] == _off_days and _off_note["exceptions"] == ["2026-10-26"])
check("...and the copy keeps them across a save and a reload",
      (_model_mod.normalize_note(json.loads(json.dumps(_off_note)))
       .get("_prev") or {}).get("overrides") == _off_days)
_model_mod.apply_shared_update(_off_note, {
    "title": "Gym", "body": "Warm up!!", "date": "2026-10-05",
    "recurrence": {"freq": "weekly"}})
check("a second code that turns the repeat back on finds every day's own text",
      _off_note["overrides"] == _off_days
      and _model_mod.is_recurring(_off_note))
_on_note = _model_mod.normalize_note({
    "id": 1, "title": "Gym", "date": "2026-10-05",
    "recurrence": {"freq": "weekly"}, "overrides": copy_mod.deepcopy(_off_days)})
_model_mod.apply_shared_update(_on_note, {
    "title": "Gym (v2)", "date": "2026-10-05", "recurrence": {"freq": "daily"}})
check("a share code that keeps a repeat leaves this device's days in the note",
      _on_note["overrides"] == _off_days
      and "overrides" not in (_on_note.get("_prev") or {}))
# The restore's own copy: putting back a version that did not repeat over
# a series with days of its own.
_rs_note = _model_mod.normalize_note({
    "id": 1, "title": "Gym", "body": "Warm up", "date": "2026-10-05",
    "recurrence": {"freq": "weekly"}, "overrides": copy_mod.deepcopy(_off_days)})
_rs_copy = _model_mod.copy_replaced_by_restore(
    _rs_note, {"title": "Gym", "body": "Warm up", "recurrence": {}})
check("a restore that ends a repeat keeps the series' days in its copy",
      _rs_copy is not None and _rs_copy.get("overrides") == _off_days
      and (_rs_copy.get("recurrence") or {}).get("freq") == "weekly")

# What a save loses is measured in cells, not in the padding lining a table
# up: one cell grown wider re-pads every row, and read as the whole table
# lost, its copy replaced the rescue copy the note held (2026-10-28).
_pad_old = ("Shopping\n| Item     | Qty |\n| -------- | --- |\n| milk     | 1   |\n"
            "| bread    | 2   |\n| eggs     | 12  |\n| apples   | 6   |")
_pad_new = ("Shopping\n| Item                  | Qty |\n| --------------------- | --- |\n"
            "| oat milk, semi-skimmed | 1   |\n| bread                 | 2   |\n"
            "| eggs                  | 12  |\n| apples                | 6   |")
check("a cell grown wider is no loss to keep a copy for",
      not _model_mod.rescue_copy_due("List", _pad_old, "List", _pad_new))
check("...while a table emptied of its rows still is",
      _model_mod.rescue_copy_due("List", _pad_old, "List", "Shopping\n| Item | Qty |\n| --- | --- |"))
# ...nor a change made to every row: a column added or an empty one removed,
# a numbered list renumbered by a step put in, each read as the whole span
# between its first and last change lost, and its copy replaced the one the
# note held.
_col_old = "\n".join(["Pie"] + ["| %s | %d |" % (w, i) for i, w in enumerate(
    ["flour", "butter", "sugar", "apples", "cinnamon", "lemon", "salt", "egg"])])
_col_new = "\n".join(line + "  |" if line.startswith("|") else line
                     for line in _col_old.split("\n"))
_steps = "\n".join("%d. Step number %d of the recipe" % (i, i) for i in range(1, 13))
_steps_in = _steps.replace("1. Step number 1 of the recipe",
                           "1. Step number 1 of the recipe\n2. Wash the bowl")
for i in range(12, 1, -1):
    _steps_in = _steps_in.replace("\n%d. Step number %d" % (i, i),
                                  "\n%d. Step number %d" % (i + 1, i))
_cjk = "今天我们讨论了下个季度的计划以及每个人负责的部分和截止日期" * 3
check("a column added, removed empty, or a list renumbered is no loss either "
      "(%s)" % [_model_mod.rescue_copy_due("t", a, "t", b) for a, b in (
          (_col_old, _col_new), (_col_new, _col_old), (_steps, _steps_in))],
      not _model_mod.rescue_copy_due("t", _col_old, "t", _col_new)
      and not _model_mod.rescue_copy_due("t", _col_new, "t", _col_old)
      and not _model_mod.rescue_copy_due("t", _steps, "t", _steps_in))
# ...nor a list's markers changed: numbers turned to bullets, or bullets one
# level in, counted each "1." as a word lost, and the copy of a paragraph
# deleted before was replaced (found on Android first).
_mk_items = ["milk", "eggs", "bread", "butter", "flour", "sugar", "salt",
             "apples", "pears", "rice", "beans", "tea", "coffee", "onion"]
_mk_num = "\n".join("%d. %s" % (i + 1, w) for i, w in enumerate(_mk_items))
_mk_bul = "\n".join("• " + w for w in _mk_items)
_mk_in = "\n".join("◦ " + w for w in _mk_items)
from collections import Counter as _Counter
# The markers counted as words would pass the bars: what this check rules out.
_mk_as_words = sum((len(w) + 1) * n for w, n in
                   (_Counter(_mk_num.split()) - _Counter(_mk_bul.split())).items())
check("...nor a list's markers changed: numbers to bullets, bullets one level in "
      "(as words %d, now %d)" % (_mk_as_words, _model_mod.words_lost(_mk_num, _mk_bul)),
      not _model_mod.rescue_copy_due("t", _mk_num, "t", _mk_bul)
      and not _model_mod.rescue_copy_due("t", _mk_bul, "t", _mk_in)
      and _mk_as_words > 40 and _model_mod.text_lost(_mk_num, _mk_bul) > 0.3 * len(_mk_num)
      and _model_mod.rescue_copy_due("t", _mk_num, "t", "\n".join(_mk_num.split("\n")[:3])))
check("...nor one letter changed in a paragraph written without spaces",
      not _model_mod.rescue_copy_due("t", _cjk, "t", _cjk.replace("季度", "月份", 1)))
_col_full = "\n".join(line + " a long note about where to buy it |"
                      if line.startswith("|") else line for line in _col_old.split("\n"))
check("...while a column of words deleted still keeps one",
      _model_mod.rescue_copy_due("t", _col_full, "t", _col_old))
# ...and so do five rows of eight: words gone were set against a length that
# counts the padding, and half a table read as a quarter.
from noteorganizer.core import tables as _tables_mod
# Short cells, as a shopping list's: their padding is most of each row.
_trip_lines = ["Groceries"] + _tables_mod.format_table([["Item", "Qty", "Ok"]] + [
    list(row) for row in (("tea", "1", "y"), ("jam", "2", "n"), ("oat", "1", "y"),
                          ("egg", "6", "y"), ("fig", "3", "n"), ("rye", "1", "y"),
                          ("soy", "2", "n"), ("nut", "4", "y"))])
_trip_old = "\n".join(_trip_lines)
_trip_cut = "\n".join(_trip_lines[:2] + _trip_lines[7:])
_trip_lost = _model_mod._lost(_trip_old, _trip_cut)
check("...and five rows of a table's eight deleted at once keep one (%d of %d "
      "characters, %d lost)" % (len(_trip_cut), len(_trip_old), _trip_lost),
      _model_mod.rescue_copy_due("t", _trip_old, "t", _trip_cut)
      and 40 < _trip_lost < 0.3 * len(_trip_old))
# The comments are a text the copy holds, and the measure left them out: 780
# characters of them replaced by "ok" kept no copy. Weighed as a
# text of their own, so a long comment does not make a whole body deleted
# read as a small share either.
_cm_long = " ".join("Remember the vet said %d grams a day" % i for i in range(24))
_cm_body = "Walk the dog twice a day and keep the lead short near the road."
check("comments replaced keep a copy, weighed as a text of their own",
      _model_mod.rescue_copy_due("Dog", _cm_body, "Dog", _cm_body, _cm_long, "ok")
      and _model_mod.rescue_copy_due("Dog", _cm_body, "Dog", _cm_body, _cm_long, "")
      and _model_mod.rescue_copy_due("Dog", _cm_body, "Dog", "", _cm_long, _cm_long)
      and not _model_mod.rescue_copy_due("Dog", _cm_body, "Dog", _cm_body,
                                         _cm_long, _cm_long + " Buy food.")
      and not _model_mod.rescue_copy_due("Dog", _cm_body, "Dog", _cm_body, "", "new"))

# A repeat turned off keeps its days' own text in the note here; the phone,
# and this app before the fix, kept them only in the rescue copy, which the
# next copy erased (the owner's choice: one place, the note). Brought back
# into the note as it is read, once.
_kd_series = {"date": "2026-11-02", "recurrence": {"freq": "weekly", "interval": 1}}
_kd_days = {"overrides": {"2026-11-09": {"body": "Leg day - knee hurt"}},
            "exceptions": ["2026-11-16"]}
_kd_turned_off = _model_mod.normalize_note({
    "id": 1, "title": "Gym", "body": "Warm up.",
    "_prev": dict({"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days)})
# A copy that does not repeat holds days an update replaced on purpose:
# left as it is (the phone's copies of words that carried days were never
# released, only its turn-off copies, which repeat).
_kd_carried = _model_mod.normalize_note({
    "id": 2, "title": "Gym", "body": "Warm up.",
    "_prev": dict({"title": "Gym", "body": "Warm up. Physio said no squats."}, **_kd_days)})
_kd_empty_days = _model_mod.normalize_note({   # days with no text of their own
    "id": 3, "title": "Gym", "body": "Warm up.",
    "_prev": dict({"title": "Gym", "body": "Warm up."}, exceptions=["2026-11-16"], **_kd_series)})
# Repeating again on another start: the old series' days are not its own.
_kd_live = _model_mod.normalize_note({
    "id": 4, "title": "Gym", "body": "Warm up.", "date": "2026-11-03",
    "recurrence": {"freq": "weekly", "interval": 1}, "_prev": dict(_kd_series, **_kd_days)})
check("an older notebook's days kept only in the rescue copy come back into the note",
      _kd_turned_off["overrides"] == _kd_days["overrides"]
      and _kd_turned_off["exceptions"] == ["2026-11-16"]
      and _kd_turned_off["_prev"].get("overrides") == _kd_days["overrides"])
check("...but not days that hold no text of their own, nor an update's copy that does "
      "not repeat, nor a note repeating from another start, and a second read changes nothing",
      _kd_empty_days["exceptions"] == [] and _kd_empty_days["overrides"] == {}
      and _kd_carried["overrides"] == {} and _kd_carried["_prev"].get("overrides") == _kd_days["overrides"]
      and _kd_live["overrides"] == {} and _kd_live["_prev"].get("overrides") == _kd_days["overrides"]
      and _model_mod.normalize_note(_kd_turned_off) == _kd_turned_off
      and _model_mod.normalize_note(_kd_carried) == _kd_carried)
# The phone's 0.12.0 turned a series back on as it was with none of its days:
# repeating, the copy the same series, its days' text in the copy alone, which
# the next copy of words erased.
_kd_back_on = _model_mod.normalize_note(dict(
    {"id": 5, "title": "Gym", "body": "Warm up.", "_prev": dict(
        {"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days)}, **_kd_series))
check("a series the phone turned back on as it was takes its days back from its copy",
      _kd_back_on["overrides"] == _kd_days["overrides"]
      and _kd_back_on["exceptions"] == ["2026-11-16"])
# An update's copy repeats when the series here did, and holds the days the
# update replaced on purpose: taken in, the same backup imported again read
# as a change, and its Update spent the only earlier version.
_kd_updated = _model_mod.normalize_note(dict(
    {"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days))
_kd_updated["uid"] = "kd-updated"
_kd_backup = {"uid": "kd-updated", "title": "Gym", "body": "Rowing only.",
              "created": _kd_updated["created"]}
_model_mod.apply_shared_update(_kd_updated, _kd_backup, _model_mod.UPDATABLE_FROM_BACKUP)
_kd_reread = _model_mod.normalize_note(_kd_updated)
check("an update's copy of a series gives no days back, and the same backup "
      "again changes nothing (%s)" % sorted(
          f for f in _model_mod.UPDATABLE_FROM_BACKUP
          if _model_mod.normalize_note(dict(_kd_reread))[f]
          != _model_mod.normalize_note(dict(_kd_backup))[f]),
      _model_mod.is_recurring(_kd_updated["_prev"])
      and "category" in _kd_updated["_prev"]
      and _kd_reread["overrides"] == {} and _kd_reread["exceptions"] == []
      and not _model_mod.shared_update_changes(
          _kd_reread, _kd_backup, _model_mod.UPDATABLE_FROM_BACKUP))
# ...nor does a copy of the series taking days a moment ago make the note,
# held in memory, differ from the same note arriving again.
_kd_mem = dict(_kd_turned_off, overrides={}, exceptions=[])
check("a note's rescue copy never makes the same note arriving again read as changed",
      not _model_mod.shared_update_changes(
          _kd_mem, {k: v for k, v in _kd_mem.items() if k != "_prev"},
          _model_mod.UPDATABLE_FROM_BACKUP))
# Taken back into a note that repeats as the copy's series, the copy's days
# were kept as well: a day the person then reset came back at every read.
# Once the note repeats as that series, the copy's are spent --
# here, and in a copy a turn-off left that holds them beside the note's.
_kd_reset = _model_mod.normalize_note(dict(_kd_back_on, overrides={}, exceptions=[]))
_kd_beside = _model_mod.normalize_note(dict(
    {"id": 9, "title": "Gym", "body": "Warm up. And stretch.", "_prev": dict(
        {"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days)}, **_kd_series, **_kd_days))
check("once a note repeats as its copy's series, the copy's days are spent, and a day reset "
      "stays reset (%s, %s)" % (sorted(_kd_back_on["_prev"]), sorted(_kd_reset["overrides"])),
      not any(key in _kd_back_on["_prev"] for key in _model_mod.DAY_FIELDS)
      and _kd_reset["overrides"] == {} and _kd_reset["exceptions"] == []
      and _kd_beside["overrides"] == _kd_days["overrides"]
      and not any(key in _kd_beside["_prev"] for key in _model_mod.DAY_FIELDS)
      and _kd_turned_off["_prev"].get("overrides") == _kd_days["overrides"])
# ...and an arriving note is read as a load reads it, its copy's days taken
# back: an older backup of a turned-off series, compared bare, lacked the days
# the same notebook here holds and read as edited elsewhere. One
# whose copy holds a day reset here since holds that day: a real difference.
_kd_old_off = {"id": 1, "title": "Gym", "body": "Warm up.",
               "_prev": dict({"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days)}
_kd_old_on = dict(_kd_reset, _prev=dict(
    {"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days))
check("an older backup of a series, turned off or back on, reads as the notebook it came "
      "from read here; one whose copy holds a day reset here since reads as changed",
      not _model_mod.shared_update_changes(
          _kd_turned_off, _kd_old_off, _model_mod.UPDATABLE_FROM_BACKUP)
      and not _model_mod.shared_update_changes(
          _kd_back_on, dict(_kd_back_on, overrides={}, exceptions=[], _prev=dict(
              {"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days)),
          _model_mod.UPDATABLE_FROM_BACKUP)
      and _model_mod.shared_update_changes(
          _kd_reset, _kd_old_on, _model_mod.UPDATABLE_FROM_BACKUP))

# The copy's days come back per date: a note that repeats as the copy's
# series again and holds a day of its own -- edited after 0.97.405 or the
# phone's 0.12.0 turned it back on with none -- took none back, and the spend
# erased the copy's own-text day for good.
_kd_own = {"2026-11-23": {"body": "Rest week"}}
_kd_some = _model_mod.normalize_note(dict(
    {"id": 12, "title": "Gym", "body": "Warm up.", "overrides": _kd_own, "_prev": dict(
        {"title": "Gym", "body": "Warm up."}, **_kd_series, **_kd_days)}, **_kd_series))
check("a note repeating as its copy's series again takes back each of the copy's days on a "
      "date it leaves free, then the copy's are spent (%s)" % sorted(_kd_some["overrides"]),
      _kd_some["overrides"] == dict(_kd_own, **_kd_days["overrides"])
      and _kd_some["exceptions"] == ["2026-11-16"]
      and not any(key in _kd_some["_prev"] for key in _model_mod.DAY_FIELDS)
      and _model_mod.normalize_note(_kd_some) == _kd_some)
# The note's own day wins its date; a move never goes onto a date it holds.
_kd_mine = _model_mod.normalize_note(dict(
    {"id": 13, "title": "Gym", "body": "Warm up.",
     "overrides": {"2026-11-09": {"body": "Swim instead"}},
     "moved": {"2026-11-30": "2026-12-01"}, "_prev": dict(
         {"title": "Gym", "body": "Warm up."}, overrides={}, exceptions=["2026-11-09"],
         moved={"2026-11-23": "2026-12-01", "2026-12-07": "2026-12-08"}, **_kd_series)},
    **_kd_series))
check("the note's own day keeps its date over the copy's, and the copy's move onto a date "
      "the note holds is dropped, the note's own move kept (%s, %s)" % (
          _kd_mine["moved"], _kd_mine["exceptions"]),
      _kd_mine["overrides"] == {"2026-11-09": {"body": "Swim instead"}}
      and _kd_mine["exceptions"] == []
      and _kd_mine["moved"] == {"2026-11-30": "2026-12-01", "2026-12-07": "2026-12-08"})
# A copy holding only deleted days: they come back too, so the days the person
# deleted before trying another start stay deleted when it is put back.
_kd_gone = _model_mod.normalize_note(dict(
    {"id": 14, "title": "Gym", "body": "Warm up.", "_prev": dict(
        {"title": "Gym", "body": "Warm up."}, exceptions=["2026-11-16"], **_kd_series)},
    **_kd_series))
check("a series' deleted days kept only in its copy stay deleted once it repeats as that "
      "series again", _kd_gone["exceptions"] == ["2026-11-16"]
      and "exceptions" not in _kd_gone["_prev"])

# A date the note holds with no words of its own -- the same day moved, or
# only coloured, after 0.97.405 or the phone's 0.12.0 turned the repeat back
# on -- spent the copy's own text for that day at the first start.
# The rule: a copy's day is dropped only where the note deleted that day or
# wrote words of its own for it; its words go where the note draws the day.
from noteorganizer.core import recurrence as _rec_t10
_t10_word = {"body": "Dentist 3pm"}


def _t10(days, copy_days=None):
    """A note repeating as its copy's series, holding *days*; the copy holds
    *copy_days* (by default 11-09's own text alone), read as a load reads it."""
    copy_days = {"overrides": {"2026-11-09": dict(_t10_word)}} if copy_days is None else copy_days
    return _model_mod.normalize_note(dict(
        {"id": 20, "title": "Gym", "body": "Warm up.", "_prev": dict(
            {"title": "Gym", "body": "Warm up."}, **_kd_series, **copy_days)},
        **_kd_series, **days))


def _t10_shows(note, day):
    """The words the calendar shows on *day* for *note*, or None: no day there."""
    when = _rec_t10.parse_date(day)
    if day not in _rec_t10.expand_occurrences(note, when, when):
        return None
    return _rec_t10.effective_note(note, day).get("body")


_t10_moved = _t10({"moved": {"2026-11-09": "2026-11-10"}})
_t10_desk = _t10({"overrides": {"2026-11-09": {"title": "Gym", "body": "Warm up.", "comments": "",
                                               "color": "#ff6b6b", "category": "Work"}}})
_t10_phone = _t10({"overrides": {"2026-11-09": {"color": "#ff6b6b"}}})
check("the copy's own text for a day the note moved goes with the day, and for a day it "
      "only coloured goes into that day, its colour and category kept (%s, %s, %s)" % (
          _t10_moved["overrides"], _t10_desk["overrides"], _t10_phone["overrides"]),
      _t10_shows(_t10_moved, "2026-11-10") == "Dentist 3pm"
      and _t10_moved["moved"] == {"2026-11-09": "2026-11-10"}
      and _t10_desk["overrides"]["2026-11-09"] == {"body": "Dentist 3pm", "color": "#ff6b6b",
                                                   "category": "Work"}
      and _t10_phone["overrides"]["2026-11-09"] == {"body": "Dentist 3pm", "color": "#ff6b6b"}
      and not any(key in n["_prev"] for n in (_t10_moved, _t10_desk, _t10_phone)
                  for key in _model_mod.DAY_FIELDS))
# The copy's move that cannot be placed leaves its words with the day: the
# note moved another day onto its date, or coloured the day where it stood.
_t10_copy_moved = {"moved": {"2026-11-09": "2026-11-10"},
                   "overrides": {"2026-11-10": dict(_t10_word)}}
_t10_onto = _t10({"moved": {"2026-11-16": "2026-11-10"}}, _t10_copy_moved)
_t10_stood = _t10({"overrides": {"2026-11-09": {"color": "#ff6b6b"}}}, _t10_copy_moved)
check("a copy's move the note's days leave no room for keeps its words on the day, where the "
      "note draws it (%s, %s)" % (_t10_onto["overrides"], _t10_stood["overrides"]),
      _t10_shows(_t10_onto, "2026-11-09") == "Dentist 3pm"
      and _t10_onto["moved"] == {"2026-11-16": "2026-11-10"}
      and _t10_shows(_t10_onto, "2026-11-10") == "Warm up."
      and _t10_shows(_t10_stood, "2026-11-09") == "Dentist 3pm"
      and _t10_stood["overrides"]["2026-11-09"].get("color") == "#ff6b6b"
      and _t10_stood["moved"] == {})
# A day moved onto a date whose own day the copy moved away, that move left
# behind: both stay home, each with its words, none hidden under the other.
_t10_chain = _t10({"moved": {"2026-11-23": "2026-11-10"}}, {
    "moved": {"2026-11-09": "2026-11-10", "2026-11-16": "2026-11-09"},
    "overrides": {"2026-11-10": {"body": "Monday 9th's words"},
                  "2026-11-09": {"body": "Monday 16th's words"}}})
check("a copy's move onto a day whose own move stays behind stays behind too, each day's "
      "words on its own date (%s, %s)" % (_t10_chain["moved"], _t10_chain["overrides"]),
      _t10_chain["moved"] == {"2026-11-23": "2026-11-10"}
      and _t10_shows(_t10_chain, "2026-11-09") == "Monday 9th's words"
      and _t10_shows(_t10_chain, "2026-11-16") == "Monday 16th's words")
# An edit the copy draws on no day -- under a date its day was moved from, a
# shape neither app writes -- stays on its date, beside the day's own words.
# The note holds a day of its own, so the days come back one by one.
_t10_stray = _t10({"overrides": {"2026-11-30": {"body": "Rest week"}}}, {
    "moved": {"2026-11-09": "2026-11-10"},
    "overrides": {"2026-11-10": dict(_t10_word), "2026-11-09": {"body": "Stray words"}}})
check("an edit the copy draws on no day stays on its own date, beside its day's own words "
      "(%s)" % _t10_stray["overrides"],
      _t10_shows(_t10_stray, "2026-11-10") == "Dentist 3pm"
      and (_t10_stray["overrides"].get("2026-11-09") or {}).get("body") == "Stray words")

def _t10_aside(note):
    """The copy's days *note* set aside, as (date, text) pairs."""
    return [(entry["day"], entry["body"]) for entry in note.get("_set_aside") or []]


# What the note wrote still wins: its deletion, and its own words as they are
# -- the copy's for that day are set aside, to be a note of their own on that
# date (the owner's choice: added to the day's, four earlier fixes read them
# four ways, each leaving a case; and, her choice again, for a day deleted
# too, the phone's older build having shown it blank).
_t10_gone = _t10({"exceptions": ["2026-11-09"]}, _t10_copy_moved)
_t10_own = _t10({"moved": {"2026-11-09": "2026-11-10"},
                 "overrides": {"2026-11-10": {"body": "Swim instead"}}})
check("a day the note deleted keeps the note's; one it wrote words for keeps them as they are, the "
      "copy's set aside for that date (%s, %s)" % (_t10_own["overrides"], _t10_aside(_t10_own)),
      "Dentist" not in json.dumps(_t10_gone.get("overrides")) and _t10_gone["exceptions"] == ["2026-11-09"]
      and _t10_aside(_t10_gone) == [("2026-11-10", "Dentist 3pm")]
      and _t10_own["overrides"] == {"2026-11-10": {"body": "Swim instead"}}
      and _t10_aside(_t10_own) == [("2026-11-10", "Dentist 3pm")])

# A day coloured before the series' words changed holds the old words, read
# as its own: the copy's for that day were in no file after the first start of
# this build over 0.97.405's notebook, or the phone's 0.12.0. Now
# the day stays as it is and the copy's words are set aside. Read again,
# nothing changes and nothing is set aside twice.
_t11 = _model_mod.normalize_note(dict(
    {"id": 21, "title": "Gym", "body": "Warm up.\nBring water.", "_prev": dict(
        {"title": "Gym", "body": "Warm up."}, **_kd_series,
        overrides={"2026-11-09": dict(_t10_word)})},
    **_kd_series, overrides={"2026-11-09": {"title": "Gym", "body": "Warm up.", "comments": "",
                                            "color": "#ff6b6b", "category": "Work"}}))
check("a day coloured before the series' words changed keeps its words and look, the copy's words "
      "for it set aside, the copy spent, and a second read changes nothing (%s, %s)" % (
          _t11["overrides"], _t10_aside(_t11)),
      _t11["overrides"]["2026-11-09"]["body"] == "Warm up."
      and _t11["overrides"]["2026-11-09"]["color"] == "#ff6b6b"
      and _t10_aside(_t11) == [("2026-11-09", "Dentist 3pm")]
      and "overrides" not in _t11["_prev"]
      and _model_mod.normalize_note(json.loads(json.dumps(_t11))) == _t11)
# ...a day whose words the note holds too is left as it is, its series renamed
# since: the series' words are not the day's.
_t11_held = _model_mod.normalize_note(dict(
    {"id": 22, "title": "Gym!", "body": "Warm up.", "_prev": dict(
        {"title": "Gym", "body": "Warm up."}, **_kd_series,
        overrides={"2026-11-09": dict(_t10_word)})},
    **_kd_series, overrides={"2026-11-09": dict(_t10_word)}))
# ...and two of the copy's days for one date -- the note moved its day onto a
# day off the copy's schedule holding words of its own: one goes on the day,
# the other is set aside.
_t11_tie = _t10({"moved": {"2026-11-16": "2026-11-10"}},
                {"overrides": {"2026-11-10": {"body": "Off-schedule words"},
                               "2026-11-16": {"body": "Monday 16th's own"}}})
check("a copy's day the note holds again is left as it is, nothing set aside; of two for one date, "
      "one is on the day and the other set aside (%s, %s)" % (_t11_held["overrides"], _t11_tie["overrides"]),
      _t11_held["overrides"] == {"2026-11-09": _t10_word} and "overrides" not in _t11_held["_prev"]
      and not _t10_aside(_t11_held)
      and _t10_shows(_t11_tie, "2026-11-10") == "Monday 16th's own"
      and _t10_aside(_t11_tie) == [("2026-11-10", "Off-schedule words")]
      and "overrides" not in _t11_tie["_prev"])
# A day whose words differ from the copy's in any way -- grown from them,
# corrected in a line, a table cell edited, a box ticked -- keeps its text to
# the letter, and the copy's whole text is set aside once. Two earlier fixes
# added only the lines the day lacked, and each way of telling them apart
# left a case: a moved line added again, a long day frozen.
_t13_grown = _t10({"overrides": {"2026-11-09": {"body": "Agenda.\nBook room\nCancelled"}}},
                  {"overrides": {"2026-11-09": {"title": "", "body": "Agenda.\nBook room"}}})
_t14_cell = _t10({"overrides": {"2026-11-09": {"body": "Plan\n| Task | Who        |\n| ---- | ---------- |\n"
                                                       "| Room | Ann (done) |\n| Food | Bob        |"}}},
                 {"overrides": {"2026-11-09": {"body": "Plan\n| Task | Who |\n| ---- | --- |\n"
                                                       "| Room | Ann |\n| Food | Bob |"}}})
_t14_box = _t10({"overrides": {"2026-11-09": {"body": "| Done | Task |\n| --- | --- |\n| [x] | Lunch |"}}},
                {"overrides": {"2026-11-09": {"body": "| Done | Task |\n| --- | --- |\n| [ ] | Lunch |"}}})
_t13_again = _model_mod.normalize_note(json.loads(json.dumps(_t14_cell)))
check("a day grown from the copy's text, a cell edited or a box ticked keeps its text to the letter; "
      "the copy's is set aside once, whole, and a second read sets nothing aside again (%s, %s, %s)" % (
          _t10_aside(_t13_grown), _t10_aside(_t14_cell), _t10_aside(_t14_box)),
      _t13_grown["overrides"]["2026-11-09"]["body"] == "Agenda.\nBook room\nCancelled"
      and _t14_cell["overrides"]["2026-11-09"]["body"].startswith("Plan\n| Task | Who        |\n")
      and _t14_box["overrides"]["2026-11-09"]["body"] == "| Done | Task |\n| --- | --- |\n| [x] | Lunch |\n"
      and _t10_aside(_t13_grown) == [("2026-11-09", "Agenda.\nBook room")]
      and [day for day, _text in _t10_aside(_t14_cell)] == ["2026-11-09"]
      and "| Room | Ann |" in _t10_aside(_t14_cell)[0][1]
      and len(_t10_aside(_t14_box)) == 1
      and _t13_again == _t14_cell)
# Read alike as a day's words: a title with a space after it, and a text
# ending in a table with the line under it or without -- the phone keeps its
# series' text as typed, its days with the line. Read apart, a day only
# coloured was set aside as earlier text, or took none.
_t15_tbl = "Plan\n| a | b |\n| --- | --- |\n| 1 | 2 |"
_t15_alike = _model_mod.normalize_note(dict(
    {"id": 27, "title": "Gym", "body": "Warm up.", "_prev": dict(
        {"title": "Gym", "body": _t15_tbl}, **_kd_series,
        overrides={"2026-11-16": {"title": "Gym ", "body": _t15_tbl + "\n", "color": "#ff6b6b"}})},
    **_kd_series, overrides={"2026-11-16": {"body": "Own words"}}))
_t15_spaced = _t10({"overrides": {"2026-11-09": {"title": "Gym ", "body": "Warm up.", "color": "#ff6b6b"}}})
check("a copy's day only coloured, its title with a space after it or its table with the line under "
      "it, is no earlier text; a note's day the same takes the copy's words (%s, %s)" % (
          _t10_aside(_t15_alike), _t15_spaced["overrides"]),
      not _t10_aside(_t15_alike) and _t15_alike["overrides"]["2026-11-16"] == {"body": "Own words"}
      and _t10_shows(_t15_spaced, "2026-11-09") == "Dentist 3pm")
# A note of its own is made of each day set aside: on its date, its words and
# look, the series' title marked as the earlier text -- and taken off the note.
_t15_made = _model_mod.notes_set_aside(_t13_grown)
check("a day set aside becomes a note on its date, titled with the series' name and \"(earlier "
      "text)\", and leaves the note (%s)" % _t15_made,
      _t15_made == [{"title": "Gym (earlier text)", "body": "Agenda.\nBook room", "comments": "",
                     "category": "General", "color": "", "date": "2026-11-09"}]
      and "_set_aside" not in _t13_grown
      and _model_mod.normalize_note(dict(_t15_made[0], id=99))["date"] == "2026-11-09")
# Read from a file, the days set aside keep a real date in the calendar's
# form and a word; anything else in the list is not a day.
_t15_read = _model_mod.normalize_note({"id": 28, "title": "Gym", "_set_aside": [
    {"day": " 2026-11-9 ", "body": "Kept", "color": 5}, {"day": 5, "body": "No date"},
    "not a day", {"day": "2026-11-10", "body": "   "}, {"day": "2026-11-11", "title": "Only a title"}]})
check("days set aside read from a file keep a real date in the calendar's form and a word (%s)"
      % _t10_aside(_t15_read),
      _t10_aside(_t15_read) == [("2026-11-09", "Kept"), ("2026-11-11", "")]
      and (_t15_read.get("_set_aside") or [{}])[0].get("color") == "")
# A copy of another series than the note's repeats as now is replaced by the
# next turn-off, delete or import Update: its days with words were in it
# alone, and the new copy erased them. Set aside first.
_t15_other = _model_mod.normalize_note(dict(
    {"id": 23, "title": "Gym", "body": "Warm up.", "_prev": {
        "title": "Gym", "body": "Warm up.", "date": "2026-11-03",
        "recurrence": {"freq": "weekly", "interval": 1, "weekdays": [1]},
        "overrides": {"2026-11-10": {"body": "Tuesday words"},
                      "2026-11-17": {"color": "#ff6b6b"}}}}, **_kd_series))
_t15_waits = "overrides" in _t15_other["_prev"] and not _t10_aside(_t15_other)
_t15_update = copy_mod.deepcopy(_t15_other)
_model_mod.apply_shared_update(_t15_update, dict(_t15_other, body="Warm up. Stretch.", _prev=None),
                               _model_mod.UPDATABLE_FROM_BACKUP)
_model_mod.copy_days_set_aside(_t15_other)
check("another series' copy keeps its days while it waits, and sets aside those with words before "
      "a turn-off or an import's Update replaces it (%s, %s)" % (
          _t10_aside(_t15_other), _t10_aside(_t15_update)),
      _t15_waits and _t10_aside(_t15_other) == [("2026-11-10", "Tuesday words")]
      and not any(key in _t15_other["_prev"] for key in _model_mod.DAY_FIELDS)
      and _t10_aside(_t15_update) == [("2026-11-10", "Tuesday words")]
      and _t15_update["_prev"]["body"] == "Warm up.")
# A day moved onto a date its rule now gives by itself -- made daily since, or
# started elsewhere -- was drawn nowhere, and a delete there took it: its move
# goes, its words staying where they showed (the owner's choice: words never
# move on their own). A chain (the 9th to the
# 10th, the 16th onto the 9th it left) holds while the rule leaves the dates
# free; and a day deleted there leaves its date free too.
_t15_chain = {"moved": {"2026-11-09": "2026-11-10", "2026-11-16": "2026-11-09"},
              "overrides": {"2026-11-10": {"body": "Ninth's words"}, "2026-11-09": {"body": "16th's words"}}}
_t15_weekly = _model_mod.normalize_note(dict({"id": 24, "title": "Gym", "body": "x"}, **_kd_series,
                                             **copy_mod.deepcopy(_t15_chain)))
_t15_daily = _model_mod.normalize_note(dict(
    {"id": 25, "title": "Gym", "body": "x", "date": "2026-11-02",
     "recurrence": {"freq": "daily", "interval": 1}}, **copy_mod.deepcopy(_t15_chain)))
_t15_freed = _model_mod.normalize_note(dict(
    {"id": 26, "title": "Gym", "body": "x", "date": "2026-11-02", "exceptions": ["2026-11-10"],
     "recurrence": {"freq": "daily", "interval": 1}}, moved={"2026-11-09": "2026-11-10"},
    overrides={"2026-11-10": {"body": "N"}}))
check("a day moved onto a date its rule now gives loses its move, its words where they showed, a chain "
      "of moves too, while a chain on dates the rule leaves free, or a deleted day's date, holds (%s, %s)" % (
          _t15_daily["moved"], _t15_daily["overrides"]),
      _t15_weekly["moved"] == _t15_chain["moved"]
      and _t15_daily["moved"] == {}
      and _t10_shows(_t15_daily, "2026-11-10") == "Ninth's words"
      and _t10_shows(_t15_daily, "2026-11-09") == "16th's words"
      and _t10_shows(_t15_daily, "2026-11-16") == "x"
      and _model_mod.normalize_note(json.loads(json.dumps(_t15_daily))) == _t15_daily
      and _t15_freed["moved"] == {"2026-11-09": "2026-11-10"})
# ...and at once when a share code makes the series daily, not at the next start.
_t15_coded = _model_mod.normalize_note(dict({"id": 29, "uid": "coded", "title": "Gym", "body": "x"},
                                            **_kd_series, moved={"2026-11-09": "2026-11-10"},
                                            overrides={"2026-11-10": {"body": "Held on Tuesday"}}))
_model_mod.apply_shared_update(_t15_coded, {"uid": "coded", "title": "Gym", "body": "x", "date": "2026-11-02",
                                            "recurrence": {"freq": "daily"}})
check("a share code making the series daily drops a move onto its new days at once, the words where "
      "they showed (%s, %s)" % (_t15_coded["moved"], _t15_coded["overrides"]),
      _t15_coded["moved"] == {} and _t10_shows(_t15_coded, "2026-11-10") == "Held on Tuesday")
# Days set aside are capped as moved days are: each becomes a note at the next
# start, and a file can say anything; a save empties the list each time.
_t15_flood = _model_mod.normalize_note({"id": 30, "title": "Gym", "body": "x", "_set_aside": [
    {"day": "2026-11-09", "body": "words %d" % i} for i in range(_model_mod.MAX_OCCURRENCES + 1)]})
check("a file's days set aside are read at most as many as a series' moved days (%d)"
      % len(_t15_flood.get("_set_aside") or []),
      len(_t15_flood.get("_set_aside") or []) == _model_mod.MAX_OCCURRENCES
      and _t15_flood["_set_aside"][0]["body"] == "words 0")
# A day goes home only where the rule still gives its own date:
# moved onto a Thursday, the series then on Thursdays, its words stay on the
# Thursday they showed on, and the move goes -- sent "home" to a Monday the
# rule no longer gives, they left the calendar.
_t16_thu = _model_mod.normalize_note({"id": 31, "title": "Gym", "body": "plan", "date": "2026-11-05",
                                      "recurrence": {"freq": "weekly"}, "moved": {"2026-11-09": "2026-11-12"},
                                      "overrides": {"2026-11-12": {"body": "dentist at 4"}}})
check("a day moved onto a date the rule now gives, its own date no longer the rule's, keeps its words "
      "where they showed (%s, %s)" % (_t16_thu["moved"], sorted(_t16_thu["overrides"])),
      _t16_thu["moved"] == {} and _t10_shows(_t16_thu, "2026-11-12") == "dentist at 4"
      and "2026-11-09" not in _t16_thu["overrides"])


class _T16Walked(dict):
    """A note's moves that count each walk over them, and each move read."""
    walks = reads = 0

    def __iter__(self):
        _T16Walked.walks += 1
        return super().__iter__()

    def items(self):
        _T16Walked.walks += 1
        return super().items()

    def __getitem__(self, day):
        _T16Walked.reads += 1
        return super().__getitem__(day)


# ...and a chain is walked once, not a pass a link: 2,000 links under a daily
# rule took the square of that, and a crafted backup froze the window. Two
# days moved onto each other's dates stay: neither date is free.
_t16_days = [(_dtT.date(2026, 11, 2) + _dtT.timedelta(days=i)).isoformat() for i in range(2001)]
_t16_chain = {"id": 32, "title": "Gym", "body": "x", "date": "2026-11-02",
              "recurrence": {"freq": "daily", "interval": 1}, "exceptions": [],
              "moved": _T16Walked({_t16_days[i]: _t16_days[i + 1] for i in range(2000)}),
              "overrides": {_t16_days[2000]: {"body": "the last"}}}
_model_mod.drop_hidden_moves(_t16_chain)
_t16_swap = _model_mod.normalize_note({"id": 35, "title": "Gym", "body": "x", "date": "2026-11-02",
                                       "recurrence": {"freq": "daily"},
                                       "moved": {"2026-11-09": "2026-11-10", "2026-11-10": "2026-11-09"}})
check("a chain of 2,000 moved days, every date the rule's, goes home walking the moves once, "
      "not once a link; two days swapped stay (%d walks, %d reads; %s)"
      % (_T16Walked.walks, _T16Walked.reads, _t16_swap["moved"]),
      _T16Walked.walks <= 3 and _T16Walked.reads <= 2 * 2000 + 10 and _t16_chain["moved"] == {}
      and _t16_chain["overrides"] == {_t16_days[2000]: {"body": "the last"}}
      and _t16_swap["moved"] == {"2026-11-09": "2026-11-10", "2026-11-10": "2026-11-09"})
# ...and a note made of a day set aside has words: one with none -- an
# untitled series whose day's text was emptied -- made an empty note at a
# save, and none at the start.
check("days set aside with no words make no note, at a save as at the start",
      _model_mod.notes_set_aside({"title": "", "_set_aside": [
          {"day": "2026-11-09", "title": "", "body": "", "comments": "", "category": "", "color": "#ff0000"}]})
      == [])
# A week shifted a day at a time (Wed to Thu, Tue to Wed, Mon to
# Tue), then the shift made the rule (Tue-Thu): an earlier fix sent words
# home one by one and wrote what was left over the Wednesday's -- one day's
# text in no file. Words now never move on their own (the owner's choice):
# the moves go, each day's words staying where they showed; a date's own
# words stay too.
_t17_week = {"freq": "weekly", "interval": 1, "weekdays": [0, 1, 2]}
_t17_copy_day = {"title": "Gym", "body": "x", "comments": "", "formatting": [], "paragraphs": [],
                 "recurrence": {"freq": "weekly"}, "exceptions": []}
_t17_shift = _model_mod.normalize_note({
    "id": 36, "title": "Standup", "body": "series", "date": "2026-11-02", "recurrence": _t17_week,
    "moved": {"2026-11-04": "2026-11-05", "2026-11-03": "2026-11-04", "2026-11-02": "2026-11-03"},
    "overrides": {"2026-11-05": {"body": "WED"}, "2026-11-04": {"body": "TUE"}, "2026-11-03": {"body": "MON"}}})
_t17_shift["recurrence"] = dict(_t17_week, weekdays=[1, 2, 3])
_model_mod.drop_hidden_moves(_t17_shift)
_t17_stray = {"id": 37, "title": "Gym", "body": "x", "date": "2026-11-02", "recurrence": {"freq": "daily"},
              "exceptions": [], "moved": {"2026-11-09": "2026-11-10"},
              "overrides": {"2026-11-10": {"body": "MOVED"}, "2026-11-09": {"body": "STRAY"}}}
_model_mod.drop_hidden_moves(_t17_stray)
check("a week shifted a day at a time, the shift then made the rule, keeps every day's words where "
      "they showed, the moves gone; a date's own words stay (%s; %s)"
      % ({k: v["body"] for k, v in _t17_shift["overrides"].items()}, _t17_stray["overrides"]),
      {k: v["body"] for k, v in _t17_shift["overrides"].items()}
      == {"2026-11-03": "MON", "2026-11-04": "TUE", "2026-11-05": "WED"}
      and _t17_shift["moved"] == {}
      and {k: v["body"] for k, v in _t17_stray["overrides"].items()}
      == {"2026-11-10": "MOVED", "2026-11-09": "STRAY"}
      and _t17_stray["moved"] == {})
# ...a day moved onto a deleted date, its own date then no longer the rule's,
# is listed off the schedule: its words were shown and listed nowhere.
_t17_hidden = _model_mod.normalize_note({
    "id": 38, "title": "Meeting", "body": "x", "date": "2026-11-02",
    "recurrence": {"freq": "weekly", "end": "2026-12-20"}, "exceptions": ["2026-12-14"],
    "moved": {"2026-12-21": "2026-12-14"}, "overrides": {"2026-12-14": {"body": "Budget review"}}})
_t17_drawn = _model_mod.normalize_note(dict(_t17_hidden, recurrence={"freq": "weekly"}))
check("a day moved onto a deleted date, its own date no longer the rule's, is listed off the schedule; "
      "drawn there, it is not (%s, %s)" % (_rec_t10.off_schedule_days(_t17_hidden),
                                          _rec_t10.off_schedule_days(_t17_drawn)),
      _rec_t10.off_schedule_days(_t17_hidden) == ["2026-12-14"]
      and _rec_t10.off_schedule_days(_t17_drawn) == [])
# ...a weekly series turned back on as it was is the same series whether its
# start's weekday is lit or left to the start: read as another, its deleted
# days came back and its copy's days became "earlier text".
_t17_lit = {"freq": "weekly", "interval": 1, "weekdays": [0]}
_t17_off = _model_mod.normalize_note({
    "id": 39, "title": "Gym", "body": "x", "date": "2026-11-02", "recurrence": {"freq": ""},
    "exceptions": ["2026-11-16"], "overrides": {"2026-11-09": {"body": "Own"}},
    "_prev": dict(_t17_copy_day, date="2026-11-02", recurrence=_t17_lit, exceptions=["2026-11-16"], moved={},
                  overrides={"2026-11-09": {"body": "Own"}})})
check("a weekly series turned back on as it was is the same with its weekday lit or not",
      _model_mod.kept_days_fit(_t17_off, "2026-11-02", {"freq": "weekly"})
      and _model_mod._repeats_as(dict(_t17_off, recurrence={"freq": "weekly"}), _t17_off["_prev"])
      and not _model_mod.kept_days_fit(_t17_off, "2026-11-02", {"freq": "weekly", "weekdays": [1]})
      and _model_mod._same_series("2026-11-02", {"freq": "monthly"},
                                  "2026-11-02", {"freq": "monthly", "month_days": [2]})
      and not _model_mod._same_series("2026-11-02", {"freq": "monthly"},
                                      "2026-11-02", {"freq": "monthly", "month_days": [3]}))
# ...whatever month-day policy a weekly rule keeps hidden (saved from a
# monthly draft), which it never reads; a monthly one reads it.
check("a weekly rule is one series whatever 'Skip that month' it keeps hidden; a monthly one reads it",
      _model_mod._same_series("2026-11-02", {"freq": "weekly", "month_day_policy": "skip"},
                              "2026-11-02", {"freq": "weekly"})
      and not _model_mod._same_series("2026-01-31", {"freq": "monthly", "month_day_policy": "skip"},
                                      "2026-01-31", {"freq": "monthly"}))
# ...nor the weekdays, month days or policy a rule keeps that its frequency
# never reads: the phone's sheet stores all three.
check("a rule is one series whatever fields it keeps that its frequency never reads",
      _model_mod._same_series("2026-11-02", {"freq": "weekly", "month_days": [15]}, "2026-11-02", {"freq": "weekly"})
      and _model_mod._same_series("2026-11-02", {"freq": "daily", "weekdays": [0, 2]}, "2026-11-02", {"freq": "daily"})
      and _model_mod._same_series("2026-11-07", {"freq": "monthly", "month_day_policy": "skip"},
                                  "2026-11-07", {"freq": "monthly"})
      and not _model_mod._same_series("2026-11-02", {"freq": "weekly", "weekdays": [0, 2]},
                                      "2026-11-02", {"freq": "weekly"}))
# ...and an import reads the repeat by the days it gives: the start's weekday
# lit in the backup and not here is no change, and the Update spent the
# note's only earlier version for nothing.
_t19_here = _model_mod.normalize_note({"id": 49, "uid": "t19-lit", "title": "Gym", "body": "x",
                                       "date": "2026-11-02", "recurrence": {"freq": "weekly"}})
check("an import reads a repeat whose start weekday is lit, or left to the start, as unchanged",
      not _model_mod.shared_update_changes(
          _t19_here, dict(_t19_here, recurrence={"freq": "weekly", "weekdays": [0]}),
          _model_mod.UPDATABLE_FROM_BACKUP)
      and _model_mod.shared_update_changes(
          _t19_here, dict(_t19_here, recurrence={"freq": "weekly", "weekdays": [1]}),
          _model_mod.UPDATABLE_FROM_BACKUP))
# ...a day moved onto a date a dead move -- its own date no longer the rule's
# -- still points at takes it: two moves onto one date were read as the dead.
_t17_dead = _model_mod.normalize_note({"id": 40, "title": "Gym", "body": "x", "date": "2026-11-02",
                                       "recurrence": {"freq": "weekly"}, "moved": {"2026-11-18": "2026-11-20"}})
_rec_t10.move_day(_t17_dead, "2026-11-23", "2026-11-20")
check("a day moved onto a date a dead move points at takes it, the dead move gone (%s)" % _t17_dead["moved"],
      _t17_dead["moved"] == {"2026-11-23": "2026-11-20"})
# ...an Update's copy, as a restore leaves it, sets its days aside too when
# replaced; and a backup's Update counts the days it brings as held.
_t17_upd = _model_mod.normalize_note({
    "id": 41, "title": "Meeting", "body": "x", "date": "2026-11-04", "recurrence": {"freq": "daily"},
    "_prev": dict(_t17_copy_day, category="Work", date="2026-11-02", moved={},
                  overrides={"2026-11-22": {"body": "Room W2"}})})
_model_mod.copy_days_set_aside(_t17_upd)
_t17_back = _model_mod.normalize_note({
    "id": 42, "uid": "bk", "title": "Meeting", "body": "x", "date": "2026-11-04", "recurrence": {"freq": "daily"},
    "_prev": dict(_t17_copy_day, date="2026-11-02", moved={}, overrides={"2026-11-09": {"body": "ROOM 4B"}})})
_model_mod.apply_shared_update(_t17_back, {
    "uid": "bk", "title": "Meeting", "body": "x, from the laptop", "date": "2026-11-02",
    "recurrence": {"freq": "weekly"}, "overrides": {"2026-11-09": {"body": "ROOM 4B"}}},
    _model_mod.UPDATABLE_FROM_BACKUP)
check("an Update's copy sets its days with words aside when replaced; a backup's own days count as "
      "held (%s, %s)" % (_t10_aside(_t17_upd), _t10_aside(_t17_back)),
      _t10_aside(_t17_upd) == [("2026-11-22", "Room W2")] and _t10_aside(_t17_back) == [])


# History lists a day moved past a bounded series' end, and one
# moved onto a deleted date, and its search finds their words: in no row,
# they were found nowhere -- History is the one search of a day's own words.
_t18_bounded = _model_mod.normalize_note({
    "id": 43, "title": "Meeting", "body": "x", "date": "2026-11-02",
    "recurrence": {"freq": "weekly", "end": "2026-12-14"}, "moved": {"2026-12-14": "2026-12-18"},
    "overrides": {"2026-12-18": {"body": "Budget review"}}})
_t18_endless = _model_mod.normalize_note({
    "id": 44, "title": "Meeting", "body": "x", "date": "2026-11-02", "recurrence": {"freq": "weekly"},
    "exceptions": ["2026-12-14"], "moved": {"2026-12-21": "2026-12-14"},
    "overrides": {"2026-12-14": {"body": "Budget review"}}})


def _t18_found(note):
    return [c["date"] for row in _rec_t10.history_entries([note], "Budget") for c in row.get("children", [])]


# Two moves onto one date -- an older build's, or an Undo's beside a
# dead move -- are listed once: twice in History, and the phone's list threw.
_t19_two = {"id": 46, "title": "Meeting", "body": "x", "date": "2026-11-02",
            "recurrence": {"freq": "weekly", "interval": 2}, "exceptions": [], "overrides": {},
            "moved": {"2026-12-14": "2026-12-10", "2026-12-07": "2026-12-10"}}
# ...whichever the file lists first: the live move, or the dead one (the
# check once built only the order that passes by luck).
_t19_orders = [_t19_two, dict(_t19_two, moved={"2026-12-07": "2026-12-10", "2026-12-14": "2026-12-10"})]
# Which origin an unread twin is named by follows the file's order (a read
# keeps the live one, below; recorded as latent among the low findings): the
# date is listed once either way.
check("two moves onto one date are listed once, by the banner's count and in History (%s)"
      % [_rec_t10.drawn_moves(n) for n in _t19_orders],
      _rec_t10.drawn_moves(_t19_two) == [("2026-12-14", "2026-12-10")]
      and all([new for _orig, new in _rec_t10.drawn_moves(n)] == ["2026-12-10"]
              and [c["date"] for row in _rec_t10.history_entries([n]) for c in row.get("children", [])]
              == ["2026-12-10"] for n in _t19_orders))
# ...and a read keeps the one the calendar draws, whichever comes
# first by date: by date alone it kept the dead 7 December, and a meeting
# moved under the phone's 0.13.0 jumped back at the upgrade.
check("of two moves onto one date, a read keeps the one the calendar draws (%s)"
      % [_model_mod.normalize_note(copy_mod.deepcopy(n))["moved"] for n in _t19_orders],
      all(_model_mod.normalize_note(copy_mod.deepcopy(n))["moved"] == {"2026-12-14": "2026-12-10"}
          for n in _t19_orders))
# The owner's choice: a day the note deleted stays deleted, but the
# copy's words for it are set aside, not dropped: the phone's 0.13.0 showed
# such a day blank, its words in the copy alone, and the install erased them.
_t21_hidden = _model_mod.normalize_note({
    "id": 47, "title": "Gym", "body": "x", "date": "2026-11-02", "recurrence": {"freq": "weekly"},
    "exceptions": ["2026-11-09"],
    "_prev": {"title": "Gym", "body": "x", "comments": "", "formatting": [], "paragraphs": [],
              "date": "2026-11-02", "recurrence": {"freq": "weekly"}, "exceptions": [], "moved": {},
              "overrides": {"2026-11-09": {"body": "Hidden words"}}}})
check("a day the note deleted stays deleted, and the copy's words for it are set aside, not dropped (%s)"
      % _t10_aside(_t21_hidden),
      "2026-11-09" in _t21_hidden["exceptions"] and _t10_aside(_t21_hidden) == [("2026-11-09", "Hidden words")])
# ...and a backup's Update of that note keeps what its copy set aside as it
# was read: an Add kept it, an Update dropped it.
_t22_mine = _model_mod.normalize_note({"id": 48, "uid": "t22-gym", "title": "Gym", "body": "here",
                                       "date": "2026-11-02", "recurrence": {"freq": "weekly"}})
_t22_theirs = {"uid": "t22-gym", "title": "Gym", "body": "x", "date": "2026-11-02",
               "recurrence": {"freq": "weekly"}, "exceptions": ["2026-11-09"],
               "_prev": {"title": "Gym", "body": "x", "comments": "", "formatting": [], "paragraphs": [],
                         "date": "2026-11-02", "recurrence": {"freq": "weekly"}, "exceptions": [], "moved": {},
                         "overrides": {"2026-11-09": {"body": "Words from the backup"}}}}
_model_mod.apply_shared_update(_t22_mine, _t22_theirs, _model_mod.UPDATABLE_FROM_BACKUP)
check("a backup's Update keeps the earlier text its note's copy set aside as it was read (%s)"
      % _t10_aside(_t22_mine),
      _t10_aside(_t22_mine) == [("2026-11-09", "Words from the backup")])
# ...made once: a note already holding the same words on the same day is that
# note, and each later Update from the same device made it again.
_t22_book = [_t22_mine]
_t22_first = _model_mod.settle_set_aside(_t22_book)
_t22_mine["_set_aside"] = [{"day": "2026-11-09", "body": "Words from the backup"}]
_t22_again = _model_mod.settle_set_aside(_t22_book)
# ...its comments among its words: the same text with other comments is
# another note, or its comments arrived nowhere.
_t22_mine["_set_aside"] = [{"day": "2026-11-09", "body": "Words from the backup", "comments": "ask the physio"}]
_t22_commented = _model_mod.settle_set_aside(_t22_book)
check("an '(earlier text)' note already holding the same words on its day is not made again (%s, %s, %s, %d notes)"
      % (_t22_first, _t22_again, _t22_commented, len(_t22_book)),
      _t22_first == 1 and _t22_again == 0 and _t22_commented == 1 and len(_t22_book) == 3)
# ...and a copy holding the series as the note does, its weekday lit and the
# note's not, is spent: compared as stored, Restore previous stayed offered
# for nothing, and the next turn-off brought back an old agenda.
_t18_lit_copy = _model_mod.normalize_note({
    "id": 45, "title": "Gym", "body": "plan", "date": "2026-11-02", "recurrence": {"freq": "weekly"},
    "_prev": {"title": "Gym", "body": "plan", "comments": "", "formatting": [], "paragraphs": [],
              "date": "2026-11-02", "recurrence": {"freq": "weekly", "weekdays": [0]}}})
check("a copy holding the series as the note does, its weekday lit and the note's not, is spent, and "
      "a restore keeps nothing of it",
      _model_mod.rescue_copy_spent(_t18_lit_copy)
      and _model_mod.copy_replaced_by_restore(_t18_lit_copy, _t18_lit_copy["_prev"]) is None
      and not _model_mod.rescue_copy_spent(dict(_t18_lit_copy, recurrence={"freq": "weekly", "weekdays": [1]})))
check("History lists a day moved past a bounded series' end, or onto a deleted date, and finds its "
      "words (%s, %s)" % (_t18_found(_t18_bounded), _t18_found(_t18_endless)),
      _t18_found(_t18_bounded) == ["2026-12-18"] and _t18_found(_t18_endless) == ["2026-12-14"]
      and _rec_t10.history_entries([_t18_bounded])[0]["n_occurrences"] == 7)


# The fuzz of a series' days (the owner's choice): seven reviews in a row
# each found a road that lost or doubled a day's words. Random roads on one
# series -- a day edited, moved, deleted; the rule or start changed, the
# repeat off and on, Restore previous, a read, a share code's or a backup's
# Update -- and after every step every day's words the person did not delete
# or type over are somewhere (a day, the rescue copy, a note made of them),
# and none twice among the days and the notes made. The save, turn-off and
# restore are the window's (save_current_note, _turn_off_rescue_copy,
# restore_previous_version), the phone's fixture replays them the same way.
import random as _f17_random
import collections as _f17_coll

_F17_START = _dtT.date(2026, 11, 2)
_F17_DAYS = [(_F17_START + _dtT.timedelta(days=i)).isoformat() for i in range(42)]
_F17_RULES = [{"freq": "weekly"}, {"freq": "weekly", "weekdays": [0, 2]}, {"freq": "daily"},
              {"freq": "daily", "interval": 2}, {"freq": "weekly", "weekdays": [1, 3]}, {"freq": ""},
              {"freq": "weekly", "weekdays": [0, 1, 2]}, {"freq": "weekly", "weekdays": [1, 2, 3]}]


def _f17_where(note, made):
    """(the words of the note's days and of the notes made; every word a person
    can reach -- a day the calendar draws or lists off the schedule, any day of
    a note that no longer repeats (a repeat brings it back), the copy Restore
    previous brings, a note made of them). A word in the file alone, on a date
    nothing shows, is not kept (the fuzz counted it kept)."""
    overrides = note.get("overrides") or {}
    days = [p.get("body") for p in overrides.values() if p.get("body")]
    if _rec_t10.is_recurring(note):
        off = set(_rec_t10.off_schedule_days(note))
        seen = [p.get("body") for d, p in overrides.items() if p.get("body") and (
            d in off or _rec_t10.expand_occurrences(
                note, _rec_t10.parse_date(d), _rec_t10.parse_date(d)) == [d])]
    else:
        seen = list(days)
    held = seen + list(made)
    prev = note.get("_prev") or {}
    held += [p.get("body") for p in (prev.get("overrides") or {}).values() if p.get("body")]
    held += [e.get("body") for e in note.get("_set_aside") or []]
    return days + list(made), set(held)


def _f17_save(note, date, rule):
    """The window's series save of a new date and rule (the phone's fixture's save)."""
    rule = _rec_t10.normalize_recurrence(rule)
    days_lost = (_rec_t10.is_recurring(note) and not rule["freq"]
                 and _model_mod.days_hold_own_text(note))
    days_kept = _model_mod.days_hold_own_text(note)
    if not _model_mod.kept_days_fit(note, date, rule):
        note["exceptions"] = []
    if days_lost:
        existing = note.get("_prev")
        if not (_model_mod.update_copy(existing) and not _model_mod.rescue_copy_spent(note)):
            _model_mod.copy_days_set_aside(note)
            note["_prev"] = NO.NoteOrganizer._whole_note_rescue_copy(note)
        else:
            kept = copy_mod.deepcopy(existing)
            whole = NO.NoteOrganizer._whole_note_rescue_copy(note)
            for key in ("date", "recurrence") + _model_mod.DAY_FIELDS:
                kept.setdefault(key, whole.get(key))
            note["_prev"] = kept
    note["date"], note["recurrence"] = date, rule
    _model_mod.drop_hidden_moves(note)
    _model_mod.spend_series_days(note)
    if not rule["freq"] and not days_kept:
        note["exceptions"], note["overrides"], note["moved"] = [], {}, {}
    if _model_mod.rescue_copy_spent(note):
        note.pop("_prev", None)


def _f17_restore(note):
    """The window's restore_previous_version write."""
    prev = note["_prev"]
    replaced = _model_mod.copy_replaced_by_restore(note, prev)
    for key in ("title", "body", "comments", "formatting", "paragraphs"):
        note[key] = copy_mod.deepcopy(prev.get(key, note.get(key)))
    for key, _label in NO.NoteOrganizer._PREV_EXTRA_LABELS:
        if key in prev:
            note[key] = copy_mod.deepcopy(prev[key])
    _model_mod.drop_hidden_moves(note)
    if replaced is None:
        note.pop("_prev", None)
    else:
        note["_prev"] = replaced


# Whether the roads reach the placement of a copy's days on a series turned
# back on as it was (_copy_days_placed), and its setting aside of words for a
# day the note deleted: the fuzz once took neither, in 3,000 roads.
_f17_placed = {"calls": 0, "gone": 0}
_f17_placed_fn = _model_mod._copy_days_placed


def _f17_count_placed(note, prev, moved):
    _f17_placed["calls"] += 1
    overrides, aside = _f17_placed_fn(note, prev, moved)
    deleted = set(note.get("exceptions") or [])
    _f17_placed["gone"] += any(entry.get("day") in deleted for entry in aside)
    return overrides, aside


_model_mod._copy_days_placed = _f17_count_placed
_F17_ALL = ["edit", "edit", "move", "shift", "delete", "rule", "rule", "read", "share", "backup", "restore",
            "off", "back", "back", "older"]
# A third of the roads keep to the turn-off and the turn-on with the days
# edited and deleted between: the corner the reviews kept finding.
_F17_OFF_ON = ["edit", "edit", "delete", "delete", "off", "back", "back", "older", "rule", "read"]
_F17_ROADS = 1500
_f17_failures, _f17_steps, _f17_doubles = [], 0, 0
for _f17_seed in range(_F17_ROADS):
    _rng17 = _f17_random.Random(_f17_seed)
    _note = _model_mod.normalize_note({"id": 1, "uid": "f17", "title": "Gym", "body": "plan",
                                       "date": "2026-11-02", "recurrence": {"freq": "weekly"}})
    _made, _live, _n = [], _f17_coll.Counter(), 0
    _road = []
    for _step in range(14):
        _f17_steps += 1
        _drawn = sorted(set(_rec_t10.expand_occurrences(
            _note, _rec_t10.parse_date(_F17_DAYS[0]), _rec_t10.parse_date(_F17_DAYS[-1]))) & set(_F17_DAYS))
        # A copy is one slot: replaced, the words it alone held go with it --
        # the documented rule, not a loss -- unless it repeats as a series the
        # note does not: those are set aside (copy_days_set_aside).
        _copy_was = copy_mod.deepcopy(_note.get("_prev"))
        _slot_copy = isinstance(_copy_was, dict) and not (
            _rec_t10.is_recurring(_copy_was) and not _model_mod._repeats_as(_note, _copy_was))
        _days_was = set(_f17_where(_note, _made)[0]) | {e.get("body") for e in _note.get("_set_aside") or []}
        _only_copy = ({p.get("body") for p in (_copy_was.get("overrides") or {}).values()} - _days_was
                      if _slot_copy else set())
        # A day is edited, moved or deleted only while the note repeats.
        _repeats = _rec_t10.is_recurring(_note)
        _older_lost = set()
        _op = _rng17.choice(_F17_ALL if _f17_seed % 3 else _F17_OFF_ON)
        _road.append(_op)
        if _op == "shift" and _repeats and len(_drawn) >= 2:
            # A run of days each given words, each held a day later, the last
            # first -- the road a critical loss once took.
            _i = _rng17.randrange(len(_drawn) - 1)
            _run = _drawn[_i:_i + _rng17.randint(2, 4)]
            for _d in _run:
                _old = (_note.get("overrides") or {}).get(_d, {}).get("body")
                if _old in _live:
                    _live[_old] -= 1
                _n += 1
                _note.setdefault("overrides", {})[_d] = {"body": "w%d" % _n}
                _live["w%d" % _n] += 1
            for _d in reversed(_run):
                _t = (_rec_t10.parse_date(_d) + _dtT.timedelta(days=1)).isoformat()
                _now = set(_rec_t10.expand_occurrences(
                    _note, _rec_t10.parse_date(_F17_DAYS[0]), _rec_t10.parse_date(_F17_DAYS[-1])))
                if (_t in _F17_DAYS and _t not in _now and _t not in (_note.get("overrides") or {})
                        and _t not in (_note.get("moved") or {}).values()):
                    _rec_t10.move_day(_note, _d, _t)
        elif _op == "edit" and _repeats and _drawn:
            _d = _rng17.choice(_drawn)
            _old = (_note.get("overrides") or {}).get(_d, {}).get("body")
            if _old in _live:
                _live[_old] -= 1
            _n += 1
            _note.setdefault("overrides", {})[_d] = {"body": "w%d" % _n}
            _live["w%d" % _n] += 1
        elif _op == "move" and _repeats and _drawn:
            _d = _rng17.choice(_drawn)
            _free = [t for t in _F17_DAYS if t not in _drawn and t not in (_note.get("overrides") or {})
                     and t not in (_note.get("moved") or {}).values()]
            if _free:
                _rec_t10.move_day(_note, _d, _rng17.choice(_free))
        elif _op == "delete" and _repeats and _drawn:
            _d = _rng17.choice(_drawn)
            _origin = _rec_t10.moved_from(_note, _d) or _d
            _note["exceptions"] = sorted(set(_note.get("exceptions") or []) | {_origin})
            (_note.get("moved") or {}).pop(_origin, None)
            _gone = (_note.get("overrides") or {}).pop(_d, {}).get("body")
            if _gone in _live:
                _live[_gone] -= 1
        elif _op == "rule":
            _f17_save(_note, _rng17.choice(_F17_DAYS[:7]), copy_mod.deepcopy(_rng17.choice(_F17_RULES)))
        elif _op == "off" and _repeats:
            _f17_save(_note, _note.get("date"), {"freq": ""})
        elif _op == "older" and _repeats:
            # The turn-off and the turn-on as it was of 0.97.405 and the
            # phone's 0.13.0, the versions people upgrade from: the days left
            # in the copy alone, each shown blank -- one, looking empty,
            # perhaps deleted there -- then this build's
            # first read, at the install. What the copy they replaced held
            # alone was theirs to lose, not this build's.
            _older_lost = {p.get("body") for p in ((_copy_was or {}).get("overrides") or {}).values()} - _days_was
            _note["_prev"] = NO.NoteOrganizer._whole_note_rescue_copy(_note)
            _note["exceptions"], _note["overrides"], _note["moved"] = [], {}, {}
            _blank = sorted(set(_rec_t10.expand_occurrences(
                _note, _rec_t10.parse_date(_F17_DAYS[0]), _rec_t10.parse_date(_F17_DAYS[-1]))) & set(_F17_DAYS))
            if _blank and _rng17.random() < 0.5:
                _note["exceptions"] = [_rng17.choice(_blank)]
            _note = _model_mod.normalize_note(json.loads(json.dumps(_note)))
        elif (_op == "back" and isinstance(_note.get("_prev"), dict)
              and _rec_t10.is_recurring(_note["_prev"])):
            # The copy's repeat put back: as it was, or from another start.
            _f17_save(_note, _note["_prev"].get("date") if _rng17.random() < 0.6
                      else _rng17.choice(_F17_DAYS[:7]), copy_mod.deepcopy(_note["_prev"]["recurrence"]))
        elif _op == "read":
            _note = _model_mod.normalize_note(json.loads(json.dumps(_note)))
        elif _op in ("share", "backup"):
            _incoming = {"uid": "f17", "title": "Gym", "body": "plan, from the laptop %d" % _step,
                         "date": _rng17.choice(_F17_DAYS[:7]),
                         "recurrence": copy_mod.deepcopy(_rng17.choice(_F17_RULES))}
            if _op == "backup":
                _n += 1
                _incoming["overrides"] = {_rng17.choice(_F17_DAYS): {"body": "w%d" % _n}}
                _live["w%d" % _n] += 1
            _model_mod.apply_shared_update(_note, _incoming, _model_mod.UPDATABLE_FROM_BACKUP
                                           if _op == "backup" else _model_mod.UPDATABLE_FROM_SHARED)
        elif _op == "restore" and isinstance(_note.get("_prev"), dict):
            _f17_restore(_note)
        _box = [_note]
        _model_mod.settle_set_aside(_box)
        _made += [made.get("body") for made in _box[1:]]
        _shown, _held = _f17_where(_note, _made)
        # The slot rule excuses a copy REPLACED by another, never one spent --
        # the same copy, its days taken out -- whose days are owed to the
        # note, and were excused once (DR188). A new copy can match the old
        # in every field but its days: an Update over an Update's copy.
        _was, _now = _copy_was or {}, _note.get("_prev")
        _spent = {key: value for key, value in _was.items() if key not in _model_mod.DAY_FIELDS}
        # ...and never an Update's copy a turn-off replaced: kept whole is
        # the promise there, which the slot rule must not excuse.
        if (isinstance(_now, dict) and _now != _was and _now != _spent
                and not (_op in ("off", "rule") and _model_mod.update_copy(_copy_was))):
            for _word in _only_copy - _held:
                _live[_word] = 0
        for _word in _older_lost - _held:
            _live[_word] = 0
        _lost = sorted(w for w, k in _live.items() if k > 0 and w not in _held)
        # Words shown twice -- an '(earlier text)' note repeating words a day
        # shows, or a copy's day given back on its own date while the day
        # holds them where it was moved -- are the duplicates the owner chose
        # to leave (1 Nov): nothing lost, the extra deleted by hand. Counted,
        # not failed: the fuzz once held only for its own seeds, by luck.
        _f17_doubles += sum(1 for w, k in _f17_coll.Counter(_shown).items() if k > 1)
        if _lost:
            _f17_failures.append((_f17_seed, _road[:], _lost))
            break
    else:
        # ...and History, the one search of a day's own words, finds every
        # day the calendar draws or lists off the schedule.
        _off = set(_rec_t10.off_schedule_days(_note)) if _rec_t10.is_recurring(_note) else set()
        for _d, _p in (_note.get("overrides") or {}).items():
            if not (_p.get("body") and _rec_t10.is_recurring(_note) and (_d in _off or _rec_t10.expand_occurrences(
                    _note, _rec_t10.parse_date(_d), _rec_t10.parse_date(_d)) == [_d])):
                continue
            _found = [c["date"] for row in _rec_t10.history_entries([_note], _p["body"])
                      for c in row.get("children", [])]
            if _d not in _found:
                _f17_failures.append((_f17_seed, _road[:], "History misses %s %s" % (_d, _p["body"])))
                break
_model_mod._copy_days_placed = _f17_placed_fn
check("a fuzz of a series' days: %d roads, %d steps, no day's words lost, out of reach or missed by "
      "History but those the person deleted or typed over (%s; words shown twice, the duplicates left by "
      "the owner's choice: %d)" % (_F17_ROADS, _f17_steps, _f17_failures[:3], _f17_doubles),
      not _f17_failures)
check("...and its roads turn a series back on as its copy, and set aside a copy's words for a day the note "
      "deleted (%s)" % _f17_placed,
      _f17_placed["calls"] > 0 and _f17_placed["gone"] > 0)
# ...and a copy of another series asks for each day where the note holds it
# now: moved since by the note, or sent home -- by date alone, its words were
# set aside as earlier text the note still held.
_t16_copy_day = {"title": "Gym", "body": "x", "comments": "", "formatting": [], "paragraphs": [],
                 "recurrence": {"freq": "weekly"}, "exceptions": []}
_t16_moved_since = _model_mod.normalize_note({
    "id": 33, "title": "Gym", "body": "x", "date": "2026-10-26", "recurrence": {"freq": "weekly"},
    "moved": {"2026-11-09": "2026-11-11"}, "overrides": {"2026-11-11": {"body": "legs + towel"}},
    "_prev": dict(_t16_copy_day, date="2026-11-02", moved={},
                  overrides={"2026-11-09": {"body": "legs + towel"}})})
_t16_sent_home = _model_mod.normalize_note({
    "id": 34, "title": "Gym", "body": "x", "date": "2026-11-02", "recurrence": {"freq": "daily"},
    "overrides": {"2026-11-09": {"body": "legs + towel"}},
    "_prev": dict(_t16_copy_day, date="2026-11-02", moved={"2026-11-09": "2026-11-12"},
                  overrides={"2026-11-12": {"body": "legs + towel"}})})
for _t16_note in (_t16_moved_since, _t16_sent_home):
    _model_mod.copy_days_set_aside(_t16_note)
check("a copy's day the note moved since, or sent home, is held, not set aside as earlier text (%s, %s)"
      % (_t16_moved_since.get("_set_aside"), _t16_sent_home.get("_set_aside")),
      not _t16_moved_since.get("_set_aside") and not _t16_sent_home.get("_set_aside")
      and "overrides" not in _t16_moved_since["_prev"])


def _t10_side(rnd, tag, ops):
    """A series' days as either app's editor makes them, from none: a day
    given words, or only a colour (the desktop's shape or the phone's),
    deleted, reset, or moved to a date no day of it is drawn on."""
    note = dict({"title": "Gym", "body": "Warm up."}, **_kd_series,
                overrides={}, exceptions=[], moved={})
    pool = [(_dtT.date(2026, 11, 2) + _dtT.timedelta(days=i)).isoformat() for i in range(70)]
    for _k in range(rnd.randint(0, ops)):
        shown = _rec_t10.expand_occurrences(note, _dtT.date(2026, 11, 2), _dtT.date(2027, 1, 15))
        if not shown:
            break
        day, kind = rnd.choice(shown), rnd.choice(("text", "colour", "phone", "gone", "move", "reset"))
        orig = _rec_t10.moved_from(note, day) or day
        if kind == "text":
            note["overrides"][day] = {"title": "Gym", "body": "%s %s %d" % (tag, day, rnd.randint(0, 99))}
        elif kind == "colour":
            note["overrides"][day] = {"title": "Gym", "body": "Warm up.", "color": "#00aa00"}
        elif kind == "phone":
            note["overrides"][day] = {"color": "#3366ff"}
        elif kind == "gone":
            note["overrides"].pop(day, None)
            note["exceptions"].append(orig)
        elif kind == "reset":
            note["overrides"].pop(day, None)
            note["moved"].pop(orig, None)
        else:
            free = [d for d in pool if d not in shown]
            if free:
                _rec_t10.move_day(note, day, rnd.choice(free))
        note = _model_mod.normalize_note(note)
    return {key: note[key] for key in _model_mod.DAY_FIELDS}


def _t10_words(note, day):
    """Whether *note*'s edit of *day* holds words its series does not."""
    shown = _rec_t10.day_as_kept(note, day)
    return any((shown.get(key) or "") != (note.get(key) or "") for key in ("title", "body", "comments"))


def _t10_broken(mine, theirs):
    """Where the take-back breaks its rule for one shape: the note's words
    or look on a day changed, or a copy's day with words of its own neither
    shown on the day the result draws it nor set aside for that date, though
    the note did not delete that day."""
    out = _t10(copy_mod.deepcopy(mine), copy_mod.deepcopy(theirs))
    note = _model_mod.normalize_note(dict({"title": "Gym", "body": "Warm up."}, **_kd_series, **mine))
    kept = _model_mod.normalize_note(dict({"title": "Gym", "body": "Warm up."}, **_kd_series, **theirs))
    came = {to: day for day, to in kept["moved"].items()}
    bad = [] if _model_mod.normalize_note(json.loads(json.dumps(out))) == out else ["not idempotent"]
    aside = set(_t10_aside(out))
    for day, patch in note["overrides"].items():
        got = out["overrides"].get(day) or {}
        if _t10_words(note, day) and any(got.get(key) != patch.get(key) for key in ("title", "body")):
            bad.append("the note's words on %s" % day)
        if any(got.get(key) != value for key, value in patch.items() if key in ("color", "category")):
            bad.append("the note's look on %s" % day)
    for key, patch in kept["overrides"].items():
        when = _rec_t10.parse_date(key)
        if not _t10_words(kept, key) or key not in _rec_t10.expand_occurrences(kept, when, when):
            continue
        day = came.get(key, key)
        if day in note["exceptions"]:
            continue
        at = out["moved"].get(day, day)
        if _t10_shows(out, at) != patch["body"] and (at, patch["body"]) not in aside:
            bad.append("the copy's words for %s" % day)
    return bad


import random as _random_t10
_t10_rnd = _random_t10.Random(10)
_t10_bad = []
for _t10_i in range(300):
    _t10_shape = (_t10_side(_t10_rnd, "note", 6), _t10_side(_t10_rnd, "copy", 8))
    _t10_bad.extend((_t10_i, why) for why in _t10_broken(*_t10_shape))
check("on 300 shapes either app's editor makes, the take-back keeps every word the note wrote as it "
      "is, and every day's own text the copy held, on the day it is drawn or set aside for its date "
      "(%s)" % (_t10_bad[:3] or "all"),
      not _t10_bad)

# ...and the styles of words held in the copy's but not the same: a part of
# the copy's text made bold since was written over, no copy kept.
_rs_prev = {"title": "Trip", "body": "Packing list: boots, rope, map, torch.",
            "comments": "", "formatting": [], "paragraphs": []}
_rs_bold = _model_mod.normalize_note({
    "id": 10, "title": "Trip", "body": "Packing list:",
    "formatting": [{"start": 0, "end": 7, "style": "bold"}], "_prev": dict(_rs_prev)})
_rs_plain = _model_mod.normalize_note({
    "id": 11, "title": "Trip", "body": "Packing list:", "_prev": dict(_rs_prev)})
check("a restore over part of the copy's words made bold since keeps them as the copy in turn",
      _model_mod.copy_replaced_by_restore(_rs_bold, _rs_bold["_prev"]) is not None
      and _model_mod.copy_replaced_by_restore(_rs_plain, _rs_plain["_prev"]) is None)

# "↩ Restore previous" weighs all it writes over: comments typed since the
# copy, and the styles of the same words, went to no file.
_rp_prev = {"title": "Trip", "body": "Packing list: boots, rope, map, torch.",
            "comments": "ok", "formatting": [], "paragraphs": []}
_rp_note = _model_mod.normalize_note({
    "id": 6, "title": "Trip", "body": "Packing list:", "_prev": dict(_rp_prev),
    "comments": "ok. Call the hut warden on Friday about the late arrival."})
_rp_styled = _model_mod.normalize_note({
    "id": 7, "title": "Trip", "body": _rp_prev["body"], "comments": "ok",
    "formatting": [{"start": 0, "end": 7, "style": "bold"}], "_prev": dict(_rp_prev)})
_rp_plain = _model_mod.normalize_note({
    "id": 8, "title": "Trip", "body": "Packing list:", "comments": "ok", "_prev": dict(_rp_prev)})
_rp_kept = _model_mod.copy_replaced_by_restore(_rp_note, _rp_note["_prev"])
check("a restore keeps comments typed since the copy, and styles put on the same "
      "words, as the next copy; and nothing when nothing would be lost",
      _rp_kept is not None and "hut warden" in _rp_kept["comments"]
      and _model_mod.copy_replaced_by_restore(_rp_styled, _rp_styled["_prev"]) is not None
      and _model_mod.copy_replaced_by_restore(_rp_plain, _rp_plain["_prev"]) is None)

# The restore's own list of what it can put back must be exactly what an
# update can replace beyond the text -- a field added to one without the
# other is the drift this closes.
check("Restore previous can name every field an update replaces",
      {k for k, _ in NO.NoteOrganizer._PREV_EXTRA_LABELS}
      == set(_model_mod.UPDATABLE_FROM_BACKUP)
      - set(_model_mod.PREV_TEXT_FIELDS))

# ---- Two launches probing the same folder at once both see it writable ----
# The probe file had one fixed name, and overlapping probes collided --
# measured at nearly half answering "not writable". Threads reproduce it
# on both Windows (sharing violation) and Linux (the other probe already
# removed the file).
import threading as _threading
_wr_dir = tempfile.mkdtemp(prefix="nd_writable_")
_wr_false = []


def _wr_worker():
    for _ in range(300):
        if not _paths._is_writable(_wr_dir):
            _wr_false.append(1)


try:
    _wr_threads = [_threading.Thread(target=_wr_worker) for _ in range(4)]
    for _t in _wr_threads:
        _t.start()
    for _t in _wr_threads:
        _t.join()
    check("overlapping writability probes never answer 'not writable'",
          not _wr_false)
    check("...and leave no probe files behind",
          not [f for f in os.listdir(_wr_dir) if f.startswith(".write_test")])
finally:
    shutil.rmtree(_wr_dir, ignore_errors=True)

# ---- The stale-copy purge deletes only what it proved it copied ----
# It compared attachment NAMES at the top level only, then deleted the
# whole attachments tree: a file in a subfolder (never copied) or a
# different file sharing a name was destroyed, while the startup message
# said every attachment had been checked. And in the built app the folder
# above the app's own is scanned -- Downloads, the Desktop -- where a
# generic settings.json was adopted, then deleted.
_pg_real_legacy = _paths.get_legacy_dirs
_pg_root = tempfile.mkdtemp(prefix="nd_purge_")
try:
    _pg_app = os.path.join(_pg_root, "app")
    _pg_stale = os.path.join(_pg_root, "stale")
    for _d in (_pg_app, _pg_stale):
        os.makedirs(os.path.join(_d, "attachments"))
    _pg_notes = [{"id": 1, "title": "Same", "body": "x"}]
    for _d in (_pg_app, _pg_stale):
        with open(os.path.join(_d, "notes_data.json"), "w",
                  encoding="utf-8") as _f:
            json.dump(_pg_notes, _f)
    _paths.get_legacy_dirs = lambda app_dir: [_pg_stale]

    def _pg_write(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as _f:
            _f.write(text)

    # 1. A subfolder in the stale attachments: never copied, so the
    #    folder is not covered and nothing in it may go.
    _pg_write(os.path.join(_pg_stale, "attachments", "a.txt"), "same")
    _pg_write(os.path.join(_pg_app, "attachments", "a.txt"), "same")
    _pg_write(os.path.join(_pg_stale, "attachments", "2024 trip", "beach.jpg"),
              "only copy")
    _paths.purge_stale_copies(_pg_app)
    check("a subfolder's file the migration never copied survives the purge",
          os.path.isfile(os.path.join(_pg_stale, "attachments", "2024 trip",
                                      "beach.jpg")))
    check("...and so does the rest of that folder's notebook",
          os.path.isfile(os.path.join(_pg_stale, "notes_data.json")))

    # 2. Same name, different bytes: not covered either.
    shutil.rmtree(os.path.join(_pg_stale, "attachments", "2024 trip"))
    _pg_write(os.path.join(_pg_stale, "attachments", "a.txt"), "DIFFERENT")
    _paths.purge_stale_copies(_pg_app)
    check("a file that merely shares a name with ours is not deleted",
          os.path.isfile(os.path.join(_pg_stale, "attachments", "a.txt")))
    check("...and neither is the notebook beside it",
          os.path.isfile(os.path.join(_pg_stale, "notes_data.json")))

    # 3. Genuinely covered, but beside a settings.json that is not ours.
    _pg_write(os.path.join(_pg_stale, "attachments", "a.txt"), "same")
    with open(os.path.join(_pg_stale, "settings.json"), "w",
              encoding="utf-8") as _f:
        json.dump({"someOtherApp.fontSize": 14}, _f)
    _paths.purge_stale_copies(_pg_app)
    check("a covered folder is still cleaned up, file by file",
          not os.path.exists(os.path.join(_pg_stale, "notes_data.json"))
          and not os.path.exists(os.path.join(_pg_stale, "attachments")))
    check("...but another program's settings.json there is left alone",
          os.path.isfile(os.path.join(_pg_stale, "settings.json")))

    # 4. A backup beside a covered notebook is read too: one holding a note
    #    the app does not have stays. They went unread, with the notebook.
    with open(os.path.join(_pg_stale, "notes_data.json"), "w", encoding="utf-8") as _f:
        json.dump(_pg_notes, _f)
    _pg_unique = os.path.join(_pg_stale, "notes_data_backup_20261001_090000.json")
    _pg_same = os.path.join(_pg_stale, "notes_data_backup_20261002_090000.json")
    with open(_pg_unique, "w", encoding="utf-8") as _f:
        json.dump(_pg_notes + [{"id": 2, "title": "Only in a backup"}], _f)
    with open(_pg_same, "w", encoding="utf-8") as _f:
        json.dump(_pg_notes, _f)
    _paths.purge_stale_copies(_pg_app)
    check("a leftover backup holding a note the app lacks survives the purge",
          os.path.isfile(_pg_unique))
    check("...while a backup the app already holds whole is cleaned up",
          not os.path.exists(_pg_same)
          and not os.path.exists(os.path.join(_pg_stale, "notes_data.json")))
finally:
    _paths.get_legacy_dirs = _pg_real_legacy
    shutil.rmtree(_pg_root, ignore_errors=True)

# Adoption: the same "is this ours" question before a settings.json is
# copied in as this app's preferences.
_ad_real_legacy = _paths.get_legacy_dirs
_ad_real_appdata = _paths.get_appdata_dir
_ad_root = tempfile.mkdtemp(prefix="nd_adopt_settings_")
try:
    _ad_app = os.path.join(_ad_root, "app")
    _ad_old = os.path.join(_ad_root, "old")
    os.makedirs(_ad_app)
    os.makedirs(_ad_old)
    with open(os.path.join(_ad_old, "notes_data.json"), "w",
              encoding="utf-8") as _f:
        json.dump([{"id": 1, "title": "Old note"}], _f)
    with open(os.path.join(_ad_old, "settings.json"), "w",
              encoding="utf-8") as _f:
        json.dump({"someOtherApp.fontSize": 14}, _f)
    _paths.get_legacy_dirs = lambda app_dir: [_ad_old]
    _paths.get_appdata_dir = lambda: os.path.join(_ad_root, "no_appdata")
    _paths.run_migrations(_ad_app)
    check("an old notebook is still adopted...",
          os.path.isfile(os.path.join(_ad_app, "notes_data.json")))
    _ad_settings = os.path.join(_ad_app, "settings.json")
    _ad_took = False
    if os.path.isfile(_ad_settings):
        with open(_ad_settings, encoding="utf-8") as _f:
            _ad_took = "someOtherApp.fontSize" in json.load(_f)
    check("...without adopting another program's settings.json beside it",
          not _ad_took)
finally:
    _paths.get_legacy_dirs = _ad_real_legacy
    _paths.get_appdata_dir = _ad_real_appdata
    shutil.rmtree(_ad_root, ignore_errors=True)

# ...and this folder's own readable settings.json, met with no notes file,
# is copied aside before the old notebook's replaces it: it was replaced
# with no copy kept (the name, the theme, the categories, the Trash window).
_ks_root = tempfile.mkdtemp(prefix="nd_keep_settings_")
try:
    _ks_app = os.path.join(_ks_root, "app")
    _ks_old = os.path.join(_ks_root, "old")
    os.makedirs(_ks_app)
    os.makedirs(_ks_old)
    with open(os.path.join(_ks_old, "notes_data.json"), "w", encoding="utf-8") as _f:
        json.dump([{"id": 1, "title": "Old note"}], _f)
    with open(os.path.join(_ks_old, "settings.json"), "w", encoding="utf-8") as _f:
        json.dump({"app_version": "0.1.0", "theme": "dark"}, _f)
    with open(os.path.join(_ks_app, "settings.json"), "w", encoding="utf-8") as _f:
        json.dump({"theme": "light", "username": "Ana"}, _f)
    _paths.get_legacy_dirs = lambda app_dir: [_ks_old]
    _paths.get_appdata_dir = lambda: os.path.join(_ks_root, "no_appdata")
    _paths.run_migrations(_ks_app)
    _ks_kept = sorted(p for p in os.listdir(_ks_app) if p.startswith("settings_replaced_"))
    _ks_held = {}
    if _ks_kept:
        with open(os.path.join(_ks_app, _ks_kept[0]), encoding="utf-8") as _f:
            _ks_held = json.load(_f)
    with open(os.path.join(_ks_app, "settings.json"), encoding="utf-8") as _f:
        _ks_now = json.load(_f)
    check("an old notebook adopted keeps this folder's own readable settings aside first "
          "(%s, now %s)" % (_ks_kept, _ks_now),
          _ks_held.get("username") == "Ana" and _ks_now.get("theme") == "dark")
    # ...not again when they are already the old notebook's own bytes (a start
    # that went no further): each start left one more copy, of those.
    os.remove(os.path.join(_ks_app, "notes_data.json"))
    for _p in _ks_kept:
        os.remove(os.path.join(_ks_app, _p))
    _paths.run_migrations(_ks_app)
    _ks_again = [p for p in os.listdir(_ks_app) if p.startswith("settings_replaced_")]
    check("...and keeps no copy of settings that are already the old notebook's (%s)" % _ks_again,
          _ks_again == [] and os.path.isfile(os.path.join(_ks_app, "notes_data.json")))
    # ...and, that copy failing, the settings stay, and the old Trash stays where
    # it is, said: brought under this folder's window, it would be emptied by it.
    shutil.rmtree(_ks_app)
    os.makedirs(_ks_app)
    with open(os.path.join(_ks_app, "settings.json"), "w", encoding="utf-8") as _f:
        json.dump({"theme": "light", "username": "Ana"}, _f)
    with open(os.path.join(_ks_old, "trash.json"), "w", encoding="utf-8") as _f:
        json.dump([{"id": 9, "title": "Old trashed", "deleted_at": "2026-01-01 10:00:00"}], _f)
    with open(os.path.join(_ks_old, "templates.json"), "w", encoding="utf-8") as _f:
        json.dump([{"name": "Weekly", "title": "w"}], _f)
    _ks_backup_was = _paths._timestamped_backup
    _paths._timestamped_backup = lambda *a, **k: None
    try:
        _ks_msg = _paths.run_migrations(_ks_app) or ""
    finally:
        _paths._timestamped_backup = _ks_backup_was
    with open(os.path.join(_ks_app, "settings.json"), encoding="utf-8") as _f:
        _ks_stayed = json.load(_f)
    check("an old notebook whose settings could not be copied aside leaves this folder's, and "
          "its Trash where it is, said (%s)" % _ks_msg.replace("\n", " ")[-120:],
          _ks_stayed.get("username") == "Ana"
          and not os.path.exists(os.path.join(_ks_app, "trash.json"))
          and "trash.json" in _ks_msg
          and os.path.isfile(os.path.join(_ks_app, "notes_data.json")))
    check("...its templates, which no window empties, still come in",
          os.path.isfile(os.path.join(_ks_app, "templates.json"))
          and "templates.json" not in _ks_msg)
finally:
    _paths.get_legacy_dirs = _ad_real_legacy
    _paths.get_appdata_dir = _ad_real_appdata
    shutil.rmtree(_ks_root, ignore_errors=True)

# ---- The reclaim message says what happened ----
# "Moved your notebook back", when it was COPIED and the AppData copy
# stays -- and the entry file added that the two "can never drift apart".
_rc_real_appdata = _paths.get_appdata_dir
_rc_root = tempfile.mkdtemp(prefix="nd_reclaim_")
try:
    _rc_app = os.path.join(_rc_root, "app")
    _rc_appdata = os.path.join(_rc_root, "appdata")
    os.makedirs(_rc_app)
    os.makedirs(_rc_appdata)
    with open(os.path.join(_rc_appdata, "notes_data.json"), "w",
              encoding="utf-8") as _f:
        json.dump([{"id": 1, "title": "From the exe"}], _f)
    _paths.get_appdata_dir = lambda: _rc_appdata
    _rc_msg = _paths.run_migrations(_rc_app) or ""
    check("the reclaim says it COPIED the notebook, not moved it",
          _rc_msg.startswith("Copied") and "Moved" not in _rc_msg)
    check("...and that the installed app keeps its own copy",
          "will not appear" in _rc_msg
          and os.path.isfile(os.path.join(_rc_appdata, "notes_data.json")))
finally:
    _paths.get_appdata_dir = _rc_real_appdata
    shutil.rmtree(_rc_root, ignore_errors=True)

# ---- The startup readers take damage as damage too ----
# The same two kinds of damage as the loaders' (_DAMAGED), met before any
# loader runs. Every launch reads settings.json for the reclaim marker and
# sizes up each notebook a migration might adopt, and the purge reads both
# notebooks before it deletes anything. Each read raised past its except
# clause, and the app stopped before its window opened.
_su_real = (_paths.get_appdata_dir, _paths.get_legacy_dirs)
_su_root = tempfile.mkdtemp(prefix="nd_damaged_startup_")
try:
    _paths.get_appdata_dir = lambda: os.path.join(_su_root, "no_appdata")
    for _how, _bytes in _DAMAGED.items():
        _su_app = os.path.join(_su_root, _how, "app")
        _su_old = os.path.join(_su_root, _how, "old")
        os.makedirs(_su_app)
        os.makedirs(_su_old)
        _paths.get_legacy_dirs = lambda app_dir, _old=_su_old: [_old]
        _su_notes = os.path.join(_su_old, "notes_data.json")
        _su_set = os.path.join(_su_old, "settings.json")
        for _file in (_su_notes, _su_set, os.path.join(_su_app, "settings.json")):
            with open(_file, "wb") as _f:
                _f.write(_bytes)
        check("a %s notebook counts as holding no notes" % _how,
              _answer(lambda: _paths.count_notes_in(_su_notes)) == 0)
        check("...and is never taken for a copy of ours, so never deleted",
              _answer(lambda: _paths.is_redundant_copy(_su_notes, [])) is False)
        check("a %s settings.json is not taken for ours" % _how,
              _answer(lambda: _paths._looks_like_our_settings(_su_set)) is False)
        _answer(lambda: _paths._preserve_settings_if_unreadable(_su_set))
        check("...and is kept aside before a migration writes over it",
              any(_n.startswith("settings_corrupt_")
                  and open(os.path.join(_su_old, _n), "rb").read() == _bytes
                  for _n in os.listdir(_su_old)))
        # The launch itself: a damaged settings.json in the app folder, and
        # only a damaged notebook to adopt -- nothing to do, said quietly.
        _su_ran = _answer(lambda: _paths.run_migrations(_su_app))
        check("a launch beside a %s settings.json and notebook starts (%s)"
              % (_how, _su_ran),
              _su_ran is None)
        # The purge, both ways round: our notebook damaged, then theirs.
        with open(os.path.join(_su_app, "notes_data.json"), "wb") as _f:
            _f.write(_bytes)
        _su_purged = _answer(lambda: _paths.purge_stale_copies(_su_app))
        check("a purge beside a %s notebook of ours deletes nothing (%s)"
              % (_how, _su_purged),
              _su_purged == [] and os.path.isfile(_su_notes))
        with open(os.path.join(_su_app, "notes_data.json"), "w",
                  encoding="utf-8") as _f:
            json.dump([{"id": 1, "title": "Ours"}], _f)
        _su_purged = _answer(lambda: _paths.purge_stale_copies(_su_app))
        check("...nor beside a %s old one (%s)" % (_how, _su_purged),
              _su_purged == [] and os.path.isfile(_su_notes))
finally:
    _paths.get_appdata_dir, _paths.get_legacy_dirs = _su_real
    shutil.rmtree(_su_root, ignore_errors=True)

# ---- The qa scripts' own guard fails closed ----
# Nine identical copies of it read an unreadable notebook as EMPTY and
# overwrote it with [], and ran from any folder at all. One definition now
# (qa/_qa_support.hermetic_seed) refuses outside a declared scratch run,
# and beside any notebook it cannot prove is empty -- leaving it untouched.
# And it asks the app's own resolver which folder the app will open: the
# copy this file had looked beside itself while the app opened the folder
# notebook_location.txt names, the owner's notebook.
# Each fresh folder stands as a scratch copy's, the app's folder too; the
# repository's layout is walked by tools/check_guest.py (item 12).
# (_qa_support is imported at the top, for its guest step.)
_hs_root = tempfile.mkdtemp(prefix="nd_seed_")
_hs_cwd = os.getcwd()
_hs_marker = os.environ.get(_qa_support.SCRATCH_MARKER)
_hs_profile = os.environ.get("USERPROFILE")


def _hs_try(contents, marker, app_dir=None):
    """Run the guard in a fresh folder holding `contents` as its
    notes_data.json (None: no file), the app in `app_dir` (default: that
    folder). Returns (refused, the folder's notes file afterwards)."""
    folder = tempfile.mkdtemp(dir=_hs_root)
    path = os.path.join(folder, "notes_data.json")
    if contents is not None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(contents)
    if marker:
        os.environ[_qa_support.SCRATCH_MARKER] = "1"
    else:
        os.environ.pop(_qa_support.SCRATCH_MARKER, None)
    os.chdir(folder)
    try:
        _qa_support.hermetic_seed(app_dir or folder)
        refused = False
    except SystemExit:
        refused = True
    finally:
        os.chdir(_hs_cwd)
    after = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            after = fh.read()
    return refused, after


def _hs_notebook(where):
    """A stand-in for someone's notebook, never the owner's: its files, as bytes."""
    os.makedirs(where, exist_ok=True)
    for name, text in (("notes_data.json", '[{"id": 1, "title": "Her note"}]'),
                       ("trash.json", '[{"id": 2, "title": "Her deleted note"}]'),
                       ("settings.json", '{"theme": "dark"}')):
        with open(os.path.join(where, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    return _hs_bytes(where)


def _hs_bytes(where):
    return {name: open(os.path.join(where, name), "rb").read()
            for name in sorted(os.listdir(where))}


def _hs_located(line):
    """An app folder whose notebook_location.txt says `line`."""
    app = tempfile.mkdtemp(dir=_hs_root)
    with open(os.path.join(app, "notebook_location.txt"), "w", encoding="utf-8") as fh:
        fh.write("# my own notebook, out of the repo" + chr(10) + line + chr(10))
    return app


try:
    _ok_refused, _ok_after = _hs_try(None, marker=True)
    check("the qa seed runs in a declared scratch folder and seeds it",
          not _ok_refused and _ok_after == "[]")
    _nm_refused, _nm_after = _hs_try("[]", marker=False)
    check("...refuses to run where no scratch run was declared",
          _nm_refused and _nm_after == "[]")
    _bad = '[{"id": 1, "title": "half a notebook"'
    _bad_refused, _bad_after = _hs_try(_bad, marker=True)
    check("...refuses beside a notebook it cannot read, leaving it as it was",
          _bad_refused and _bad_after == _bad)
    _real = '[{"id": 1, "title": "Groceries"}]'
    _real_refused, _real_after = _hs_try(_real, marker=True)
    check("...and refuses beside a notebook holding notes, leaving it as it was",
          _real_refused and _real_after == _real)
    # The app's notebook_location.txt names her notebook: by its path, and
    # through %USERPROFILE%, which a guest's homes leave as they are.
    _hs_her = os.path.join(_hs_root, "her", "Note Organizer")
    _hs_before = _hs_notebook(_hs_her)
    _abs_refused, _abs_after = _hs_try(None, marker=True, app_dir=_hs_located(_hs_her))
    check("...refuses where the app's notebook_location.txt names a notebook by "
          "its path, writing nothing here or there",
          _abs_refused and _abs_after is None and _hs_bytes(_hs_her) == _hs_before)
    os.environ["USERPROFILE"] = os.path.join(_hs_root, "her")
    _hs_var = ("%USERPROFILE%" + os.sep if os.name == "nt" else "$USERPROFILE/")
    _var_refused, _var_after = _hs_try(
        None, marker=True, app_dir=_hs_located(_hs_var + "Note Organizer"))
    check("...and where it names one through %USERPROFILE%",
          _var_refused and _var_after is None and _hs_bytes(_hs_her) == _hs_before)
    # The app elsewhere, beside a notebook of its own, with no location file:
    # the guard saw an empty folder here, and the app opened that one.
    _hs_away = os.path.join(_hs_root, "checkout")
    _hs_away_before = _hs_notebook(_hs_away)
    _away_refused, _away_after = _hs_try(None, marker=True, app_dir=_hs_away)
    check("...and where the app it starts opens another folder than this one",
          _away_refused and _away_after is None
          and _hs_bytes(_hs_away) == _hs_away_before)
finally:
    if _hs_marker is None:
        os.environ.pop(_qa_support.SCRATCH_MARKER, None)
    else:
        os.environ[_qa_support.SCRATCH_MARKER] = _hs_marker
    if _hs_profile is None:
        os.environ.pop("USERPROFILE", None)
    else:
        os.environ["USERPROFILE"] = _hs_profile
    shutil.rmtree(_hs_root, ignore_errors=True)

# ======================================================================
# What the app writes, it reads back (2026-10-15). The import refused a
# backup over 500 MB or 10,000 files while the export wrote any size, so
# one long video made a backup that could not be restored; and the Share
# panel's Select all could tick more notes than one code may carry.
# ======================================================================
import zipfile as _zipfile
from noteorganizer.core import sharing as _sh


def _entry(name, size, packed):
    info = _zipfile.ZipInfo(name)
    info.file_size, info.compress_size = size, packed
    return info


_GB = 1_000_000_000
_backup = [_entry("notes_data.json", 2_000_000, 300_000)] + [
    _entry("attachments/p%d.jpg" % k, 3_000_000, 2_900_000) for k in range(250)]
check("a backup of 750 MB of photos imports when the disk has room for it",
      sum(i.file_size for i in _backup) > 500_000_000
      and _sh.backup_entries_problem(_backup) is None
      and _sh.backup_space_problem(_backup, 10 * _GB) is None)
check("...and so does one holding more than 10,000 attached files",
      _sh.backup_entries_problem(
          [_entry("attachments/f%d.txt" % k, 10, 10) for k in range(10_050)]) is None)
_no_room = _sh.backup_space_problem(_backup, 1 * _GB) or ""
check("a backup the disk has no room for is refused, saying what it needs -- "
      "on one disk the attachments count twice, unpacked and then copied",
      "free space" in _no_room and _sh.backup_space_problem(_backup, 2 * _GB) is None)
check("...and with the attachments on another disk, each disk is asked for its own share",
      _sh.backup_space_problem(_backup, 1 * _GB, 1 * _GB) is None
      and _sh.backup_space_problem(_backup, 1 * _GB, 500_000_000) is not None)
# Refused for no room, the backup is sound: its own kind, so the import says
# that alone, not "couldn't be read". A hostile archive stays a plain refusal.
_room_was = _sh._disk_of
_sh._disk_of = lambda _p: (1000, "one-disk")
try:
    _zroom = tempfile.mkdtemp(prefix="zip-room-")
    with _zipfile.ZipFile(os.path.join(_zroom, "r.zip"), "w") as _zf:
        _zf.writestr("notes_data.json", "[]")
    try:
        with _zipfile.ZipFile(os.path.join(_zroom, "r.zip")) as _zf:
            _sh._safe_extract_zip(_zf, os.path.join(_zroom, "out"))
        _room_answer = None
    except ValueError as _exc:
        _room_answer = _exc
finally:
    _sh._disk_of = _room_was
    shutil.rmtree(_zroom, ignore_errors=True)
check("a backup refused for no room is refused as a sound one with no room, its own kind",
      isinstance(_room_answer, _sh.BackupRefused) and "free space" in str(_room_answer))
check("an entry expanding a thousand times past its packed size is refused as a zip bomb",
      "hostile" in (_sh.backup_entries_problem(
          [_entry("attachments/x.bin", 3 * _GB, 3_000_000)]) or ""))
check("...but not a big file that packs like real content, nor a small one that packs well",
      _sh.backup_entries_problem([_entry("attachments/film.mp4", 3 * _GB, 2_900_000_000)]) is None
      and _sh.backup_entries_problem([_entry("attachments/log.txt", 40_000_000, 10_000)]) is None)
check("a bomb spread over many entries, each under the size one is asked about, is refused "
      "as a whole",
      "The backup would expand" in (_sh.backup_entries_problem(
          [_entry("attachments/b%d.bin" % k, 49_000_000, 49_000) for k in range(100)]) or ""))
check("...while a whole backup of text, which packs about ten times, imports",
      _sh.backup_entries_problem(
          [_entry("notes_data.json", 400_000_000, 40_000_000)]
          + [_entry("attachments/n%d.txt" % k, 1_000_000, 100_000) for k in range(200)]) is None)
_saved_files = _sh.MAX_BACKUP_FILES
try:
    _sh.MAX_BACKUP_FILES = 5
    _too_many = _sh.backup_entries_problem([_entry("attachments/f%d" % k, 1, 1) for k in range(6)])
finally:
    _sh.MAX_BACKUP_FILES = _saved_files
check("more files than the limit are still refused", "files" in (_too_many or ""))

_zroot = tempfile.mkdtemp(prefix="zip-limits-")
try:
    _zpath = os.path.join(_zroot, "b.zip")
    with _zipfile.ZipFile(_zpath, "w", _zipfile.ZIP_DEFLATED) as _zf:
        _zf.writestr("notes_data.json", "[]")
        _zf.writestr("attachments/a.txt", "hello")
    _out = os.path.join(_zroot, "out")
    with _zipfile.ZipFile(_zpath) as _zf:
        _sh._safe_extract_zip(_zf, _out, os.path.join(_zroot, "app", "attachments"))
    check("an ordinary backup still unpacks, its attachments' folder not made yet",
          os.path.isfile(os.path.join(_out, "attachments", "a.txt")))
    _bpath = os.path.join(_zroot, "bomb.zip")
    with _zipfile.ZipFile(_bpath, "w", _zipfile.ZIP_DEFLATED) as _zf:
        _zf.writestr("notes_data.json", "[]")
        _zf.writestr("attachments/zeros.bin", b"\0" * 3_000_000)
    _bomb_out = os.path.join(_zroot, "bomb_out")
    _saved_min = _sh.BOMB_MIN_BYTES
    try:
        _sh.BOMB_MIN_BYTES = 1_000_000
        try:
            with _zipfile.ZipFile(_bpath) as _zf:
                _sh._safe_extract_zip(_zf, _bomb_out)
            _bomb_answer = "extracted"
        except ValueError as _exc:
            _bomb_answer = str(_exc)
    finally:
        _sh.BOMB_MIN_BYTES = _saved_min
    check("a real archive shaped like a zip bomb is refused before anything is written",
          "hostile" in _bomb_answer and not os.path.exists(_bomb_out))
    _spath = os.path.join(_zroot, "slip.zip")
    with _zipfile.ZipFile(_spath, "w") as _zf:
        _zf.writestr("../escaped.txt", "x")
    try:
        with _zipfile.ZipFile(_spath) as _zf:
            _sh._safe_extract_zip(_zf, os.path.join(_zroot, "slip_out"))
        _slip = "extracted"
    except ValueError as _exc:
        _slip = str(_exc)
    check("a path that climbs out of the folder is still refused",
          "unsafe file paths" in _slip and not os.path.exists(os.path.join(_zroot, "escaped.txt")))
finally:
    shutil.rmtree(_zroot, ignore_errors=True)

# Closing the window stops a backup between two chunks (2026-10-15): the
# close waited 30 s for a long import, then the process died mid-file and
# left the unpacked backup, a half-copied attachment, an export's .tmp.
_sroot = tempfile.mkdtemp(prefix="zip-stop-")
try:
    _film = os.path.join(_sroot, "film.bin")
    with open(_film, "wb") as _fh:
        _fh.write(os.urandom(3_000_000))
    os.utime(_film, (1_600_000_000, 1_600_000_000))
    _plain = os.path.join(_sroot, "plain.zip")
    with _zipfile.ZipFile(_plain, "w", _zipfile.ZIP_DEFLATED) as _zf:
        _zf.write(_film, "attachments/film.bin")
    _through = os.path.join(_sroot, "through.zip")
    with open(_through, "wb") as _raw, _zipfile.ZipFile(
            _sh.StoppableFile(_raw, lambda: False), "w", _zipfile.ZIP_DEFLATED) as _zf:
        _zf.write(_film, "attachments/film.bin")
    with open(_plain, "rb") as _a, open(_through, "rb") as _b:
        check("a backup written through the stoppable file is the same, byte for byte",
              _a.read() == _b.read())

    def _stopped(work):
        try:
            work()
        except _sh.BackupStopped:
            return True
        return False

    _cut = os.path.join(_sroot, "cut.zip")

    def _write_cut():
        with open(_cut, "wb") as _raw, _zipfile.ZipFile(_sh.StoppableFile(
                _raw, lambda: os.path.getsize(_cut) > 100_000), "w",
                _zipfile.ZIP_DEFLATED) as _zf:
            _zf.write(_film, "attachments/film.bin")
    check("an export asked to stop stops in the middle of a file",
          _stopped(_write_cut) and os.path.getsize(_cut) < 2_000_000)
    _unpacked = os.path.join(_sroot, "out", "attachments", "film.bin")

    def _read_cut():
        with open(_plain, "rb") as _raw, _zipfile.ZipFile(_sh.StoppableFile(
                _raw, lambda: os.path.isfile(_unpacked)
                and os.path.getsize(_unpacked) > 0)) as _zf:
            _sh._safe_extract_zip(_zf, os.path.join(_sroot, "out"))
    check("...and so does an import's unpacking",
          _stopped(_read_cut) and 0 < os.path.getsize(_unpacked) < 3_000_000)
    _copy = os.path.join(_sroot, "copy.bin")
    _sh.copy_file_until_stopped(_film, _copy, lambda: False)
    with open(_film, "rb") as _a, open(_copy, "rb") as _b:
        check("an attachment copied a chunk at a time arrives whole, its date kept as copy2 keeps it",
              _a.read() == _b.read()
              and int(os.path.getmtime(_copy)) == 1_600_000_000)
    _half = os.path.join(_sroot, "half.bin")
    check("...and one asked to stop midway leaves nothing behind",
          _stopped(lambda: _sh.copy_file_until_stopped(
              _film, _half, lambda: os.path.isfile(_half) and os.path.getsize(_half) > 0))
          and not os.path.exists(_half))
finally:
    shutil.rmtree(_sroot, ignore_errors=True)


def _encode_answer(notes):
    try:
        return _sh.encode_share_code(notes)
    except _sh.ShareCodeTooLarge as _exc:
        return "refused: " + str(_exc)


_201 = [{"title": "n%d" % k, "body": "x"} for k in range(_sh.MAX_SHARED_NOTES + 1)]
check("no code is made for more notes than one code may carry, and the answer says what to do",
      "at most %d notes" % _sh.MAX_SHARED_NOTES in _encode_answer(_201)
      and "Backup" in _encode_answer(_201))
check("...while %d notes still make a code that imports back" % _sh.MAX_SHARED_NOTES,
      len(_sh.decode_share_code(_encode_answer(_201[:-1]))) == _sh.MAX_SHARED_NOTES)
import random as _random
_rng = _random.Random(5)
_letters = "".join(_rng.choice("abcdefghijklmnopqrstuvwxyz ") for _ in range(4000))
for _limit, _small in (("MAX_DECOMPRESSED_BYTES", 1000), ("MAX_SHARE_CODE_CHARS", 500)):
    _saved_limit = getattr(_sh, _limit)
    try:
        setattr(_sh, _limit, _small)
        _answer = _encode_answer([{"title": "big", "body": _letters}])
    finally:
        setattr(_sh, _limit, _saved_limit)
    check("no code is made past the import's %s either" % _limit,
          _answer.startswith("refused: ") and "too much for one code" in _answer)

# ---- A notes file another program holds at the start ----
# It read as unreadable, its copy failed for the same reason, and the first
# keystroke's autosave replaced fifty notes with one. Read again a moment
# later, and never written over while neither it nor a copy of it could be
# read.
_hw_dir = tempfile.mkdtemp(prefix="nd_held_")
_hw_prev = _paths.APP_DIR
try:
    _paths.configure(_hw_dir)
    with open(_paths.DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "title": "Important"}], f)
    _hw_real_open = open
    _hw_tries = {"n": 0}

    def _hw_flaky(path, *a, **k):
        if os.path.abspath(str(path)) == os.path.abspath(_paths.DATA_FILE) and _hw_tries["n"] < 1:
            _hw_tries["n"] += 1
            raise PermissionError(13, "held by another program")
        return _hw_real_open(path, *a, **k)

    _hw_sleep = _storage.time.sleep
    _storage.open = _hw_flaky
    _storage.time.sleep = lambda s: None
    try:
        _hw_notes, _hw_report = _storage.load_notes()
    finally:
        del _storage.open
        _storage.time.sleep = _hw_sleep
    check("a notes file held for a moment at the start is read on a later try",
          [n.get("title") for n in _hw_notes] == ["Important"]
          and not _hw_report.get("notes_file_corrupt"))
    # Held for good: here a folder stands where the file is, which neither
    # reads nor copies, on Windows and elsewhere alike.
    os.remove(_paths.DATA_FILE)
    os.makedirs(_paths.DATA_FILE)
    _storage.time.sleep = lambda s: None
    try:
        _hw_notes, _hw_report = _storage.load_notes()
    finally:
        _storage.time.sleep = _hw_sleep
    # The other program lets go: the notes are back as they were, and the
    # first save of this run must still leave them alone.
    os.rmdir(_paths.DATA_FILE)
    with open(_paths.DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "title": "Important"}], f)
    _hw_ok, _hw_exc = _storage.save_notes([{"id": 1, "title": "Shopping"}])
    with open(_paths.DATA_FILE, encoding="utf-8") as f:
        _hw_disk = [n.get("title") for n in json.load(f)]
    check(f"a notes file neither read nor copied is never written over this run "
          f"({_hw_ok}, {_hw_disk})",
          _hw_report.get("notes_file_corrupt") and _hw_report.get("corrupt_backup_path") is None
          and not _hw_ok and _hw_disk == ["Important"])
finally:
    _paths.WRITES_HELD.clear()
    _paths.configure(_hw_prev)
    shutil.rmtree(_hw_dir, ignore_errors=True)

# ---- The settings file held the same way ----
# Left out of the notes file's retries, a refused read took the place-holder
# for the file: the cleanup ran again, and save_setting wrote the place-holder
# and one key over the person's categories and theme.
_hs_prev = _paths.APP_DIR
_hs_real_open = open
_hs_sleep = _storage.time.sleep
_hs_real = {"categories": {"Work": "#123456"}, "theme": "dark_slate",
            "cleanup_done": False}


def _hs_refusing(times):
    left = {"n": times}

    def _open(path, *a, **k):
        if (os.path.abspath(str(path)) == os.path.abspath(_paths.SETTINGS_FILE)
                and left["n"] != 0):
            left["n"] -= 1
            raise PermissionError(13, "held by another program")
        return _hs_real_open(path, *a, **k)
    return _open


def _hs_disk():
    with _hs_real_open(_paths.SETTINGS_FILE, encoding="utf-8") as f:
        return json.load(f)


_hs_dirs = []
_hs_slept = []
try:
    _storage.time.sleep = _hs_slept.append
    for _hs_case in ("moment", "start", "later"):
        _hs_dirs.append(tempfile.mkdtemp(prefix="nd_heldset_"))
        _paths.configure(_hs_dirs[-1])
        with _hs_real_open(_paths.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_hs_real, f)
        with _hs_real_open(_paths.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "title": "a", "category": "Held-start client"},
                       {"id": 2, "title": ""}], f)
        if _hs_case == "later":
            _storage.load_settings()                       # read whole once
        _storage.open = _hs_refusing(1 if _hs_case == "moment" else -1)
        try:
            _hs_got = _storage.load_settings()
            _hs_held = _paths.writes_held(_paths.SETTINGS_FILE)
            # Every later read is one try: retried each time, a hold for the
            # run cost a second a read -- the start 19 s, a note click 4.
            _hs_waits = len(_hs_slept)
            _hs_later = [_storage.load_settings() for _ in range(5)]
            _hs_waits = len(_hs_slept) - _hs_waits
            _storage.save_setting("last_open_note_id", 7)
            _hs_saved = _hs_disk().get("last_open_note_id") == 7
            _hs_notes, _hs_report = (_storage.load_notes() if _hs_case == "start"
                                     else (None, {}))
        finally:
            del _storage.open
        _hs_aside = [p for p in os.listdir(_paths.APP_DIR) if p.startswith("settings_corrupt_")]
        if _hs_case == "moment":
            check("a settings file held for a moment at the start is read on a "
                  "later try (%s, held %s)" % (sorted(_hs_got), _hs_held),
                  _hs_got.get("theme") == "dark_slate" and not _hs_held and _hs_saved)
        elif _hs_case == "start":
            check("held for the whole start, it is not taken for damage: no copy "
                  "aside, never written over, and the cleanup waits (%s, %s, %s)"
                  % (_hs_aside, _hs_disk(), _hs_report.get("cleanup_report")),
                  _hs_got == {_storage.TRASH_WINDOW_UNKNOWN: True} and _hs_held
                  and not _hs_saved and not _hs_aside and _hs_disk() == _hs_real
                  and _hs_report.get("cleanup_report") is None
                  and len(_hs_notes) == 2)
            check("...its categories not said to have gone missing, the notes "
                  "keeping theirs (%s, %s)" % (_hs_report.get("categories_adopted"),
                                               _hs_notes[0].get("category")),
                  _hs_report.get("categories_adopted") == []
                  and _hs_notes[0].get("category") == "Held-start client")
            check("...and only the run's first read waits for it: five later reads "
                  "try once each (%d waits)" % _hs_waits,
                  _hs_waits == 0
                  and _hs_later == [{_storage.TRASH_WINDOW_UNKNOWN: True}] * 5)
        else:
            check("refused later on, the last good read stands in, and a setting "
                  "saved keeps every other (%s)" % _hs_disk(),
                  _hs_got.get("categories") == {"Work": "#123456"} and not _hs_held
                  and _hs_saved and not _hs_aside
                  and _hs_disk() == dict(_hs_real, last_open_note_id=7))
        _paths.WRITES_HELD.clear()
    # ...and a hold that ends later in the run changes nothing: the defaults
    # it said stand all run. Read once the hold ended, the real window purged
    # a Trash the start said it would keep whole.
    _hs_dirs.append(tempfile.mkdtemp(prefix="nd_heldset_"))
    _paths.configure(_hs_dirs[-1])
    with _hs_real_open(_paths.SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(_hs_real, trash_retention_days=7), f)
    _storage.open = _hs_refusing(-1)
    try:
        _storage.load_settings()
    finally:
        del _storage.open
    _hs_after = _storage.load_settings()
    _hs_window = _storage.trash_retention_days()
    _paths.WRITES_HELD.clear()
    check("a settings file held at the start keeps the run on its defaults once "
          "the hold ends (%s, window %s)" % (sorted(_hs_after), _hs_window),
          _hs_after == {_storage.TRASH_WINDOW_UNKNOWN: True} and _hs_window is None)
finally:
    _storage.time.sleep = _hs_sleep
    NO.CATEGORY_COLORS.pop("Held-start client", None)
    _paths.configure(_hs_prev)
    for _d in _hs_dirs:
        shutil.rmtree(_d, ignore_errors=True)

# ...and a notes file the system refuses at the start is held the same, never
# copied aside: a copy made the moment it let go took a good file aside, and
# the empty list's first save went over it.
_hn_dir = tempfile.mkdtemp(prefix="nd_heldnotes_")
_hn_prev = _paths.APP_DIR
try:
    _paths.configure(_hn_dir)
    with _hs_real_open(_paths.DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([{"id": 1, "title": "kept"}], f)

    def _hn_open(path, *a, **k):
        if os.path.abspath(str(path)) == os.path.abspath(_paths.DATA_FILE):
            raise PermissionError(13, "held by another program")
        return _hs_real_open(path, *a, **k)
    _storage.open = _hn_open
    _storage.time.sleep = lambda _s: None
    try:
        _hn_notes, _hn_report = _storage.load_notes(None)
    finally:
        del _storage.open
        _storage.time.sleep = _hs_sleep
    _hn_aside = [p for p in os.listdir(_hn_dir) if p.startswith("notes_data_corrupt_")]
    _hn_held = _paths.writes_held(_paths.DATA_FILE)
    with _hs_real_open(_paths.DATA_FILE, encoding="utf-8") as f:
        _hn_disk = json.load(f)
finally:
    _paths.WRITES_HELD.clear()
    _paths.configure(_hn_prev)
    shutil.rmtree(_hn_dir, ignore_errors=True)
check("a notes file held at the start is held, never copied aside (%s, held %s)" % (_hn_aside, _hn_held),
      _hn_aside == [] and _hn_held and _hn_report.get("notes_file_corrupt") is True
      and _hn_notes == [] and _hn_disk == [{"id": 1, "title": "kept"}])

# ...and so are the Trash and the templates (only the notes had a check, and
# a copy aside of a refused Trash file would have gone unnoticed).
for _hx_name, _hx_load in (("trash", _storage.load_trash),
                           ("templates", _storage.load_templates)):
    _hx_dir = tempfile.mkdtemp(prefix="nd_held_%s_" % _hx_name)
    _hx_prev = _paths.APP_DIR
    try:
        _paths.configure(_hx_dir)
        _hx_path = _paths.TRASH_FILE if _hx_name == "trash" else _paths.TEMPLATES_FILE
        with _hs_real_open(_hx_path, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "title": "kept"}], f)

        def _hx_open(path, *a, _p=_hx_path, **k):
            if os.path.abspath(str(path)) == os.path.abspath(_p):
                raise PermissionError(13, "held by another program")
            return _hs_real_open(path, *a, **k)
        _storage.open = _hx_open
        _storage.time.sleep = lambda _s: None
        try:
            _hx_got = _hx_load()
        finally:
            del _storage.open
            _storage.time.sleep = _hs_sleep
        _hx_aside = [p for p in os.listdir(_hx_dir) if "_corrupt_" in p]
        _hx_held = _paths.writes_held(_hx_path)
        with _hs_real_open(_hx_path, encoding="utf-8") as f:
            _hx_disk = json.load(f)
    finally:
        _paths.WRITES_HELD.clear()
        _paths.configure(_hx_prev)
        shutil.rmtree(_hx_dir, ignore_errors=True)
    check("a %s file refused at the start is held, never copied aside (%s, held %s)"
          % (_hx_name, _hx_aside, _hx_held),
          _hx_aside == [] and _hx_held and _hx_got == []
          and _hx_disk == [{"id": 1, "title": "kept"}])

# A run that did not read the Trash -- held, or set aside damaged -- deletes no
# attached file: a backup's copy of a trashed note shared its file, and Remove
# attachment on it took the file the trashed note still names.
_ak_dir = tempfile.mkdtemp(prefix="nd_trashfiles_")
_ak_prev = _paths.APP_DIR
_ak_said = {}
try:
    _paths.configure(_ak_dir)
    os.makedirs(_paths.ATTACHMENTS_DIR, exist_ok=True)
    _ak_file = os.path.join(_paths.ATTACHMENTS_DIR, "abc.png")
    _ak_gone = [{"attachments": [{"filename": "abc.png", "stored_as": "abc.png"}]}]
    for _ak_case in ("held", "damaged", "read"):
        with _hs_real_open(_ak_file, "w") as f:
            f.write("x")
        with _hs_real_open(_paths.TRASH_FILE, "w", encoding="utf-8") as f:
            f.write("{ not json" if _ak_case == "damaged"
                    else json.dumps([{"id": 1, "attachments": _ak_gone[0]["attachments"]}]))
        if _ak_case == "held":
            _paths.hold_writes(_paths.TRASH_FILE)
        else:
            _storage.load_trash()
        _ak_kept = _storage.attached_files_kept()
        _storage._delete_attachment_files(_ak_gone)
        _ak_said[_ak_case] = (_ak_kept, os.path.isfile(_ak_file))
        _paths.WRITES_HELD.clear()
finally:
    _paths.WRITES_HELD.clear()
    _storage._UNREAD_AT_LOAD.clear()
    _paths.configure(_ak_prev)
    shutil.rmtree(_ak_dir, ignore_errors=True)
check("a run whose Trash was held or set aside damaged keeps every attached file; one "
      "that read it does not (%s)" % _ak_said,
      _ak_said == {"held": (True, True), "damaged": (True, True), "read": (False, False)})

# The unknown window's mark kept the one-time cleanup waiting too: a window
# chosen, its "done" lost with the damaged file read as never, and the cleanup
# ran again on months of notes, merging look-alikes.
_cw_dir = tempfile.mkdtemp(prefix="nd_cleanupagain_")
_cw_prev = _paths.APP_DIR
try:
    _paths.configure(_cw_dir)
    with _hs_real_open(_paths.SETTINGS_FILE, "w", encoding="utf-8") as f:
        f.write("{ damaged")
    _storage.load_settings()
    _cw_mark = _storage.load_settings().get(_storage.TRASH_WINDOW_UNKNOWN)
    _storage.choose_trash_window(14)
    _cw_after = _storage.load_settings()
finally:
    _paths.WRITES_HELD.clear()
    _paths.configure(_cw_prev)
    shutil.rmtree(_cw_dir, ignore_errors=True)
check("a window chosen over settings that were lost marks the one-time cleanup done, "
      "not never (%s)" % _cw_after,
      _cw_mark is True and _cw_after.get("trash_retention_days") == 14
      and _cw_after.get("cleanup_done") is True
      and _storage.TRASH_WINDOW_UNKNOWN not in _cw_after)

# A change whose write was refused does not live on in the settings kept for a
# later refused read: the dict handed out was the one kept, and the next write
# that landed put the refused Trash length on disk.
_sc_dir = tempfile.mkdtemp(prefix="nd_settingscache_")
_sc_prev = _paths.APP_DIR
_sc_write = _storage._write_json_atomic
try:
    _paths.configure(_sc_dir)
    _storage.save_settings({"trash_retention_days": 30, "cleanup_done": True})
    _storage._write_json_atomic = lambda path, value: (False, OSError(28, "No space left"))
    _sc_refused = _storage.choose_trash_window(7)[0]
    _storage._write_json_atomic = _sc_write

    def _sc_open(path, *a, **k):
        if os.path.abspath(str(path)) == os.path.abspath(_paths.SETTINGS_FILE):
            raise PermissionError(13, "held for a moment")
        return _hs_real_open(path, *a, **k)
    _storage.open = _sc_open
    try:
        _sc_seen = _storage.load_settings().get("trash_retention_days")
    finally:
        del _storage.open
finally:
    _storage._write_json_atomic = _sc_write
    _paths.WRITES_HELD.clear()
    _paths.configure(_sc_prev)
    shutil.rmtree(_sc_dir, ignore_errors=True)
check("a refused settings change is not what a later refused read gives back "
      "(refused %s, then %s)" % (not _sc_refused, _sc_seen),
      _sc_refused is False and _sc_seen == 30)

# A number of more than 4,300 digits is a plain ValueError from the parser:
# the notes, Trash and templates files holding one stopped the start; read
# as damaged, they are copied aside, as settings.json was.
_bi_dir = tempfile.mkdtemp(prefix="nd_bigint_")
_bi_prev = _paths.APP_DIR
_bi_said = {}
try:
    _paths.configure(_bi_dir)
    for _bi_path in (_paths.DATA_FILE, _paths.TRASH_FILE, _paths.TEMPLATES_FILE):
        with _hs_real_open(_bi_path, "w", encoding="utf-8") as f:
            f.write('[{"id": %s, "title": "big"}]' % ("9" * 5000))
    for _bi_name, _bi_load in (("notes", lambda: _storage.load_notes(None)[0]),
                               ("trash", _storage.load_trash),
                               ("templates", _storage.load_templates)):
        try:
            _bi_said[_bi_name] = _bi_load()
        except Exception as _bi_exc:
            _bi_said[_bi_name] = "RAISED %s" % type(_bi_exc).__name__
    _bi_aside = sorted(p.split("_corrupt_")[0] for p in os.listdir(_bi_dir) if "_corrupt_" in p)
finally:
    _paths.WRITES_HELD.clear()
    _paths.configure(_bi_prev)
    shutil.rmtree(_bi_dir, ignore_errors=True)
check("a number of 5,000 digits reads as a damaged file, copied aside, never a "
      "stopped start (%s, aside %s)" % (_bi_said, _bi_aside),
      _bi_said == {"notes": [], "trash": [], "templates": []}
      and _bi_aside == ["notes_data", "templates", "trash"])

# A format span whose style is a list or an object is unhashable: the set test
# raised TypeError past every catch, and the app did not start at any launch.
_fz_odd = [{"start": 0, "end": 1, "style": ["bold"]}, {"start": 0, "end": 1, "style": {"b": 1}},
           {"start": 0, "end": 2, "style": "bold"}]
try:
    _fz_note = _normalize_note({"id": 1, "title": "x", "body": "ab", "formatting": _fz_odd})
    _fz_tpl = _storage.normalize_template({"name": "t", "body": "ab", "formatting": _fz_odd})
    _fz_said = (_fz_note.get("formatting"), _fz_tpl.get("formatting"))
except TypeError as _fz_exc:
    _fz_said = "RAISED %s" % _fz_exc
check("a format style that is a list or an object is dropped, the rest kept (%s)" % (_fz_said,),
      _fz_said == ([{"start": 0, "end": 2, "style": "bold"}],) * 2)

# A held file's refused write is reported once a run: a setting is written at
# every note opened, and its banner took the place of a delete's Undo.
_hr_dir = tempfile.mkdtemp(prefix="nd_heldrep_")
_hr_prev = _paths.APP_DIR
_hr_calls = []
_hr_cb = _storage.on_write_failure
try:
    _paths.configure(_hr_dir)
    _paths.hold_writes(_paths.SETTINGS_FILE)
    _storage.on_write_failure = lambda path, exc: _hr_calls.append(os.path.basename(path))
    _hr_results = [_storage.save_settings({"theme": "dark_slate"})[0] for _ in range(3)]
finally:
    _storage.on_write_failure = _hr_cb
    _paths.WRITES_HELD.clear()
    _paths.configure(_hr_prev)
    shutil.rmtree(_hr_dir, ignore_errors=True)
check("a held file's refused write is reported once a run, and refused every "
      "time (%s, %s)" % (_hr_calls, _hr_results),
      _hr_calls == ["settings.json"] and _hr_results == [False] * 3)

# ---- Every file renamed into place is on the disk first ----
# A power cut just after a rename can leave the new name pointing at bytes
# never written. One writer of six waited for them (_write_json_atomic): the
# backup export over the previous backup, the migrated notes file that marks
# a copy done and the import's attached files did not. Read in the source,
# so a seventh cannot be added without it: each
# os.replace has an fsync, or a call to the copier that has one, in the
# lines before it.
_fs_files = ["note_organizer.py"] + sorted(
    os.path.join(_root, _name)
    for _root, _dirs, _names in os.walk("noteorganizer") for _name in _names
    if _name.endswith(".py"))
_fs_bare = []
for _fs_file in _fs_files:
    with open(_fs_file, encoding="utf-8") as _f:
        _fs_lines = _f.read().split("\n")
    for _n, _line in enumerate(_fs_lines):
        if "os.replace(" in _line and not _line.lstrip().startswith("#"):
            _before = "\n".join(_fs_lines[max(0, _n - 25):_n])
            if "os.fsync(" not in _before and "copy_file_until_stopped(" not in _before:
                _fs_bare.append("%s:%d" % (_fs_file, _n + 1))
with open(os.path.join("noteorganizer", "core", "sharing.py"), encoding="utf-8") as _f:
    _fs_copier = _f.read().split("def copy_file_until_stopped", 1)[-1].split("\ndef ", 1)[0]
check("every file renamed into place is written to the disk first (%s)"
      % (_fs_bare or "all"),
      not _fs_bare and "os.fsync(" in _fs_copier)

# ---- No change says what it did over a notes write it never checked ----
# "Pinned to top", "Duplicated as" and "Moved" went on the status line over a
# refused write, in place of its "Not saved". Read in the source, so another
# cannot be added: a method that throws away save_notes' answer sets no status.
import ast as _sv_ast
_sv_methods = []
for _sv_file in ["note_organizer.py"] + sorted(
        os.path.join("noteorganizer", "ui", _n)
        for _n in os.listdir(os.path.join("noteorganizer", "ui")) if _n.endswith(".py")):
    with open(_sv_file, encoding="utf-8") as _f:
        _sv_tree = _sv_ast.parse(_f.read())
    _sv_methods += [(_sv_file, _fn) for _fn in _sv_ast.walk(_sv_tree)
                    if isinstance(_fn, _sv_ast.FunctionDef) and _fn.name != "save_notes"]


def _sv_calls(fn, name):
    """Whether *fn* calls self.<name>(...) anywhere in it."""
    return any(isinstance(_c, _sv_ast.Call) and isinstance(_c.func, _sv_ast.Attribute)
               and _c.func.attr == name and isinstance(_c.func.value, _sv_ast.Name)
               and _c.func.value.id == "self" for _c in _sv_ast.walk(fn))


# The throwers, then any method that calls one (a helper's write, one level
# up: _relocate_day's callers said "Moved to" over its refusal) and speaks.
_sv_throwers = {_fn.name for _file, _fn in _sv_methods if any(
    isinstance(_s, _sv_ast.Expr) and isinstance(_s.value, _sv_ast.Call)
    and isinstance(_s.value.func, _sv_ast.Attribute)
    and _s.value.func.attr == "save_notes" for _s in _sv_ast.walk(_fn))}
_sv_bare = ["%s:%s" % (_file, _fn.name) for _file, _fn in _sv_methods
            if _sv_calls(_fn, "set_status")
            and (_fn.name in _sv_throwers
                 or any(_sv_calls(_fn, _t) for _t in _sv_throwers))]
check("no method sets the status line after a notes write whose answer it, or "
      "a helper it calls, threw away (%s)" % (_sv_bare or "none"), not _sv_bare)

# ============================================================
# A FIELD THIS VERSION DOES NOT KNOW IS KEPT (the owner's D2, 2026-11-13)
# ============================================================
# A newer version, or another program, may write a field this one has never
# heard of; rebuilt field by field, every load dropped it, and an older app
# erased what a newer one added. Kept now, within bounds, by both apps alike.
import re
from noteorganizer.core import model as _d2
from noteorganizer.core import duplicates as _d2_dups
from noteorganizer.core import sharing as _d2_share

_d2_seen = _d2.normalize_note({'id': 1, 'title': 'x', 'mood': 'calm', 'weather': {'t': 3, 'sky': ['sun']},
                               '_mark': 1, 'deleted_at': '2026-11-01 10:00:00', 'tags': ['old']})
check(f"a field this version does not know is kept as it came ({ {k: _d2_seen.get(k) for k in ('mood', 'weather')} })",
      _d2_seen.get('mood') == 'calm' and _d2_seen.get('weather') == {'t': 3, 'sky': ['sun']})
check("...but not a name starting '_', the Trash's deleted_at, nor the removed tags",
      '_mark' not in _d2_seen and 'deleted_at' not in _d2_seen and 'tags' not in _d2_seen)
_d2_raw = {'id': 1, 'title': 'x', 'weather': {'t': 3}}
_d2_kept = _d2.normalize_note(_d2_raw)
_d2_raw['weather']['t'] = 99
check("...as a copy, not the dict it came in", _d2_kept.get('weather') == {'t': 3})
_d2_many = _d2.normalize_note(dict({'id': 1}, **{'f%02d' % i: i for i in range(40)}))
check(f"...at most {_d2.MAX_UNKNOWN_FIELDS}, the first by name",
      sorted(k for k in _d2_many if re.fullmatch(r'f\d\d', k))
      == ['f%02d' % i for i in range(_d2.MAX_UNKNOWN_FIELDS)])
_d2_big = _d2.normalize_note({'id': 1, 'big': 'x' * _d2.MAX_UNKNOWN_UNITS, 'small': 'y'})
check("...a field past the allowance left out, the rest kept",
      'big' not in _d2_big and _d2_big.get('small') == 'y')
# ...and a template's, by the owner's decision of 14 November: rebuilt from its known fields,
# a newer version's field was gone at the next template saved or imported.
_d2_tpl = NO.normalize_template({'name': 'Weekly', 'body': 'b', 'reminder_time': '09:00', '_mark': 1,
                                 'many': {'deep': [1, 2]}})
check(f"a template keeps a field this version does not know "
      f"({ {k: _d2_tpl.get(k) for k in ('reminder_time', 'many', '_mark')} })",
      _d2_tpl.get('reminder_time') == '09:00' and _d2_tpl.get('many') == {'deep': [1, 2]}
      and '_mark' not in _d2_tpl)
_d2_tpls = NO.normalize_template(dict({'name': 'T'}, **{'f%02d' % i: i for i in range(40)}))
check(f"...at most {_d2.MAX_UNKNOWN_FIELDS} of them, the first by name, as a note's",
      sorted(k for k in _d2_tpls if re.fullmatch(r'f\d\d', k))
      == ['f%02d' % i for i in range(_d2.MAX_UNKNOWN_FIELDS)])
_d2_tpl_file = os.path.abspath(NO.TEMPLATES_FILE)
_d2_tpl_had = os.path.exists(_d2_tpl_file)
_d2_tpl_was = NO.load_templates()
NO.save_templates([_d2_tpl])
check(f"...through a save and a load ({[t.get('reminder_time') for t in NO.load_templates()]})",
      [t.get('reminder_time') for t in NO.load_templates()] == ['09:00'])
if _d2_tpl_had:
    NO.save_templates(_d2_tpl_was)
else:
    os.remove(_d2_tpl_file)


def _d2_nest(depth):
    value = 'core'
    for _ in range(depth):
        value = [value]
    return value


# A thousand levels kept would break the copy that keeps them (a red here
# stays a red, not a crash before the footer).
try:
    _d2_deep = _d2.normalize_note({'id': 1, 'deep': _d2_nest(_d2.MAX_UNKNOWN_DEPTH),
                                   'deeper': _d2_nest(_d2.MAX_UNKNOWN_DEPTH + 1),
                                   'nan': float('nan'), 'thousand': _d2_nest(1000)})
except RecursionError:
    _d2_deep = {'thousand': 'broke the load'}
check("...nested to the depth allowed, and not one level past it, a NaN or a thousand levels",
      'deep' in _d2_deep and 'deeper' not in _d2_deep and 'nan' not in _d2_deep
      and 'thousand' not in _d2_deep)
# Through the file: load, save, read the bytes.
_d2_dir = tempfile.mkdtemp()
_d2_app_dir = NO_paths.APP_DIR
try:
    NO_paths.configure(_d2_dir)
    with open(NO_paths.SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'cleanup_done': True}, f)
    with open(NO_paths.DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump([{'id': 1, 'title': 'Kept', 'mood': 'calm'}], f)
    _d2_loaded, _ = _storage.load_notes()
    _storage.save_notes(_d2_loaded)
    with open(NO_paths.DATA_FILE, encoding='utf-8') as f:
        _d2_disk = json.load(f)
finally:
    NO_paths.configure(_d2_app_dir)
    shutil.rmtree(_d2_dir, ignore_errors=True)
check(f"...through a load and a save, in the file ({_d2_disk[0].get('mood')!r})",
      _d2_disk[0].get('mood') == 'calm')
# Two notes the same but for such a field are two notes, to every judge.
_d2_a = _d2.normalize_note({'id': 1, 'title': 'Same', 'body': 'b', 'mood': 'calm'})
_d2_b = _d2.normalize_note({'id': 2, 'title': 'Same', 'body': 'b', 'mood': 'storm'})
_d2_clean, _d2_stats = _d2.clean_notes([_d2_a, _d2_b])
check("...two notes differing only in such a field are not duplicates (signature, groups, cleanup)",
      _d2.content_signature(_d2_a) != _d2.content_signature(_d2_b)
      and _d2_dups._dup_key(_d2_a) != _d2_dups._dup_key(_d2_b)
      and not _d2_dups.find_duplicate_groups([_d2_a, _d2_b]) and len(_d2_clean) == 2)
# A share code stays a closed list: a stranger's code brings no field.
_d2_code_notes = _d2_share.decode_share_code(_d2_share.encode_share_code([dict(_d2_a, extra='x')]))
check("...a share code carries none", all('mood' not in n and 'extra' not in n for n in _d2_code_notes))
# A backup's Update brings its own beside this note's; a code's never does.
_d2_mine = _d2.normalize_note({'id': 1, 'title': 'Old', 'mood': 'calm', 'mine': 'kept'})
_d2.apply_shared_update(_d2_mine, {'title': 'New', 'mood': 'storm', 'theirs': 'x'},
                        _d2.UPDATABLE_FROM_BACKUP)
check(f"...a backup's Update brings its own, this note's kept ({ {k: _d2_mine.get(k) for k in ('mood', 'mine', 'theirs')} })",
      _d2_mine.get('title') == 'New' and _d2_mine.get('mood') == 'storm'
      and _d2_mine.get('mine') == 'kept' and _d2_mine.get('theirs') == 'x')
_d2_coded = _d2.normalize_note({'id': 1, 'title': 'Old', 'mood': 'calm'})
_d2.apply_shared_update(_d2_coded, {'title': 'New', 'mood': 'storm'}, _d2.UPDATABLE_FROM_SHARED)
check("...a share code's Update leaves this note's own as they are",
      _d2_coded.get('title') == 'New' and _d2_coded.get('mood') == 'calm')
check("...and such a field alone is no change for an Update to make",
      not _d2.shared_update_changes(_d2.normalize_note({'id': 1, 'title': 'T', 'mood': 'calm'}),
                                    {'title': 'T', 'mood': 'storm'}, _d2.UPDATABLE_FROM_BACKUP))
# ...the note's own kept in the rescue copy, through a load, so Restore
# previous can put back a value the Update wrote over (qa5 presses it).
_d2_over = _d2.normalize_note({'id': 1, 'title': 'Mine', 'reminder': '10:00', 'own': 1})
_d2.apply_shared_update(_d2_over, {'title': 'Older', 'reminder': '09:00'}, _d2.UPDATABLE_FROM_BACKUP)
_d2_reloaded = _d2.normalize_note(json.loads(json.dumps(_d2_over)))
check(f"...a backup's Update keeps this note's own in its rescue copy, through a load "
      f"({(_d2_reloaded.get('_prev') or {}).get('_unknown')})",
      _d2_over.get('reminder') == '09:00'
      and (_d2_reloaded.get('_prev') or {}).get('_unknown') == {'reminder': '10:00', 'own': 1})
_d2_full = _d2.normalize_note(dict({'id': 1, 'title': 'T'}, **{'m%02d' % i: i for i in range(30)}))
_d2.apply_shared_update(_d2_full, dict({'title': 'U'}, **{'z%02d' % i: i for i in range(7)}),
                        _d2.UPDATABLE_FROM_BACKUP)
# The note's own keys, not unknown_fields' reading of them, which bounds them as it reads.
check("...and the two sets together are held to the bounds at once, chosen by name",
      sorted(k for k in _d2_full if re.fullmatch(r'[mz]\d\d', k))
      == sorted(['m%02d' % i for i in range(30)] + ['z00', 'z01']))
check("...a note holding only such a field is not empty, so the first start's cleanup keeps it",
      not _d2.note_is_empty(_d2.normalize_note({'id': 1, 'mood': 'calm'})))
check("...true and 1 in such a field are two notes, as on the phone (1 and 1.0 one)",
      _d2.content_signature(_d2.normalize_note({'id': 1, 'flag': True}))
      != _d2.content_signature(_d2.normalize_note({'id': 1, 'flag': 1}))
      and _d2.content_signature(_d2.normalize_note({'id': 1, 'flag': 1}))
      == _d2.content_signature(_d2.normalize_note({'id': 1, 'flag': 1.0})))
check("...an empty object and an empty list in such a field are two notes too",
      _d2.content_signature(_d2.normalize_note({'id': 1, 'x': {}}))
      != _d2.content_signature(_d2.normalize_note({'id': 1, 'x': []})))
check("...and true is not the list [\"bool\", 1], nor an empty object the list [\"dict\"]",
      _d2.content_signature(_d2.normalize_note({'id': 1, 'x': True}))
      != _d2.content_signature(_d2.normalize_note({'id': 1, 'x': ['bool', 1]}))
      and _d2.content_signature(_d2.normalize_note({'id': 1, 'x': {}}))
      != _d2.content_signature(_d2.normalize_note({'id': 1, 'x': ['dict']})))
# The copy is spent only when the note holds its own fields again, kinds told
# apart: its 1 is not the backup's true, and the field the backup added (which
# no person can remove) does not keep it from being spent.
_d2_spend = _d2.normalize_note({'id': 1, 'title': 'Old', 'flag': 1})
_d2.apply_shared_update(_d2_spend, {'title': 'New', 'flag': True}, _d2.UPDATABLE_FROM_BACKUP)
_d2_spend['title'] = 'Old'
_d2_added = _d2.normalize_note({'id': 1, 'title': 'Old'})
_d2.apply_shared_update(_d2_added, {'title': 'New', 'extra': 'x'}, _d2.UPDATABLE_FROM_BACKUP)
_d2_added['title'] = 'Old'
check(f"...a copy whose own 1 the backup wrote over as true is not spent; one whose only new field "
      f"the backup added is ({_d2.rescue_copy_spent(_d2_spend)}, {_d2.rescue_copy_spent(_d2_added)})",
      not _d2.rescue_copy_spent(_d2_spend) and _d2.rescue_copy_spent(_d2_added))
# Restore previous puts back the copy's own alone: a field the backup added,
# or the backup's true over this note's 1, is what the restored version lacks,
# so it becomes the copy in its turn (an older backup, its words held in
# this note's). The same fields as the copy's leave nothing to keep.
def _d2_restore_turn(own, theirs):
    note = _d2.normalize_note(dict({'id': 1, 'title': 'T', 'body': 'Hello world'}, **own))
    _d2.apply_shared_update(note, dict({'title': 'T', 'body': 'Hello'}, **theirs),
                            _d2.UPDATABLE_FROM_BACKUP)
    return _d2.copy_replaced_by_restore(note, note['_prev'])
_d2_turns = (_d2_restore_turn({}, {'x_new': 'v'}), _d2_restore_turn({'own': 1}, {'own': True}),
             _d2_restore_turn({'own': 1}, {'own': 1}))
check(f"...Restore previous keeps in its turn the field the backup added and the true it wrote "
      f"over a 1; with the copy's own alone it keeps nothing "
      f"({[t if t is None else t.get('_unknown') for t in _d2_turns]})",
      _d2_turns[0] is not None and _d2_turns[0].get('_unknown') == {'x_new': 'v'}
      and _d2_turns[1] is not None and _d2_turns[1].get('_unknown') == {'own': True}
      and _d2_turns[2] is None)
check("...and a list longer than the allowance is left out unwalked",
      'huge' not in _d2.normalize_note({'id': 1, 'huge': [0] * (_d2.MAX_UNKNOWN_UNITS + 1)}))
# Out of the Trash: kept, the Trash's own stamp left there.
_d2_entry = dict(_d2.normalize_note({'id': 7, 'title': 'Binned', 'mood': 'calm'}),
                 deleted_at='2026-11-01 10:00:00')
_d2_notes, _d2_trash, _d2_back = _storage.restore_many_from_trash([], [_d2_entry], [_d2_entry])
check("...and a note back from the Trash keeps it, without the Trash's deleted_at",
      _d2_back and _d2_back[0].get('mood') == 'calm' and 'deleted_at' not in _d2_back[0])

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
