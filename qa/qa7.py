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
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile, base64, zlib, struct
fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app = NO.NoteOrganizer(); app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.ask_yes_no = lambda *a, **k: True
app.geometry('1100x850'); app.update()

def find_widget(w, cls, text_contains=None):
    for c in w.winfo_children():
        if isinstance(c, cls):
            if text_contains is None or text_contains in str(c.cget('text')):
                return c
        r = find_widget(c, cls, text_contains)
        if r:
            return r
    return None

def find_all_labels(w, acc=None):
    if acc is None: acc = []
    for c in w.winfo_children():
        if isinstance(c, tk.Label):
            acc.append(str(c.cget('text')))
        find_all_labels(c, acc)
    return acc

os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)

# ============================================================
# 1. ATTACHMENT CLEANUP ON PERMANENT DELETE (the other 3 paths)
# ============================================================

# 1a. delete_forever (single trash entry)
fname_a = '20260101000000000001_a.txt'
path_a = os.path.join(NO.ATTACHMENTS_DIR, fname_a)
with open(path_a, 'w') as f: f.write('x')
entry_a = {'id': 901, 'title': 'DelForever', 'attachments': [{'filename': 'a.txt', 'stored_as': fname_a}],
           'deleted_at': '2026-01-01 00:00:00'}
app.trash = [entry_a]
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
del_btn = find_widget(app.settings_trash_panel, tk.Button, 'Delete')
del_btn.invoke()
app.update()
check('delete_forever removes the attachment file from disk', not os.path.isfile(path_a))
check('delete_forever removes the trash entry', len(app.trash) == 0)

# 1b. empty_trash (all entries)
fnames_b = []
for i in range(3):
    fn = f'2026010100000000000{i}_b{i}.txt'
    with open(os.path.join(NO.ATTACHMENTS_DIR, fn), 'w') as f: f.write('x')
    fnames_b.append(fn)
app.trash = [{'id': 910 + i, 'title': f'N{i}', 'attachments': [{'filename': f'b{i}.txt', 'stored_as': fn}],
              'deleted_at': '2026-01-01 00:00:00'} for i, fn in enumerate(fnames_b)]
app.hide_settings_page(); app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
empty_btn = find_widget(app.settings_trash_panel, tk.Button, 'Empty trash')
empty_btn.invoke()
app.update()
check('empty_trash removes ALL attachment files',
      all(not os.path.isfile(os.path.join(NO.ATTACHMENTS_DIR, fn)) for fn in fnames_b))
check('empty_trash clears the trash list', len(app.trash) == 0)

# 1c. purge_expired_trash (automatic, on load)
fname_c = '20260101000000000099_old.txt'
path_c = os.path.join(NO.ATTACHMENTS_DIR, fname_c)
with open(path_c, 'w') as f: f.write('x')
old_entry = {'id': 920, 'title': 'VeryOld', 'attachments': [{'filename': 'old.txt', 'stored_as': fname_c}],
             'deleted_at': '2020-01-01 00:00:00'}
kept, purged_count = NO.purge_expired_trash([old_entry])
check('purge_expired_trash removes the attachment file', not os.path.isfile(path_c))
check('purge_expired_trash reports 1 purged', purged_count == 1 and len(kept) == 0)

app.hide_settings_page(); app.update()

# ============================================================
# 2. DELETE NOTE FROM CALENDAR
# ============================================================
app.notes = [{'id': 1, 'title': 'CalDelete', 'body': 'x', 'category': 'General', 'date': '2026-07-15',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}]
app.save_notes()
app.notebook.select(app.TAB_CALENDAR); app.update()
app.cal_year, app.cal_month = 2026, 7
app.render_calendar()
app.open_day_popup('2026-07-15')
app.update()

del_icon = find_widget(app.day_panel, tk.Button, '🗑')
check('calendar day-list delete icon exists', del_icon is not None)
del_icon.invoke()
app.update()
check('calendar day-list delete removes the note', len(app.notes) == 0)

# detail view + Cancel doesn't bounce
app.notes = [{'id': 2, 'title': 'CalDetailDelete', 'body': 'x', 'category': 'General', 'date': '2026-07-15',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}]
app.save_notes()
app.render_calendar()
app.open_day_popup('2026-07-15')
app.update()
app.show_day_note(app.notes[0], '2026-07-15')
app.update()
del_btn_detail = find_widget(app.day_panel, tk.Button, '🗑 Delete')
check('calendar detail-view delete button exists', del_btn_detail is not None)

app.ask_yes_no = lambda *a, **k: False  # Cancel
del_btn_detail.invoke()
app.update()
check('Cancel on calendar delete leaves the note intact', len(app.notes) == 1)
check('Cancel does NOT bounce back to the day list', app._day_panel_mode == 'note')

app.ask_yes_no = lambda *a, **k: True  # Confirm
del_btn_detail2 = find_widget(app.day_panel, tk.Button, '🗑 Delete')
del_btn_detail2.invoke()
app.update()
check('Confirm on calendar delete removes the note', len(app.notes) == 0)
check('panel falls back to list after a real delete', app._day_panel_mode == 'list')

