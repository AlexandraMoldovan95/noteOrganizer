# HERMETIC SEED -- BEFORE the note_organizer import below: the module
# resolves its data directory and runs the data MIGRATIONS at import
# time, so by the first line of test code the adoption has already
# happened. The data directory must be this test's alone. An
# empty directory invites run_migrations to adopt whatever real notebook
# %APPDATA% holds, and real notes then leak into every scenario: the
# checks start flaking whenever the OWNER's data changes. Seeding an
# empty notebook plus the reclaim marker closes both migration doors
# before the app is even constructed. The refusal is the same last-line
# defence test_data_safety carries: run from a folder holding real
# notes, the script stops instead of seeding over them.
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

import sys
import note_organizer as NO, tkinter as tk, time
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

def safe(name, fn):
    try:
        fn()
        check(name, True)
    except Exception as e:
        check(f'{name} ({type(e).__name__}: {e})', False)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.geometry('1100x850'); app.update()

# ---- THEME SWITCHING ----
def theme_stress():
    for _ in range(15):
        app.toggle_theme()
        app.update()
safe('theme toggle stress (15x, no freeze)', theme_stress)

# theme correctness: note card picks up new colors
app.set_theme('dark'); app.update()  # known starting point after the toggle stress above
app.notes.append({'id':1,'title':'ThemeNote','body':'x','category':'General',
                  'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
                  'checklist':[],'attachments':[]})
app.refresh_note_list(); app.update()
def find_card_bg(w):
    for c in w.winfo_children():
        try:
            if c.cget('cursor')=='hand2' and isinstance(c, tk.Frame): return c.cget('bg')
        except: pass
        r=find_card_bg(c)
        if r: return r
before = find_card_bg(app.list_frame)
app.set_theme('light'); app.update()
after = find_card_bg(app.list_frame)
check('note card color updates on theme switch', before != after and after==app.colors['card'])

app.set_theme('dark'); app.update()

# ---- POPUP STRESS: rapid open/dismiss ----
NO.CATEGORY_COLORS.setdefault('PopupTestCat', '#7c5cff')
def popup_stress():
    app.show_settings_page(); app.update()
    app.toggle_settings_panel('categories'); app.update()
    for _ in range(5):
        app._show_color_palette(app, '#111111', lambda c: None)
        app.update()
        app._dismiss_mini_popup()
        app.update()
safe('rapid popup open/dismiss (5x, no freeze)', popup_stress)

# ---- SETTINGS PANEL STRESS: rapid toggling ----
def panel_stress():
    app.show_settings_page(); app.update()
    for _ in range(3):
        for p in ['categories','trash','duplicates','templates']:
            app.toggle_settings_panel(p)
            app.update()
safe('rapid settings panel toggling (no freeze)', panel_stress)

# ---- MEMORY LEAK CHECK: themed_widgets should stay flat ----
app.notes = [{'id':i,'title':f'N{i}','body':'x','category':'General',
             'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
             'checklist':[],'attachments':[]} for i in range(100)]
app.refresh_note_list(); app.render_calendar(); app.update()
before_widgets = len(app.themed_widgets)
for _ in range(10):
    app.refresh_note_list()
    app.render_calendar()
    app.update()
after_widgets = len(app.themed_widgets)
check(f'themed_widgets stays flat over 10 refreshes ({before_widgets} -> {after_widgets})',
      after_widgets==before_widgets)

# attachments list leak check
app.load_note(app.notes[0])
before_att = len(app.themed_widgets)
for _ in range(10):
    app.current_attachments = [{'filename':f'f{i}.txt','stored_as':'x'} for i in range(3)]
    app.refresh_attachments_list()
    app.update()
after_att = len(app.themed_widgets)
check(f'attachments list themed_widgets stays flat ({before_att} -> {after_att})',
      after_att==before_att)

# share panel leak check
before_share = len(app.themed_widgets)
for _ in range(10):
    app.toggle_share_panel()
    app.toggle_share_panel()
after_share = len(app.themed_widgets)
check(f'share panel themed_widgets stays flat ({before_share} -> {after_share})',
      after_share==before_share)

