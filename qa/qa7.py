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