# recurring note asks for scope
app.notes = [{'id': 3, 'title': 'RecurringCal', 'body': 'x', 'category': 'General', 'date': '2026-07-01',
              'recurrence': {'freq': 'daily'}, 'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}}]
app.save_notes()
app.render_calendar()
app.open_day_popup('2026-07-08')
app.update()
scope_asked = {'called': False}
app.ask_occurrence_scope = lambda *a, **k: (scope_asked.__setitem__('called', True), 'occurrence')[1]
app.ask_yes_no = lambda *a, **k: True
del_icon2 = find_widget(app.day_panel, tk.Button, '🗑')
del_icon2.invoke()
app.update()
check('recurring note delete via calendar asks for scope', scope_asked['called'])
check('only that occurrence removed, series intact', '2026-07-08' in app.notes[0].get('exceptions', []))

app.close_day_panel(); app.update()
# Un-shadow the real scope prompt: leaving this section's always-'occurrence'
# mock in place once leaked it into every later section (a save/restore
# further down dutifully "restored" this mock, believing it was the real
# method). Deleting the instance attribute brings the class method back.
del app.ask_occurrence_scope

# ---- CALENDAR PREVIEW IS A QUICK LOOK: text + chips, not the editor ----
# A note with a table drew raw pipe soup in the day preview, and its
# comments were dumped inline. The preview now shows plain text only and,
# like the note-list cards, just SAYS what else the note carries.
from noteorganizer.core import tables as _core_tables_q7
app.notes = [{'id': 9, 'title': 'PreviewNote', 'category': 'General',
              'date': '2026-07-20', 'updated': '2026-01-01 00:00',
              'created': '2026-01-01 00:00', 'attachments': [],
              'body': 'Text sus\n| A | B |\n| --- | --- |\n| 1 | 2 |\nText jos',
              'comments': 'comentariu care nu trebuie afisat',
              'checklist': [{'text': 'a', 'done': True},
                            {'text': 'b', 'done': False}]}]
app.save_notes()
app.render_calendar()
app.open_day_popup('2026-07-20')
app.update()
app.show_day_note(app.notes[0], '2026-07-20')
app.update()
_pv_texts = []
def _walk_q7(w):
    _pv_texts.append(w)
    for c in w.winfo_children():
        _walk_q7(c)
_walk_q7(app.day_panel)
_pv_text = next((w.get('1.0', 'end-1c') for w in _pv_texts
                 if isinstance(w, tk.Text)), '')
_pv_chip = next((w.cget('text') for w in _pv_texts
                 if isinstance(w, tk.Label)
                 and ('▦' in str(w.cget('text')) or '💬' in str(w.cget('text')))),
                '')
check('calendar preview strips the table to plain text',
      '|' not in _pv_text and 'Text sus' in _pv_text and 'Text jos' in _pv_text)
check('calendar preview does not dump the comments inline',
      'comentariu care nu trebuie' not in _pv_text)
check('calendar preview flags table + checklist + comments as chips',
      '▦' in _pv_chip and '1/2' in _pv_chip and '💬' in _pv_chip)
app.close_day_panel(); app.update()

# ============================================================
# 3. MULTI-SELECT BULK ACTIONS
# ============================================================
NO.CATEGORY_COLORS.setdefault('Work', '#7c5cff')
app.notes = [
    {'id': 10, 'title': 'A', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': [{'filename': 'x.png', 'stored_as': 'x.png'}]},
    {'id': 11, 'title': 'B', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
with open(os.path.join(NO.ATTACHMENTS_DIR, 'x.png'), 'w') as f: f.write('x')
app.save_notes()
app.notebook.select(app.TAB_NOTES); app.update()
app.refresh_note_list(); app.update()

check('selection mode starts off', app.selection_mode is False)
app._toggle_selection_mode()
app.update()
check('selection mode toggles on', app.selection_mode is True)
check('bulk action bar becomes visible', app.bulk_action_bar.winfo_ismapped())

# Regression: the bulk-action bar's 4 widgets used to overflow the fixed
# 280px-wide sidebar, cramping the "Category" button. Rather than assert an
# absolute pixel width (which depends on which font is actually available —
# "Segoe UI" isn't installed on the Linux CI runner, so Tk silently
# substitutes a fallback with different, wider metrics there than on a real
# Windows machine), compare the real fixed bar against a reconstruction of
# the original pre-fix sizing, built with whatever font actually resolves
# on THIS machine. That keeps the check meaningful across environments: it
# verifies the fix made things narrower, not that it hits a Windows-specific
# pixel number.
app.bulk_action_bar.update_idletasks()
fixed_width = app.bulk_action_bar.winfo_reqwidth()

_old_bar = tk.Frame(app)
tk.Label(_old_bar, text="0 selected", font=("Segoe UI", 8, "bold")
          ).pack(side="left", padx=(0, 8))
tk.Button(_old_bar, text="Select all", font=("Segoe UI", 8)
          ).pack(side="left", padx=(0, 4), ipadx=4, ipady=2)
tk.Button(_old_bar, text="\U0001F5D1 Trash", font=("Segoe UI", 8, "bold")
          ).pack(side="left", padx=(0, 4), ipadx=4, ipady=2)
tk.Button(_old_bar, text="\U0001F5C2 Category ▾", font=("Segoe UI", 8)
          ).pack(side="left", padx=(0, 4), ipadx=4, ipady=2)
# The bar gained an Export button since this check was written; the
# reconstruction carries it too, in the original sizing idiom, so the
# comparison stays four-against-four -- compact styling vs pre-fix
# styling, not four buttons vs three.
tk.Button(_old_bar, text="\U0001F4BE Export ▾", font=("Segoe UI", 8)
          ).pack(side="left", ipadx=4, ipady=2)
_old_bar.update_idletasks()
old_width = _old_bar.winfo_reqwidth()
_old_bar.destroy()

check(f'bulk action bar is narrower than the pre-fix sizing '
      f'({fixed_width}px vs {old_width}px reconstructed original)',
      fixed_width < old_width)

card_ids_before = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
app._toggle_note_selected(10, True)
app.update()
card_ids_after = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
check('selecting a note does NOT rebuild the list (no flicker)', card_ids_before == card_ids_after)
check('selection recorded correctly', app.selected_note_ids == {10})

app._bulk_select_all()
app.update()
check('Select all picks up every visible note', app.selected_note_ids == {10, 11})

# bulk trash, with attachment mention
app.trash = []  # earlier sections (calendar delete tests) left entries here
captured = {}
app.ask_yes_no = lambda t, m, **k: (captured.__setitem__('msg', m), True)[1]
app._bulk_move_to_trash()
app.update()
check('bulk trash confirmation mentions the attachment', '1 attached file' in captured.get('msg', ''))
check('both notes moved to trash', len(app.trash) == 2 and len(app.notes) == 0)
check('selection mode auto-exits after a bulk action', app.selection_mode is False)

# highlight border: correct note, moves correctly, matches theme accent
app.notes = [
    {'id': 20, 'title': 'C', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 21, 'title': 'D', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.find_note(20))
app.update()
check('opened note is highlighted', app._note_card_widgets[20]['card'].cget('highlightthickness') == 2)
check('other note is not highlighted', app._note_card_widgets[21]['card'].cget('highlightthickness') == 0)
check('highlight color matches the theme accent',
      app._note_card_widgets[20]['card'].cget('highlightbackground') == app.colors['accent'])

card_ids_before2 = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
app.open_note_in_tab(app.find_note(21))
app.update()
card_ids_after2 = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
check('switching notes does NOT rebuild the list (no flicker)', card_ids_before2 == card_ids_after2)
check('highlight correctly moved to the new note', app._note_card_widgets[21]['card'].cget('highlightthickness') == 2)

# bulk category change
app.ask_yes_no = lambda *a, **k: True
app._toggle_selection_mode()
app._toggle_note_selected(20, True)
app.update()
app._bulk_change_category()
app.update()
work_lbl = find_widget(app._mini_popup, tk.Label, 'Work')
work_lbl.event_generate('<Button-1>')
app.update()
check('bulk category change applied', app.find_note(20)['category'] == 'Work')

# ============================================================
# 4. IMAGE PREVIEW (Pillow)
# ============================================================
png_bytes = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
with open(os.path.join(NO.ATTACHMENTS_DIR, 'preview.png'), 'wb') as f:
    f.write(png_bytes)

def make_png(width, height, color=(255, 0, 0)):
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    row = bytes([0]) + bytes(color) * width
    raw = row * height
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

with open(os.path.join(NO.ATTACHMENTS_DIR, 'big.png'), 'wb') as f:
    f.write(make_png(2000, 1000))
with open(os.path.join(NO.ATTACHMENTS_DIR, 'corrupt.png'), 'wb') as f:
    f.write(b'not a real png')

app.new_note()
app.current_attachments = [
    {'filename': 'preview.png', 'stored_as': 'preview.png'},
    {'filename': 'big.png', 'stored_as': 'big.png'},
]
app.refresh_attachments_list(); app.update()

app.open_attachment(0)
app.update()
img = app._image_preview_ref
check('small image gets zoomed up for visibility (capped at 8x)', img[0].width() == 8 and img[0].height() == 8)
app._dismiss_mini_popup(); app.update()

app.open_attachment(1)
app.update()
target_w = app.winfo_width() * 0.7
img2 = app._image_preview_ref
check('large image is shrunk to fit within the window', img2[0].width() <= target_w + 5)

close_btn = find_widget(app._mini_popup, tk.Button, '✕ Close')
close_btn.invoke()
app.update()
check('Close button dismisses the preview', app._mini_popup is None)

app.current_attachments = [{'filename': 'corrupt.png', 'stored_as': 'corrupt.png'}]
app.refresh_attachments_list(); app.update()
app.open_attachment(0)
app.update()
check('corrupt image file handled gracefully, no crash', app._mini_popup is None)

# non-previewable file still gets the "opens externally" hint
app.current_attachments = [{'filename': 'doc.pdf', 'stored_as': 'doc.pdf'}]
app.refresh_attachments_list(); app.update()
texts = find_all_labels(app.attachments_frame)
check('non-image attachment shows the external-open hint',
      any('Opens in your default app' in t for t in texts))

# ============================================================
# 5. ATTACHMENT MENTION IN DELETE CONFIRMATIONS (single delete)
# ============================================================
app.notes = [{'id': 30, 'title': 'SingleDeleteAttach', 'body': 'x', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [],
              'attachments': [{'filename': 'y.png', 'stored_as': 'y.png'}]}]
app.save_notes()
app.load_note(app.notes[0])
captured2 = {}
app.ask_yes_no = lambda t, m, **k: (captured2.__setitem__('msg', m), False)[1]
app.delete_current_note()
check('single-delete confirmation mentions the attachment', '1 attached file' in captured2.get('msg', ''))

# ============================================================
# 6. "NOTE MISSING" BUG REGRESSION
# ============================================================
app.notes = [
    {'id': 40, 'title': 'KeepOpen', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 41, 'title': 'ToDeleteViaContext', 'body': 'x', 'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.find_note(40))
app.update()
app.title_entry.insert(tk.END, ' - unsaved')

error_shown = {'called': False}
app.show_error = lambda t, m: error_shown.update(called=True)
app.ask_yes_no = lambda *a, **k: True
app._context_delete_note(app.find_note(41))
app.update()
check('no spurious "Note missing" error when deleting an unrelated note', not error_shown['called'])
check('the genuinely-open note stays open', app.selected_note_id == 40)
check('its unsaved edit was correctly flushed and saved', 'unsaved' in app.find_note(40)['title'])

# ============================================================
# 6b. CANCELLED CONTEXT-DELETE MUST NOT HIJACK THE SELECTION
# ============================================================
# The delete-selection-hijack bug: _context_delete_note used to repoint
# selected_note_id at the right-clicked note so delete_current_note
# would act on it. Answering No to the confirm (or cancelling the
# occurrence-scope prompt) returned with the selection still on the
# WRONG note, and the next autosave silently overwrote that note with
# the open note's content. The delete target travels as a parameter
# now; a cancel must leave every bit of state exactly as it was.
import copy as _copy_q7

app.notes = [
    {'id': 45, 'title': 'OpenNote', 'body': 'open body', 'category': 'General',
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 46, 'title': 'VictimNote', 'body': 'victim body', 'category': 'General',
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.find_note(45))
app.update()

victim_before = _copy_q7.deepcopy(app.find_note(46))
trash_before = len(app.trash)
app.ask_yes_no = lambda *a, **k: False  # user answers No
app._context_delete_note(app.find_note(46))
app.update()
check('cancelled context-delete keeps the selection on the open note',
      app.selected_note_id == 45)

# Keep typing, then let the autosave path the bug rode fire for real.
app.title_entry.insert(tk.END, ' typed-after-cancel')
app._autosave_now()
app.update()
check('autosave after a cancelled context-delete lands in the OPEN note',
      'typed-after-cancel' in app.find_note(45)['title'])
check('the right-clicked note is untouched bit for bit',
      app.find_note(46) == victim_before)
check('a cancelled delete moves nothing to trash', len(app.trash) == trash_before)

# Same contract on the occurrence-scope cancel (the calendar route).
app.notes = app.notes + [
    {'id': 48, 'title': 'RecurringVictim', 'body': 'x', 'category': 'General', 'date': '2026-07-01',
     'recurrence': {'freq': 'daily'}, 'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}},
]
app.save_notes()
app.refresh_note_list(); app.update()
app.ask_occurrence_scope = lambda *a, **k: None  # user cancels the scope prompt
app._context_delete_note(app.find_note(48), '2026-07-09')
app.update()
check('cancelled scope prompt keeps the selection on the open note',
      app.selected_note_id == 45)
check('cancelled scope prompt leaves the series untouched',
      app.find_note(48).get('exceptions') == [])
check('cancelled scope prompt leaves the occurrence date alone',
      app.current_occurrence_date is None)

# ============================================================
# 6c. THE CALENDAR WRAPPER, THE RE-ANCHOR, AND THE POSITIVE DELETE
# ============================================================
# Three gaps a post-merge review found in 6b's coverage: the calendar
# wrapper (_delete_note_from_calendar) carried no selection assertions,
# so a hijack reintroduced in THAT frame would pass the whole suite;
# nothing proved _delete_note's find_note re-anchor (mutations must
# land in the store even when a caller hands over a copy); and no check
# anywhere asserted the editor Delete button's own confirmed delete.

# The wrapper, scope-cancel: same contract as 6b, one frame higher.
recur_before = _copy_q7.deepcopy(app.find_note(48))
app.ask_occurrence_scope = lambda *a, **k: None
app._delete_note_from_calendar(app.find_note(48), '2026-07-09')
app.update()
check('wrapper scope-cancel keeps the selection on the open note',
      app.selected_note_id == 45)
check('wrapper scope-cancel leaves the occurrence date alone',
      app.current_occurrence_date is None)
app.title_entry.insert(tk.END, ' wrap-cancel')
app._autosave_now()
app.update()
check('autosave after a wrapper cancel lands in the OPEN note',
      'wrap-cancel' in app.find_note(45)['title'])

# The wrapper, whole-series confirm-cancel.
app.ask_occurrence_scope = lambda *a, **k: 'series'
app.ask_yes_no = lambda *a, **k: False
app._delete_note_from_calendar(app.find_note(48), '2026-07-09')
app.update()
check('wrapper series-confirm-cancel keeps the selection on the open note',
      app.selected_note_id == 45)
check('the recurring note survives both wrapper cancels bit for bit',
      app.find_note(48) == recur_before)

# The re-anchor: a caller handing over a COPY must still mutate the store.
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
stale_copy = _copy_q7.deepcopy(app.find_note(48))
app._delete_note(stale_copy, '2026-07-10')
app.update()
check('occurrence delete via a stale copy still lands in the store',
      '2026-07-10' in app.find_note(48).get('exceptions', []))
check("deleting another note's occurrence leaves the editor alone",
      app.selected_note_id == 45)

# The editor Delete button's own route, confirmed for real.
app.ask_yes_no = lambda *a, **k: True
app.open_note_in_tab(app.find_note(46))
app.update()
trash_before2 = len(app.trash)
app.delete_current_note()
app.update()
check('editor-route confirmed delete removes the note', app.find_note(46) is None)
check('editor-route confirmed delete lands in trash',
      len(app.trash) == trash_before2 + 1 and any(t.get('id') == 46 for t in app.trash))
check('editor resets to a fresh note after deleting the open note',
      app.selected_note_id is None)
check('the neighbour note survives the confirmed delete', app.find_note(45) is not None)

# Mock hygiene: un-shadow the real scope prompt rather than "restoring" a
# saved value that could itself be an earlier section's leaked mock.
del app.ask_occurrence_scope

# ============================================================
# 6d. CALENDAR OCCURRENCE UX: WAY BACK, DAY BANNER, MENU, RETURN RULES
# ============================================================
# Field feedback, four pieces: the right-click edit routes lost the
# "Back to Calendar" button (only the panel's Edit button kept it); the
# editor showed only the series' start date, never WHICH day you were
# editing; the calendar menu offered a generic Open/Edit beside the two
# explicit edit scopes; and with occurrence saves riding on explicit
# gestures, Save yanked the user back to the calendar on every one.
import types as _types_q7

app.notes = [
    {'id': 60, 'title': 'SeriesUX', 'body': 'series body', 'category': 'General',
     'date': '2026-07-01', 'recurrence': {'freq': 'daily'},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}},
    {'id': 61, 'title': 'PlainDated', 'body': 'x', 'category': 'General',
     'date': '2026-07-15', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.render_calendar(); app.update()

# The right-click edit routes remember the way back now.
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()
check('ctx-open from a calendar day sets the way back (origin edit)',
      (app._pending_calendar_return or {}).get('date_str') == '2026-07-15'
      and (app._pending_calendar_return or {}).get('origin') == 'edit')
check('the Back to Calendar button is mapped on the ctx route',
      bool(app.calendar_return_btn.winfo_ismapped()))
check('the banner names the day being edited',
      bool(app.occurrence_banner.winfo_ismapped())
      and '15 July 2026' in app.occurrence_banner.cget('text'))

app.load_note(app.find_note(61)); app.update()
check('the banner hides on a plain note',
      not app.occurrence_banner.winfo_ismapped())
app.load_note(app.find_note(60)); app.update()
check('the banner switches to the series text on the series view',
      bool(app.occurrence_banner.winfo_ismapped())
      and 'edits here apply to every day' in app.occurrence_banner.cget('text'))

# An explicit Save on an EDIT-origin visit stays in the editor...
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app.body_text.insert('end', ' ux-edit')
app.save_current_note(auto=False); app.update()
check('an explicit Save on an edit-origin visit stays in the editor',
      app.notebook.index(app.notebook.select()) == app.TAB_NOTES
      and bool(app._pending_calendar_return))
del app.ask_occurrence_scope

# ...while the quick add-a-note flow still returns to the calendar.
app._add_note_for_date('2026-08-20'); app.update()
app.body_text.insert('1.0', 'quick add body')
app.save_current_note(auto=False); app.update()
check('an explicit Save on an add-origin visit returns to the calendar',
      app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
      and not app._pending_calendar_return)
app.close_day_panel(); app.update()

# Back to Calendar saves the pending occurrence edit, asking once.
app._open_note_from_calendar(app.find_note(60), '2026-07-16'); app.update()
scope_ux = []
app.ask_occurrence_scope = lambda *a, **k: (scope_ux.append(1), 'occurrence')[1]
app.body_text.insert('end', ' flushed-on-return')
app._return_to_calendar(); app.update()
check('Back to Calendar saves the pending edit, asking exactly once',
      len(scope_ux) == 1
      and 'flushed-on-return'
      in app.find_note(60)['overrides'].get('2026-07-16', {}).get('body', ''))
# Settle any still-deferred edit while the mock is armed — under the
# no-flush mutant the editor stays dirty here, and a later section's
# flush would otherwise raise the REAL scope dialog and hang the run.
app.open_blank_tab(); app.update()
del app.ask_occurrence_scope
app.close_day_panel(); app.update()

# The calendar menu drops the generic Open/Edit for a recurring note —
# menu labels are captured by patching tk.Menu, popup suppressed.
_labels_q7 = []
_orig_addc = tk.Menu.add_command
_orig_casc = tk.Menu.add_cascade
_orig_pop = tk.Menu.tk_popup
tk.Menu.add_command = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), kw.get('command')))
tk.Menu.add_cascade = lambda self, **kw: _labels_q7.append(
    (kw.get('label', ''), None))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    _ev_q7 = _types_q7.SimpleNamespace(x_root=100, y_root=100)
    app.show_note_context_menu(_ev_q7, app.find_note(60),
                               occurrence_date='2026-07-15')
    _rec_items = list(_labels_q7); _labels_q7.clear()
    app.show_note_context_menu(_ev_q7, app.find_note(61),
                               occurrence_date='2026-07-15')
    _plain_items = list(_labels_q7)
finally:
    tk.Menu.add_command = _orig_addc
    tk.Menu.add_cascade = _orig_casc
    tk.Menu.tk_popup = _orig_pop
_rec_labels = [l for l, _ in _rec_items]
_plain_labels = [l for l, _ in _plain_items]
check('the calendar menu drops generic Open/Edit for a recurring note',
      not any('Open / Edit' in l for l in _rec_labels)
      and any('only this occurrence' in l for l in _rec_labels)
      and any('whole series' in l for l in _rec_labels))
check('a plain dated note keeps Open/Edit in the calendar menu',
      any('Open / Edit' in l for l in _plain_labels))

# The captured commands are the REAL menu lambdas — invoke them, so the
# return_day plumbing one frame above _ctx_open is exercised too (the
# same frame class a hijack once hid in for deletes).
_series_cmd = next((c for l, c in _rec_items if 'whole series' in l), None)
if _series_cmd is not None:
    _series_cmd(); app.update()
check("the menu's Edit-whole-series lambda arms the way back",
      _series_cmd is not None
      and (app._pending_calendar_return or {}).get('date_str') == '2026-07-15'
      and (app._pending_calendar_return or {}).get('origin') == 'edit'
      and app.current_occurrence_date is None)
_repeat_cmd = next((c for l, c in _plain_items if 'Make this repeat' in l), None)
if _repeat_cmd is not None:
    _repeat_cmd(); app.update()
check('Make-this-repeat from a calendar day arms the way back too',
      _repeat_cmd is not None
      and (app._pending_calendar_return or {}).get('origin') == 'edit')

# The banner follows an occurrence-to-occurrence switch — the text must
# update even when the label is already packed.
app._ctx_open(app.find_note(60), '2026-07-15', return_day='2026-07-15')
app.update()
app._ctx_open(app.find_note(60), '2026-07-16', return_day='2026-07-16')
app.update()
check('the banner follows an occurrence-to-occurrence switch',
      '16 July 2026' in app.occurrence_banner.cget('text'))

# Cancelling the save question ABORTS the trip back — navigating anyway
# would show the day panel's old content while the edit sits only in
# the editor.
app._ctx_open(app.find_note(60), '2026-07-17', return_day='2026-07-17')
app.update()
app.body_text.insert('end', ' cancel-me')
_scopeN = []
app.ask_occurrence_scope = lambda *a, **k: (_scopeN.append(1), None)[1]
app._return_to_calendar(); app.update()
check('cancelling the save question aborts the trip back',
      len(_scopeN) == 1
      and app.notebook.index(app.notebook.select()) == app.TAB_NOTES
      and bool(app._pending_calendar_return)
      and bool(app.calendar_return_btn.winfo_ismapped())
      and 'cancel-me' in app.body_text.get('1.0', 'end-1c'))
check('nothing reached the store on cancel',
      'cancel-me' not in
      app.find_note(60)['overrides'].get('2026-07-17', {}).get('body', ''))
del app.ask_occurrence_scope
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app._return_to_calendar(); app.update()
check('answering the question completes the trip',
      app.notebook.index(app.notebook.select()) == app.TAB_CALENDAR
      and 'cancel-me' in app.find_note(60)['overrides']['2026-07-17']['body'])
del app.ask_occurrence_scope
app.close_day_panel(); app.update()

# Deleting ends the calendar trip on BOTH cleanup arms — a pending that
# outlived a delete once made a later, unrelated Save yank the user
# onto a stale calendar day.
app._ctx_open(app.find_note(61), None, return_day='2026-07-15'); app.update()
app.ask_yes_no = lambda *a, **k: True
app.delete_current_note(); app.update()
check('deleting the open note ends the calendar trip (fresh-editor arm)',
      not app._pending_calendar_return
      and not app.calendar_return_btn.winfo_ismapped())
app.notes.append({'id': 63, 'title': 'Bystander', 'body': 'x',
                  'category': 'General', 'updated': '2026-01-01 00:00',
                  'created': '2026-01-01 00:00', 'checklist': [],
                  'attachments': []})
app.save_notes(); app.refresh_note_list(); app.update()
app._ctx_open(app.find_note(60), '2026-07-18', return_day='2026-07-18')
app.update()
app._context_delete_note(app.find_note(63)); app.update()
check('deleting another note ends the trip too (tab-restore arm)',
      not app._pending_calendar_return
      and not app.calendar_return_btn.winfo_ismapped())

# Un-repeating via a series save retires the day banner — an occurrence
# view of a note that no longer repeats would be a lying label.
app._ctx_open(app.find_note(60), '2026-07-19', return_day='2026-07-19')
app.update()
app.write_recurrence_to_ui({})
_scopeF = []
app.ask_occurrence_scope = lambda *a, **k: (_scopeF.append(1), 'series')[1]
app.save_current_note(auto=False); app.update()
check('un-repeating via a series save retires the day banner',
      len(_scopeF) == 1 and app.current_occurrence_date is None
      and not app.occurrence_banner.winfo_ismapped())
del app.ask_occurrence_scope

# ============================================================
# 6e. OCCURRENCE VISIBILITY: SERIES BANNER, ✎ MARKS, RESET, FILTER
# ============================================================
# The invisible-override field report: a series edit seemed to skip one
# day out of three — that day carried an "only this occurrence" edit,
# which shadows series content forever with nothing saying so and no
# way back. Now the series view names it, the calendar marks it, a menu
# entry resets it, and the sidebar filter can isolate calendar notes.
app.notes = [
    {'id': 64, 'title': 'SeriesVis', 'body': 'series body', 'category': 'General',
     'date': '2026-07-01', 'recurrence': {'freq': 'daily'},
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': [], 'exceptions': [],
     'overrides': {'2026-07-15': {'title': 'SeriesVis', 'body': 'my special day',
                                  'comments': '', 'category': 'General',
                                  'color': ''}}},
    {'id': 65, 'title': 'DatedVis', 'body': 'x', 'category': 'General',
     'date': '2026-07-20', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []},
    {'id': 66, 'title': 'PlainVis', 'body': 'x', 'category': 'General',
     'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
     'checklist': [], 'attachments': []},
]
app.save_notes()
app.refresh_note_list(); app.render_calendar(); app.update()

# The series view names the repeat AND the days living on their own.
app.open_note_in_tab(app.find_note(64)); app.update()
_btext = app.occurrence_banner.cget('text')
check('the series banner says edits apply to every day',
      app.occurrence_banner.winfo_ismapped()
      and 'edits here apply to every day' in _btext)
check('the series banner counts the days with their own edits',
      '1 day keeps its own edits' in _btext)

# The calendar marks the overridden day: list row icon + preview chip.
app.open_day_popup('2026-07-15'); app.update()
_rows15 = find_all_labels(app.day_panel)
check('the day list marks an overridden day with the pencil',
      any('✎' in t and 'SeriesVis' in t for t in _rows15))
app.show_day_note(app.find_note(64), '2026-07-15'); app.update()
check('the day preview carries the edited-for-this-day chip',
      any('✎ edited for this day' in t for t in find_all_labels(app.day_panel)))
app.close_day_panel(); app.update()

# The menu offers the reset only where an override exists.
_labels6e = []
_o_add6e, _o_casc6e, _o_pop6e = (tk.Menu.add_command, tk.Menu.add_cascade,
                                 tk.Menu.tk_popup)
tk.Menu.add_command = lambda self, **kw: _labels6e.append(
    (kw.get('label', ''), kw.get('command')))
tk.Menu.add_cascade = lambda self, **kw: _labels6e.append(
    (kw.get('label', ''), None))
tk.Menu.tk_popup = lambda self, *a, **k: None
try:
    _ev6e = _types_q7.SimpleNamespace(x_root=100, y_root=100)
    app.show_note_context_menu(_ev6e, app.find_note(64),
                               occurrence_date='2026-07-15')
    _with_ov = list(_labels6e); _labels6e.clear()
    app.show_note_context_menu(_ev6e, app.find_note(64),
                               occurrence_date='2026-07-16')
    _without_ov = list(_labels6e)
finally:
    tk.Menu.add_command, tk.Menu.add_cascade, tk.Menu.tk_popup = (
        _o_add6e, _o_casc6e, _o_pop6e)
check('the reset entry appears exactly where an override exists',
      any('Reset this day' in l for l, _ in _with_ov)
      and not any('Reset this day' in l for l, _ in _without_ov))

# Invoke the REAL reset command: the day follows the series again.
# (next() with a default: a missing entry must FAIL the check, not
# crash the suite mid-run — the footer rule.)
_reset_cmd = next((c for l, c in _with_ov if 'Reset this day' in l), None)
app.ask_yes_no = lambda *a, **k: True
if _reset_cmd is not None:
    _reset_cmd(); app.update()
check('reset drops the override and the day shows series content',
      _reset_cmd is not None
      and '2026-07-15' not in (app.find_note(64).get('overrides') or {})
      and NO.effective_note(app.find_note(64),
                            '2026-07-15')['body'] == 'series body')
app.close_day_panel(); app.update()

# The sidebar filter isolates calendar notes — one judgment, used by
# the list render AND bulk select-all, exercised through the render.
app.filter_var.set(app.FILTER_REPEATING)
app.refresh_note_list(); app.update()
_vis = find_all_labels(app.list_frame)
check('the Repeating filter shows only repeating notes',
      any('SeriesVis' in t for t in _vis)
      and not any('DatedVis' in t for t in _vis)
      and not any('PlainVis' in t for t in _vis))
app.filter_var.set(app.FILTER_DATED)
app.refresh_note_list(); app.update()
_vis = find_all_labels(app.list_frame)
check('the Dated filter shows only dated non-repeating notes',
      any('DatedVis' in t for t in _vis)
      and not any('SeriesVis' in t for t in _vis)
      and not any('PlainVis' in t for t in _vis))
app.filter_var.set('All')
app.refresh_note_list(); app.update()

# The Calendar-first sort stacks the calendar dwellers on top:
# repeating series, then dated one-offs, then everything else.
# The starting order is made ADVERSE first (plain newest, series
# oldest, list reversed) — with the fixture's natural order equal to
# the expected one, a disabled sort branch passed this check unsorted.
app.notes.sort(key=lambda n: n['id'], reverse=True)
for _n, _ts in zip(app.notes, ['2026-03-01 00:00', '2026-02-01 00:00',
                               '2026-01-01 00:00']):
    _n['updated'] = _ts
app.save_notes()
app.sort_var.set('Calendar first')
app.refresh_note_list(); app.update()
_ordered = [n for t in find_all_labels(app.list_frame)
            for n in ('SeriesVis', 'DatedVis', 'PlainVis') if n in t]
check('Calendar-first sorting stacks the calendar dwellers on top',
      _ordered == ['SeriesVis', 'DatedVis', 'PlainVis'])
app.sort_var.set('Recently updated')
app.refresh_note_list(); app.update()

# ============================================================
# 7. ATTACHMENT-ONLY NOTE AUTOSAVE
# ============================================================
tmp_file = os.path.join(tempfile.gettempdir(), 'qa7_attach_only.txt')
with open(tmp_file, 'w') as f: f.write('x')

app.open_blank_tab()
app.update()
fd.askopenfilenames = lambda **k: (tmp_file,)
app.add_attachment()
app.update()
check('adding an attachment schedules an autosave', getattr(app, '_autosave_job', None) is not None)

app.after_cancel(app._autosave_job)
app._autosave_now()
app.update()
check('attachment-only note (no title/body) gets saved', app.selected_note_id is not None)
if app.selected_note_id:
    check('saved note has the attachment', len(app.find_note(app.selected_note_id).get('attachments', [])) == 1)

# manual save on a genuinely empty note still warns (regression on the intentional guard)
app.open_blank_tab()
app.update()
warned = {'called': False}
app.show_warning = lambda t, m: warned.update(called=True)
app.save_current_note(auto=False)
app.update()
check('manual save on a truly empty note still warns', warned['called'])

# ============================================================
# 8. LAST-OPEN-NOTE MEMORY
# ============================================================
app.notes = [{'id': 50, 'title': 'RememberMe', 'body': 'remembered body', 'category': 'General',
              'comments': 'a comment', 'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [{'text': 'item', 'done': False}], 'attachments': []}]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.notes[0])
app.update()

saved_settings = NO.load_settings()
check('last-open note id persisted to settings', saved_settings.get('last_open_note_id') == 50)

# new note creation also remembers itself
app.open_blank_tab()
app.update()
app.title_entry.insert(0, 'BrandNew')
app.body_text.insert('1.0', 'x')
app.save_current_note(auto=False)
app.update()
new_id = app.selected_note_id
saved_settings2 = NO.load_settings()
check('creating a new note also updates the remembered id', saved_settings2.get('last_open_note_id') == new_id)

print()
print(f"=== QA7 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