# ---- PIN + DUPLICATE UNDER STRESS ----
def pin_dup():
    n = app.notes[0]
    app.toggle_pin(n)
    app.duplicate_note(n)
    app.toggle_pin(n)
safe('pin + duplicate note', pin_dup)

# ---- ATTACHMENTS: copies of a note get their OWN files (audit Z01-F04) ----
# duplicate_note AND the Settings "clean up duplicates" merge both used to
# point the copy/survivor at the SAME file on disk as the source. Deleting
# one note then deleted the file out from under the other — for cleanup,
# the auto-purge of the trashed twin is guaranteed to destroy the very file
# the merge exists to preserve. Each copy must own its files.
import os as _os4
from noteorganizer.core import paths as _paths4
from noteorganizer.core import storage as _storage4
_os4.makedirs(_paths4.ATTACHMENTS_DIR, exist_ok=True)

def _mk_att4(name, text="payload"):
    p = _os4.path.join(_paths4.ATTACHMENTS_DIR, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p

# -- duplicate_note (the wiring seam no test covered) --
_dup_src = "20260101000000000001_dup.txt"
_dup_src_path = _mk_att4(_dup_src)
app.notes = [{'id': 1, 'title': 'Owns file', 'body': 'x', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': [{'filename': 'dup.txt', 'stored_as': _dup_src}]}]
app.save_notes()
_clone4 = app.duplicate_note(app.notes[0])
app.update()
_clone_name4 = (_clone4.get('attachments') or [{}])[0].get('stored_as')
check('duplicate_note: the copy gets a DIFFERENT attachment filename',
      bool(_clone_name4) and _clone_name4 != _dup_src)
check('duplicate_note: the copy has its own file on disk',
      bool(_clone_name4)
      and _os4.path.isfile(_os4.path.join(_paths4.ATTACHMENTS_DIR, _clone_name4)))
_storage4._delete_attachment_files([_clone4])
check('duplicate_note: deleting the copy leaves the original file intact',
      _os4.path.isfile(_dup_src_path))

# -- Settings "clean up duplicates" merge (GAP found by the Fix-1 reviewer) --
_merge_src = "20260101000000000002_merge.txt"
_merge_src_path = _mk_att4(_merge_src)
_kept4 = {'id': 10, 'title': 'Dup', 'body': 'same', 'category': 'General',
          'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
          'checklist': [], 'attachments': []}
_removed4 = {'id': 11, 'title': 'Dup', 'body': 'same', 'category': 'General',
             'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
             'checklist': [], 'attachments': [{'filename': 'merge.txt', 'stored_as': _merge_src}]}
app.notes = [_kept4, _removed4]
app.trash = []
_group4 = [_kept4, _removed4]
class _V4:
    def __init__(self, v): self._v = v
    def get(self): return self._v
_orig_ask4 = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
try:
    app._cleanup_selected_duplicates(
        [(_V4(False), _kept4, _group4), (_V4(True), _removed4, _group4)],
        None, refresh=lambda: None, announce=False)
finally:
    app.ask_yes_no = _orig_ask4
app.update()
_merged4 = [a.get('stored_as') for a in _kept4.get('attachments', [])]
check('cleanup-duplicates: survivor gets the merged file under its OWN name',
      len(_merged4) == 1 and _merged4[0] != _merge_src
      and _os4.path.isfile(_os4.path.join(_paths4.ATTACHMENTS_DIR, _merged4[0])))
# The trashed twin still points at the original file; its later purge must
# not delete the survivor's copy.
_storage4._delete_attachment_files([_removed4])
check('cleanup-duplicates: purging the trashed twin leaves the survivor file intact',
      len(_merged4) == 1
      and _os4.path.isfile(_os4.path.join(_paths4.ATTACHMENTS_DIR, _merged4[0])))

# ---- PERFORMANCE: note list with larger count ----
app.notes = [{'id':i,'title':f'Perf{i}','body':'x'*30,'category':'General',
             'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
             'checklist':[],'attachments':[]} for i in range(300)]
t0=time.perf_counter()
app.refresh_note_list()
app.update()
elapsed=(time.perf_counter()-t0)*1000
check(f'refresh_note_list with 300 notes completes ({elapsed:.0f}ms, informational)', True)

print()
print(f"=== QA4 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
