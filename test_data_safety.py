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
#
# It fails CLOSED. It used to let an unreadable notes_data.json through
# as if it were no notebook at all -- and an unreadable notebook is the
# one the app itself could still have rescued. And it runs only where a
# throwaway folder has been declared (NOTEORG_SCRATCH=1, set by
# tools/run_tests.py and by CI), the rule the qa scripts follow too
# (qa/_qa_support.hermetic_seed).
def _guard_real_notes():
    if os.environ.get("NOTEORG_SCRATCH") != "1":
        sys.exit(
            "REFUSING to run: this test deletes and rewrites notes_data.json "
            "beside it, and nothing says this folder is a throwaway copy. "
            "Run it through tools/run_tests.py, or set NOTEORG_SCRATCH=1 "
            "yourself in a scratch folder outside the project -- see "
            "CLAUDE.md, 'QA testing safety'.")
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "notes_data.json")
    if not os.path.exists(here):
        return
    try:
        with open(here, encoding="utf-8") as f:
            notes = json.load(f)
    except (IOError, OSError, ValueError) as exc:
        sys.exit(
            "REFUSING to run: the notes_data.json beside this test cannot "
            "be read (%s). It may be a real notebook the app could still "
            "rescue; this test would delete it." % exc)
    if not isinstance(notes, list) or notes:
        held = ("%d notes" % len(notes) if isinstance(notes, list)
                else "something other than an empty notebook")
        sys.exit(
            "REFUSING to run: the notes_data.json beside this test holds "
            "%s.\nThis test deletes and rewrites that file. Run it "
            "only from a throwaway copy\noutside the project tree -- see "
            "CLAUDE.md, 'QA testing safety'." % held)


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
check('no line of the welcome note leaves its bold open, and no icon '
      'carries the variation selector',
      all(line.count('**') % 2 == 0 for line in _WELCOME_LINES)
      and '\ufe0f' not in _welcome['title'] + _welcome['body'])

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
check('the on_* names give the words for that fill, other names the colour',
      all(_pvalue(pal, 'on_' + role) == _letters(pal[role])
          for pal in NO.THEMES.values()
          for role in ('accent', 'danger', 'success'))
      and _pvalue(NO.THEMES['dark'], 'card') == NO.THEMES['dark']['card'])
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
            (_paths.SETTINGS_FILE, _storage.load_settings, {}, "settings_corrupt_"),
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

_MAIN_GUARD_DRIVER = '"""Drive the REAL _main() with the heavy parts stubbed to recorders.\n\nWritten and launched by test_data_safety to prove the single-instance\nguard is WIRED, not merely implemented: _main must consult acquire() and\nhonour the answer. The adversarial review caught the gap this closes --\ndeleting the whole guard from _main left every suite green, because the\nlock primitive was tested end-to-end while the one call site a user ever\ntravels through was tested by nobody.\n"""\nimport json\nimport os\nimport sys\n\nHERE = os.path.dirname(os.path.abspath(__file__))\nos.chdir(HERE)\nsys.path.insert(0, HERE)\n\n# Hermetic seed BEFORE the note_organizer import: the module resolves its\n# data directory and runs migrations at import time, and an unseeded dir\n# invites the adoption of the machine\'s real notebook.\nif not os.path.exists("notes_data.json"):\n    with open("notes_data.json", "w", encoding="utf-8") as f:\n        f.write("[]")\ntry:\n    with open("settings.json", "r", encoding="utf-8") as f:\n        _settings = json.load(f)\nexcept Exception:\n    _settings = {}\nif not isinstance(_settings, dict):\n    _settings = {}\n_settings.setdefault("reclaimed_from_appdata", True)\nwith open("settings.json", "w", encoding="utf-8") as f:\n    json.dump(_settings, f)\n\nimport tkinter.messagebox as mb  # noqa: E402\n\nimport note_organizer as NO  # noqa: E402\nfrom noteorganizer.core import paths  # noqa: E402\n\nevents = []\nfolders = {}\n\n\ndef _recording_initialise(app_dir=None, resolved=None):\n    paths.configure(HERE)\n    events.append("init")\n    folders["opened"] = resolved[0] if resolved else None\n\n\nNO.initialise = _recording_initialise\n_real_acquire = NO.single_instance.acquire\n\n\ndef _recording_acquire(path=None):\n    events.append("acquire")\n    folders["locked"] = os.path.dirname(path) if path else None\n    return _real_acquire(path)\n\n\nNO.single_instance.acquire = _recording_acquire\n\n\nclass FakeApp:\n    def __init__(self):\n        events.append("app")\n\n    def protocol(self, *a, **k):\n        pass\n\n    def on_app_close(self):\n        pass\n\n    def mainloop(self):\n        events.append("loop")\n\n\nclass FakeRoot:\n    def withdraw(self):\n        pass\n\n    def destroy(self):\n        pass\n\n\nNO.NoteOrganizer = FakeApp\nNO.tk.Tk = FakeRoot\nmb.showinfo = lambda *a, **k: events.append("refused-dialog")\n\nNO._main()\nprint("EVENTS:" + json.dumps(events))\nprint("FOLDERS:" + json.dumps(folders))\n'

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
          _rt_report.get("categories_adopted") == ["Clients 2026"])
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
      and _junk_p.get("pinned") is True
      and len(_junk_p.get("checklist") or []) == _model_mod.MAX_CHECKLIST_ITEMS
      and _junk_p.get("exceptions") == ["2026-01-02"])

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
_here = os.path.dirname(os.path.abspath(__file__))
for _support_dir in (_here, os.path.join(_here, "qa")):
    if os.path.isfile(os.path.join(_support_dir, "_qa_support.py")):
        sys.path.insert(0, _support_dir)
        break
import _qa_support  # noqa: E402
_hs_root = tempfile.mkdtemp(prefix="nd_seed_")
_hs_cwd = os.getcwd()
_hs_marker = os.environ.get(_qa_support.SCRATCH_MARKER)


def _hs_try(contents, marker):
    """Run the guard in a fresh folder holding `contents` as its
    notes_data.json (None: no file). Returns (refused, file afterwards)."""
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
        _qa_support.hermetic_seed()
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
finally:
    if _hs_marker is None:
        os.environ.pop(_qa_support.SCRATCH_MARKER, None)
    else:
        os.environ[_qa_support.SCRATCH_MARKER] = _hs_marker
    shutil.rmtree(_hs_root, ignore_errors=True)

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
