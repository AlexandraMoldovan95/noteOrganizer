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

NO.save_settings(original_settings)  # restore whatever was really there

# ---- run_migrations(): Case 1 backup-verification fix ----
# The bug this closes: if backing up the local file before overwriting it
# with the AppData copy failed, the overwrite used to proceed anyway. Now
# it should refuse and leave the local file untouched instead.
real_get_appdata_dir = NO.get_appdata_dir
app_dir = tempfile.mkdtemp()
appdata_dir = tempfile.mkdtemp()
try:
    NO.get_appdata_dir = lambda: appdata_dir

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
    NO.get_appdata_dir = real_get_appdata_dir
    shutil.rmtree(app_dir, ignore_errors=True)
    shutil.rmtree(appdata_dir, ignore_errors=True)

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
