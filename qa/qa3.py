# HERMETIC SEED -- BEFORE the note_organizer import below. Building the
# app calls initialise(), which resolves the data directory and runs the
# data MIGRATIONS, so this script's data directory must be its own by
# then; seeding it before the import leaves no step in between.
# hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to run at all
# outside a scratch run, or beside a notebook it cannot prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile, time, zipfile, json
import contextlib
import errno
import zlib
import threading
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import click as _qa_click, pin_popup_visibility as _qa_pin
_qa_pin(NO)
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.ask_yes_no=lambda *a,**k: True
app.geometry('1100x850'); app.update()

def find_btn(w, txt_contains):
    for c in w.winfo_children():
        if isinstance(c,tk.Button) and txt_contains in str(c.cget('text')): return c
        r=find_btn(c,txt_contains)
        if r: return r
    return None

def find_text_widget(w):
    for c in w.winfo_children():
        if isinstance(c,tk.Text): return c
        r=find_text_widget(c)
        if r: return r
    return None

def click_dialog_button(app, label):
    """Search every currently-placed overlay for the target button, rather
    than assuming the themed dialog is always the LAST one in place_slaves()
    — a lingering toast notification (or any other .place()'d overlay) can
    end up after the real dialog in that list, and blindly grabbing [-1]
    then finds an empty frame with no matching button at all."""
    app.update()
    for frame in app.place_slaves():
        b = find_btn(frame, label)
        if b:
            b.invoke()
            return

# ---- TRASH: pagination ----
app.trash = [{'id':i,'title':f'Deleted{i}','body':'x','category':'General',
             'deleted_at':f'2026-01-{(i%28)+1:02d} 00:00:00'} for i in range(600)]
app.show_settings_page(); app.update()
t0=time.perf_counter()
app.toggle_settings_panel('trash')
app.update()
elapsed=(time.perf_counter()-t0)*1000
# What makes this panel fast is that it PAGES: it draws one page of rows
# whatever the trash holds. That is the promise, and it is what this
# asserts -- checked further down, where the row count is read.
#
# The wall clock is kept only as a "did it hang" guard, with a ceiling
# loose enough that it cannot go red for being measured on a busy
# machine. It twice did: 515ms under mutation load, 604ms with more
# checks alive in the same process, both times with the paging working
# perfectly. A budget that fails when the machine is busy reports the
# machine, not the app -- and the house rules call that a bug in the
# check, not a flake to re-run.
check(f'trash panel opens without hanging on 600 entries ({elapsed:.0f}ms)',
      elapsed < 4000)

def count_rows(w, marker):
    count=[0]
    def walk(x):
        for c in x.winfo_children():
            if isinstance(c,tk.Label) and marker in str(c.cget('text')): count[0]+=1
            walk(c)
    walk(w)
    return count[0]
# Read the page size from the app rather than hardcoding it. What matters
# here is that the panel pages at all and that "Show more" adds exactly one
# more page -- not the specific number, which is a performance tuning knob
# (it went 50 -> 25 when Settings began showing one section at a time, and
# hardcoding it here meant a tuning change looked like a broken feature).
PAGE = app.TRASH_PAGE_SIZE
initial_rows = count_rows(app.settings_trash_panel, 'Deleted')
check(f'trash paginated to {PAGE} initial rows', initial_rows==PAGE)

def trash_row_labels():
    out = []
    def walk(x):
        for c in x.winfo_children():
            if isinstance(c, tk.Label) and 'Deleted' in str(c.cget('text')):
                out.append(c)
            walk(c)
    walk(app.settings_trash_panel)
    return out


first_page = trash_row_labels()
show_more = find_btn(app.settings_trash_panel, 'Show')
check('Show more button present', show_more is not None)
if show_more:
    show_more.invoke()
    app.update()
    check(f'Show more expands to {PAGE*2} rows',
          count_rows(app.settings_trash_panel, 'Deleted')==PAGE*2)
    # Added under the rows already drawn, not all drawn again: that
    # flickered and grew with every page (field pass). The new rows scroll
    # with the wheel like the old.
    both_pages = trash_row_labels()
    check('...under the rows already drawn, which stay the same rows',
          both_pages[:PAGE] == first_page
          and all(w.winfo_exists() for w in first_page)
          and bool(both_pages[-1].bind('<MouseWheel>')))

# A note deleted while the panel is open (from the sidebar, which stays on
# screen) moves every row down one: Show more then draws them all again,
# or one row showed twice and the new one never (audit).
app.toggle_settings_panel('trash'); app.update()
_st_note = NO.normalize_note({'id': 7777, 'title': 'FreshlyTrashed', 'body': 'x'})
app.notes.append(_st_note)
app._move_notes_to_trash([_st_note])
_st_more = find_btn(app.settings_trash_panel, 'Show')
if _st_more:
    _st_more.invoke()
    app.update()
_st_titles = []
def _st_walk(x):
    for c in x.winfo_children():
        if isinstance(c, tk.Label):
            t = str(c.cget('text'))
            if t.startswith('Deleted') or t == 'FreshlyTrashed':
                _st_titles.append(t)
        _st_walk(c)
_st_walk(app.settings_trash_panel)
check(f'Show more after a delete elsewhere shows each note once, the new one '
      f'included ({len(_st_titles)} rows)',
      _st_more is not None and 'FreshlyTrashed' in _st_titles
      and len(_st_titles) == len(set(_st_titles)) == PAGE * 2)
app.trash = [e for e in app.trash if e.get('title') != 'FreshlyTrashed']
app.toggle_settings_panel('trash'); app.update()

# restore preserves pagination + moves note back
restore_btn = find_btn(app.settings_trash_panel, 'Restore')
before_trash = len(app.trash)
before_notes = len(app.notes)
if restore_btn:
    restore_btn.invoke()
    app.update()
check('restore removes from trash', len(app.trash)==before_trash-1)
check('restore adds to notes', len(app.notes)==before_notes+1)

# empty trash
app.toggle_settings_panel('trash'); app.update()
app.toggle_settings_panel('trash'); app.update()
empty_btn = find_btn(app.settings_trash_panel, 'Empty trash')
if empty_btn:
    empty_btn.invoke()
    app.update()
check('empty trash clears everything', len(app.trash)==0)

# ---- SHARE CODE (single + multi note) ----
app.notes = [{'id':1,'title':'ShareMe','body':'share body','comments':'','category':'General',
             'date':'','color':'','recurrence':{},'updated':'2026-01-01 00:00',
             'created':'2026-01-01 00:00','checklist':[],'attachments':[]}]
app.save_notes()
app.notebook.select(0); app.update()
app.load_note(app.notes[0])
app.share_current_note_as_code()
app.update()
check('share code area becomes visible', app.editor_code_area.winfo_ismapped())
code_entry = find_text_widget(app.editor_code_area)
check('share code text widget exists', code_entry is not None)
# Generate, fix a word, Copy: the code that went out was the one from before
# the fix, a wall of characters nobody proofreads.
app.body_text.insert('end', ' and the fix')
_sc_copy = next(w for w in app.editor_code_area.winfo_children()
                if isinstance(w, tk.Button) and 'Copy code' in str(w.cget('text')))
_sc_copy.invoke(); app.update()
_sc_out = NO.decode_share_code(app.clipboard_get())[0]
check(f'Copy code copies the note as it is now, not as it was at Generate ({_sc_out.get("body")!r})',
      _sc_out.get('body') == 'share body and the fix')
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'share body')
# Generate code from the page's top: the code at the page's foot sat below the
# window's edge and nothing moved, so the button seemed to do nothing (the
# review panel, 22 November). The code and its Copy button come into sight.
app.editor_code_area.pack_forget(); app.update()
app.editor_canvas.yview_moveto(0.0); app.update()
app.share_current_note_as_code(); app.update()
_gc_box = find_text_widget(app.editor_code_area)
_gc_btn = next(w for w in app.editor_code_area.winfo_children()
               if isinstance(w, tk.Button) and 'Copy code' in str(w.cget('text')))
# Read in the page's own height, which a scroll does not move: an embedded
# window's place on the screen waits for a redraw the suite may not get.
_gc_page = app.editor_canvas.bbox(app._editor_window)
_gc_seen = (_gc_box.winfo_rooty() - app.editor.winfo_rooty(),
            _gc_btn.winfo_rooty() + _gc_btn.winfo_height() - app.editor.winfo_rooty())
if not _gc_page or _gc_page[3] - _gc_page[1] <= app.editor_canvas.winfo_height():
    print('SKIP Generate code brings its code into sight (the whole page fits this window)')
else:
    _gc_total = _gc_page[3] - _gc_page[1]
    _gc_view = tuple(round(f * _gc_total) for f in app.editor_canvas.yview())
    check(f'Generate code brings its code and Copy button into sight '
          f'({_gc_seen} within {_gc_view} of a {_gc_total}-pixel page)',
          _gc_view[0] <= _gc_seen[0] and _gc_seen[1] <= _gc_view[1] + 1)

# decode round trip
# Paragraphs travel too: without them a shared note arrived flush
# left with flat lists, and a table lost its place on the page.
_para_note = {'title': 'P', 'body': '| A | B |\n| x | y |',
              'formatting': [],
              'paragraphs': [{'line': 0, 'align': 'center'},
                             {'line': 1, 'align': 'center'}]}
_para_back = NO.decode_share_code(
    NO.encode_share_code([_para_note]))[0]
check('a share code carries the paragraphs (table position, indents)',
      _para_back.get('paragraphs') == _para_note['paragraphs'])
# A code with words around it -- a greeting, a mail signature, a "Thanks!" --
# read only now and then: whether it did hung on the code's padding.
_cw_found = []
for _cw_body in ('x', 'xy', 'xyz', 'wxyz'):   # codes of every padding length
    _cw_code = NO.encode_share_code([{'title': _cw_body, 'body': _cw_body}])
    for _cw_text in ('Hi Ana!\n' + _cw_code + '\nThanks', _cw_code + ' Sent from my phone',
                     'Here: ' + _cw_code[:30] + '\n' + _cw_code[30:]):
        try:
            _cw_found.append(NO.decode_share_code(_cw_text)[0].get('title') == _cw_body)
        except ValueError:
            _cw_found.append(False)
check(f'a code is found among the words around it, padded or not ({_cw_found})',
      all(_cw_found) and len(_cw_found) == 12)
# ...and with its prefix broken by the wrapping ("NOTE\n1:"), read from it as
# from a whole one, as the phone reads it: left to the lenient decoder, a
# stray letter was read here that the phone refuses.
_cb_found = []
for _cw_body in ('x', 'xy', 'xyz', 'wxyz'):
    _cw_code = NO.encode_share_code([{'title': _cw_body, 'body': _cw_body}])
    try:
        _cb_found.append(NO.decode_share_code(
            'Hi\n' + _cw_code[:4] + '\n' + _cw_code[4:] + '\nThanks')[0].get('title') == _cw_body)
    except ValueError:
        _cb_found.append(False)
_cb_code = NO.encode_share_code([{'title': 'stray', 'body': 'stray'}])
try:
    NO.decode_share_code(_cb_code[:4] + '\n' + _cb_code[4:20] + '!' + _cb_code[20:])
    _cb_stray = 'read'
except ValueError:
    _cb_stray = 'refused'
check(f'a code whose prefix the wrapping broke is read as a whole one is, a stray letter '
      f'refused there too ({_cb_found}, {_cb_stray})',
      all(_cb_found) and len(_cb_found) == 4 and _cb_stray == 'refused')
# ...and words that say "NOTE 1:" are no code, said so as before: not called
# a damaged code to send again.
_cb_words = []
for _cb_text in ('Hi NOTE 1: buy milk', 'Meeting notes\nNOTE 1: call Ana about the plan'):
    try:
        NO.decode_share_code(_cb_text)
        _cb_words.append('read')
    except ValueError as _cb_e:
        _cb_words.append(str(_cb_e)[:38])
check(f'...and words saying "NOTE 1:" are said to be no share code ({_cb_words})',
      _cb_words == ["This isn't a Note Organizer share code"] * 2)
# ...while a code that reads keeps its own answer behind a hidden prefix: a
# newer version's was called no share code at all.
import base64 as _cb_b64
_cb_v2 = NO.SHARE_CODE_PREFIX + _cb_b64.urlsafe_b64encode(zlib.compress(
    json.dumps({'v': 2, 'notes': [{'title': 'n'}]}).encode())).decode()
try:
    NO.decode_share_code(_cb_v2[:4] + '\n' + _cb_v2[4:])
    _cb_v2_said = 'read'
except ValueError as _cb_e:
    _cb_v2_said = str(_cb_e)
check(f"...and a newer version's code behind a hidden prefix says so ({_cb_v2_said[:50]!r})",
      'newer version' in _cb_v2_said)
check('and an old code without paragraphs still decodes',
      'paragraphs' not in NO.decode_share_code(NO.encode_share_code([
          {'title': 'v', 'body': 'x', 'formatting': []}]))[0])

# ---- Untrusted-import hardening: decode filters to the shareable slice.
# A HAND-CRAFTED code can put anything in the JSON; decode must hand back
# only the fields a genuine code carries — never attachments (which a
# real code never has and whose stored_as could aim a later delete
# outside the attachments folder), never arbitrary keys.
import json as _json3, base64 as _b643, zlib as _zlib3
def _craft_code_list(notes_list):
    raw = _zlib3.compress(_json3.dumps({'v': 1, 'notes': notes_list}).encode())
    return NO.SHARE_CODE_PREFIX + _b643.urlsafe_b64encode(raw).decode()
def _craft_code(note_dict):
    return _craft_code_list([note_dict])
_evil = NO.decode_share_code(_craft_code({
    'title': 'Evil', 'body': 'b', 'category': 'General',
    'attachments': [{'stored_as': '../../secret.txt'}],
    'id': 999, 'pinned': True, 'bogus': 42}))[0]
check('decode drops attachments smuggled into a crafted code',
      'attachments' not in _evil)
check('decode drops arbitrary non-shareable keys (id, pinned, bogus)',
      not ({'id', 'pinned', 'bogus'} & set(_evil.keys())))
check('decode keeps the genuine shareable fields',
      _evil.get('title') == 'Evil' and _evil.get('body') == 'b')
# A crafted code can also put non-dict entries in the notes list; decode
# must survive them (the `else {}` branch), not throw on the projection.
# Guarded so a mutant that drops the branch fails HARD here (the raise
# is the bug's face) instead of crashing the run before its footer.
try:
    _mixed = NO.decode_share_code(_craft_code_list([
        42, None, 'a string', {'title': 'Real', 'body': 'b'}]))
except Exception:
    _mixed = None
check('decode tolerates non-dict note entries without crashing',
      _mixed is not None and len(_mixed) == 4 and _mixed[:3] == [{}, {}, {}]
      and _mixed[3].get('title') == 'Real')

# Sharing a note that holds a lone UTF-16 surrogate (Tk hands an astral
# emoji over unpaired; mend used to run only on disk-save) must not
# crash encode's utf-8 step (audit Z05-F02).
_emoji_note = {'title': 'plan \U0001F600', 'body': 'lone \ud83d half',
               'category': 'General'}
_enc_ok = True
try:
    _emoji_code = NO.encode_share_code(_emoji_note)
    _emoji_back = NO.decode_share_code(_emoji_code)[0]
except Exception:
    _enc_ok = False
    _emoji_back = {}
check('sharing a note with an astral/lone-surrogate emoji does not crash',
      _enc_ok and '\U0001F600' in _emoji_back.get('title', ''))
check('and the encoded code carries no lone surrogate',
      _enc_ok and not any(0xD800 <= ord(c) <= 0xDFFF
                          for c in _emoji_back.get('body', '')))

# The checklist travels too: a shared note used to arrive without it --
# the one piece of content a code silently dropped.
_ck_note = {'title': 'C', 'body': 'b', 'formatting': [],
            'checklist': [{'text': 'pack bags', 'done': True},
                          {'text': 'call venue', 'done': False}]}
_ck_back = NO.decode_share_code(NO.encode_share_code([_ck_note]))[0]
check('a share code carries the checklist, done states included',
      _ck_back.get('checklist') == _ck_note['checklist'])
check('and an old code without a checklist still decodes',
      'checklist' not in NO.decode_share_code(NO.encode_share_code([
          {'title': 'v', 'body': 'x', 'formatting': []}]))[0])

code = NO.encode_share_code([app.notes[0]])
decoded = NO.decode_share_code(code)
check('share code round-trips correctly', decoded[0]['title']=='ShareMe' and decoded[0]['body']=='share body')

# ---- THE EDITOR'S OWN SHARE ROUTE, END TO END ----
# The core round-trips above can all pass while the UI still loses
# content: the editor's "Copy code" built its note dict from a
# hand-rolled field list (dropping formatting, paragraphs AND the
# checklist), and the single-note import loader never loaded the
# checklist it received -- found in a field test, both ends. This walks
# the REAL route: editor state -> share_current_note_as_code -> the
# rendered code widget -> the import box -> the opened editor.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'RouteFull')
app.body_text.insert('1.0', 'bold word here\ncentred line')
app.body_text.tag_add('sel', '1.0', '1.4')
app._fmt_buttons['bold'].invoke()
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.mark_set('insert', '2.0')
app._set_paragraph_align('center')
app._working_checklist = [{'text': 'pack bags', 'done': True},
                          {'text': 'call venue', 'done': False}]
app.update()
app.share_current_note_as_code()
app.update()
_rt_code = find_text_widget(app.editor_code_area).get('1.0', 'end-1c')
_rt_saved_notes = list(app.notes)
app.notes = []          # clean notebook: no duplicate dialog in the way
app.save_notes()
app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _rt_code)
app._do_inline_import()
app.update()
_rt_st = app.capture_editor_state()
check('the editor-shared code arrives with its checklist, done states '
      'included',
      _rt_st.get('checklist') == [{'text': 'pack bags', 'done': True},
                                  {'text': 'call venue', 'done': False}])
check('...and with its character formatting and paragraph alignment',
      any(sp.get('style') == 'bold' for sp in _rt_st.get('formatting', []))
      and any(p.get('align') == 'center'
              for p in _rt_st.get('paragraphs', [])))
check('...and the checklist section opened so the items are visible',
      app._checklist_open)
# State hygiene: the sections below expect the ShareMe note to exist
# (it is the duplicate their dialog path skips).
app.notes = _rt_saved_notes
app.save_notes()
app.new_note(); app.update()

# ---- THE EDITOR'S CODE HAS TO CARRY THE NOTE'S IDENTITY ----
# The route check above proved the editor's code carries the note's
# CONTENT; it could not see that it carried no IDENTITY, because the
# payload is built from the editor snapshot and the identity is not
# editor content. Field-reported: a note sent out from the editor and
# brought back was copied instead of recognised -- the one thing the
# identity exists to prevent, on the route a user is most likely to
# take. The identity travels only from a SAVED note, so this walks the
# whole way: save, share from the editor, decode.
_id_saved = list(app.notes)
app.notes = []
app.save_notes()
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'TravelsBack')
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'first version')
app.save_current_note()
app.update()
_id_note = next(n for n in app.notes if n['title'] == 'TravelsBack')
app.load_note(_id_note); app.update()
app.share_current_note_as_code(); app.update()
_id_code = find_text_widget(app.editor_code_area).get('1.0', 'end-1c')
_id_payload = NO.decode_share_code(_id_code)
_id_shared = (_id_payload['notes'] if isinstance(_id_payload, dict)
              else _id_payload)[0]
check('a code made in the editor carries the note it was made from',
      _id_shared.get('uid') == _id_note['uid'])

# And the whole point of carrying it: brought back, the note is
# recognised rather than copied.
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'second version, edited here')
app.save_current_note()
app.update()
_id_asked = []
_id_focus = []
_real_dialog = app._themed_dialog
app._themed_dialog = lambda *a, **k: (
    _id_asked.append(a),
    _id_focus.append(k['buttons'][app._dialog_focus_index(k['buttons'], k.get('default'))][0]),
    'update')[2]
app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _id_code)
app._do_inline_import()
app.update()
app._themed_dialog = _real_dialog
check('...so bringing it back asks about THIS note instead of copying it',
      len(_id_asked) == 1 and _id_asked[0][0] == 'Same note, a different version')
check(f'...and Enter there replaces nothing: Cancel holds the focus ({_id_focus})',
      _id_focus == ['Cancel'])
check('...and answering "update" leaves one note, not two',
      len(app.notes) == 1)
check('...the same note, with the version the code carried',
      app.notes[0]['uid'] == _id_note['uid']
      and 'first version' in app.notes[0]['body'])
check('...and the way back is written, so the update can be undone',
      (app.notes[0].get('_prev') or {}).get('body', '').startswith('second version'))

# A note that was never saved has no identity yet, and must travel
# without one rather than borrowing whatever the editor last held.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'NeverSaved')
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'draft')
app.update()
app.share_current_note_as_code(); app.update()
_draft_payload = NO.decode_share_code(
    find_text_widget(app.editor_code_area).get('1.0', 'end-1c'))
_draft_shared = (_draft_payload['notes'] if isinstance(_draft_payload, dict)
                 else _draft_payload)[0]
check('a note that has never been saved shares without an identity',
      not (_draft_shared.get('uid') or '').strip())

# ---- THE CODE ON SCREEN BELONGS TO THE NOTE ON SCREEN ----
# Field-reported: generate a code, click another note, and the code sits
# there looking like the new note's. Copying it then shares the wrong
# note, invisibly -- nobody proofreads a wall of base64.
app.notes = []
app.save_notes()
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'CodeShown')
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'one')
app.save_current_note(); app.update()
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'OtherNote')
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'two')
app.save_current_note(); app.update()
_shown = next(n for n in app.notes if n['title'] == 'CodeShown')
_other = next(n for n in app.notes if n['title'] == 'OtherNote')
app.load_note(_shown); app.update()
app.share_current_note_as_code(); app.update()
check('the code appears under the note it was made for',
      app.editor_code_area.winfo_ismapped())
app.load_note(_other); app.update()
check('...and is gone the moment another note is opened',
      not app.editor_code_area.winfo_ismapped())
app.load_note(_shown); app.update()
app.share_current_note_as_code(); app.update()
app.new_note(); app.update()
check('...and starting a new note clears it too',
      not app.editor_code_area.winfo_ismapped())

# ---- AND THE SAME HAZARD ON THE BULK ROUTE ----
# The bulk route does not re-open anything, so the editor simply keeps
# showing the old version -- and puts it back on its next save, which is
# one keystroke away. Nothing on screen says the update was undone.
app.notes = []
app.save_notes()
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'OpenWhileUpdated')
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'mine, on screen')
app.save_current_note(); app.update()
_bulk_note = app.notes[0]
app.load_note(_bulk_note); app.update()
_bulk_code = NO.encode_share_code([
    {'uid': _bulk_note['uid'], 'title': 'OpenWhileUpdated',
     'body': 'the version that arrived', 'comments': '', 'category': 'General',
     'date': '', 'color': '', 'recurrence': {}},
    {'title': 'AlsoNew', 'body': 'a stranger', 'comments': '',
     'category': 'General', 'date': '', 'color': '', 'recurrence': {}},
])
app._themed_dialog = lambda *a, **k: 'update'
app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _bulk_code)
app._do_inline_import()
app.update()
app._themed_dialog = _real_dialog
_bulk_after = next(n for n in app.notes if n['uid'] == _bulk_note['uid'])
check('a bulk update reaches the note that was open in the editor',
      'the version that arrived' in _bulk_after['body'])
check('...and the editor is showing that version, not the replaced one',
      'the version that arrived' in app.body_text.get('1.0', 'end-1c'))
app._flush_autosave()
app.update()
_bulk_after = next(n for n in app.notes if n['uid'] == _bulk_note['uid'])
check('...so the next save cannot put the replaced version back',
      'the version that arrived' in _bulk_after['body'])
check('...while the note nothing here matched was added',
      any(n['title'] == 'AlsoNew' for n in app.notes))
# A one-note code's Update of the series open on one of its days keeps the day
# and the way back to the calendar, as the batch's does: it took the editor to
# the whole series and dropped Back to Calendar.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Weekly sync', 'body': 'series words',
                                'date': '2026-09-07', 'recurrence': {'freq': 'weekly'}})]
app.save_notes(); app.new_note(); app.update()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
_one_opened_on = app.current_occurrence_date
app._pending_calendar_return = {'year': 2026, 'month': 9, 'date_str': '2026-09-14', 'origin': 'edit'}
_one_code = NO.encode_share_code([dict(app.find_note(1), body='series words, updated')])
app._themed_dialog = lambda *a, **k: 'update'
if not app._is_placed(app.import_panel):
    app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end'); app.import_box.insert('1.0', _one_code)
app._do_inline_import(); app.update()
app._themed_dialog = _real_dialog
check(f"a one-note code's Update keeps the day it was on, and the way back "
      f"({_one_opened_on} -> {app.current_occurrence_date}, {app._pending_calendar_return})",
      _one_opened_on == app.current_occurrence_date == '2026-09-14'
      and app._pending_calendar_return is not None
      and 'updated' in app.find_note(1)['body'])
app._pending_calendar_return = None
app.notes = []; app.save_notes(); app.new_note(); app.update()
# A double-click on Import: the second press found the box the first emptied,
# and said in red that no code was pasted.
from _qa_support import fire as _ib_fire
if not app._is_placed(app.import_panel):
    app.toggle_import_panel(); app.update()
_ib_btn = find_btn(app.import_panel, 'Import')
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', NO.encode_share_code([{'title': 'Twice', 'body': 'a'},
                                                   {'title': 'Clicked', 'body': 'b'}]))
for _ib_t in (300000, 300250):
    if not app._is_placed(app.import_panel):
        app.toggle_import_panel(); app.update()
    _ib_fire(_ib_btn, '<Enter>')
    _ib_fire(_ib_btn, '<ButtonPress-1>', x=5, y=5, rootx=420, rooty=310, time=_ib_t)
    _ib_fire(_ib_btn, '<ButtonRelease-1>', x=5, y=5, rootx=420, rooty=310, time=_ib_t + 60)
    app.update()
_ib_said = str(app.import_status.cget('text'))
check(f"a double-click on Import adds the notes and says nothing false ({_ib_said!r})",
      'No code' not in _ib_said and sum(1 for n in app.notes if n.get('title') in ('Twice', 'Clicked')) == 2)
app.notes = []; app.save_notes(); app.new_note(); app.update()
if app._is_placed(app.import_panel):
    app.toggle_import_panel(); app.update()

# ---- SETTINGS SHOWS WHAT IS TRUE NOW, NOT AT THE LAST VISIT ----
# Field-reported: delete a note, open Settings, and Recently deleted did
# not list it -- the page came back showing the panel built on an earlier
# visit. It appeared only after clicking the nav entry again.
app.trash = []
app.notes = [{'id': 5150, 'title': 'ToBeDeleted', 'body': 'x',
              'comments': '', 'category': 'General', 'date': '', 'color': '',
              'recurrence': {}, 'checklist': [], 'attachments': [],
              'created': '2026-01-01 00:00', 'updated': '2026-01-01 00:00'}]
app.save_notes()
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
check('the trash panel starts out empty', count_rows(app.settings_trash_panel,
                                                     'ToBeDeleted') == 0)
app.hide_settings_page(); app.update()
app._delete_note(app.notes[0], None)
app.update()
app.show_settings_page(); app.update()
check('a note deleted since the last visit is in Recently deleted on arrival',
      count_rows(app.settings_trash_panel, 'ToBeDeleted') == 1)
app.hide_settings_page(); app.update()
app.trash = []

app.notes = list(_id_saved)
app.save_notes()
app.new_note(); app.update()

# ---- IMPORT CODE with duplicate detection ----
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', code)
app.wait_variable = lambda var: click_dialog_button(app, 'Skip the duplicate')
before = len(app.notes)
# multi-note code needed to trigger the dialog path; build one with 1 dup + 1 fresh
multi_notes = [
    {'title':'ShareMe','body':'share body','comments':'','category':'General','date':'','color':'','recurrence':{}},
    {'title':'FreshOne','body':'fresh body','comments':'','category':'General','date':'','color':'','recurrence':{}},
]
multi_code = NO.encode_share_code(multi_notes)
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', multi_code)
app._do_inline_import()
app.update()
check('import code with skip-duplicates adds only the fresh note',
      len(app.notes)==before+1 and any(n['title']=='FreshOne' for n in app.notes))

# ---- A NOTE THAT COMES BACK, EDITED SOMEWHERE ELSE ----
# The case the text-matching duplicate check answers wrongly: the note IS
# one we have, and its text differs precisely BECAUSE it was edited, so
# resemblance says "new note" and would leave two copies behind. Identity
# is asked first, and the user is asked what to do about it.
#
# This block APPENDS to the notebook and deletes exactly what it appended.
# An earlier version replaced app.notes and put the old list back, and the
# checks a hundred lines down lost the notes they were set up with.
app.open_blank_tab()
app.update()
_ident_base = len(app.notes)
app.notes.append(NO.normalize_note({'id': 9001, 'title': 'Departed',
                                    'body': 'text original'}))
app.save_notes()
_ident_note = app.notes[-1]
_sent_uid = _ident_note['uid']
_returned = NO.encode_share_code([{
    'uid': _sent_uid, 'title': 'Departed', 'body': 'text corrected on the phone',
    'formatting': [], 'paragraphs': [], 'comments': '',
    'category': 'General', 'date': '', 'color': '', 'checklist': [],
}])

_asked = []
_real_dlg_id = app._themed_dialog
app._themed_dialog = lambda *a, **k: (_asked.append(a[1]), 'update')[1]
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _returned)
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id

check('a returning note is recognised as one we already have, and asked about',
      len(_asked) == 1 and 'already here' in _asked[0])

# One note we have among several new ones: the batch's question says it as
# one -- "Update the 1" and "Add it as new notes" came of counting it.
# Cancelled, so nothing here changes.
_batch_code = NO.encode_share_code([
    {'uid': _sent_uid, 'title': 'Departed', 'body': 'text corrected again',
     'formatting': [], 'paragraphs': [], 'comments': '',
     'category': 'General', 'date': '', 'color': '', 'checklist': []},
    {'uid': 'one-new-note-in-the-batch', 'title': 'Fresh', 'body': 'new here',
     'formatting': [], 'paragraphs': [], 'comments': '',
     'category': 'General', 'date': '', 'color': '', 'checklist': []},
])
_batch_buttons = []
app._themed_dialog = lambda *a, **k: (_batch_buttons.append(
    [label for label, _v in k.get('buttons') or []]), 'cancel')[1]
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _batch_code)
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id
check(f"one note we have, among new ones: the batch's question says it as one ({_batch_buttons})",
      _batch_buttons[:1] == [['Cancel', 'Add it as a new note', 'Update it']])
check('choosing Update adds no second note',
      len(app.notes) == _ident_base + 1)
check('...and the note we had now carries the text that came back',
      _ident_note['body'] == 'text corrected on the phone')
check('...still in its place: the id did not move',
      _ident_note['id'] == 9001)
check('...still the same note: the identity did not move',
      _ident_note['uid'] == _sent_uid)
check('an update leaves the rescue copy Restore previous reads',
      (_ident_note.get('_prev') or {}).get('body') == 'text original')

# An Update agreed to, the code's other notes all look-alikes: the question
# about them can skip them and go on -- Cancel, its only no, dropped the
# Update unsaid.
_la_known = NO.normalize_note({'id': 9601, 'uid': 'la-known', 'title': 'Synced',
                               'body': 'first words'})
_la_same = NO.normalize_note({'id': 9602, 'title': 'Look alike', 'body': 'same words'})
app.notes += [_la_known, _la_same]
app.save_notes()
_la_asked = []


def _la_answer(*a, **k):
    labels = [label for label, _v in k.get('buttons') or []]
    _la_asked.append(labels)
    return 'update' if 'Update it' in labels else ('skip' if 'Skip them' in labels else 'cancel')


app._themed_dialog = _la_answer
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', NO.encode_share_code([
    {'uid': 'la-known', 'title': 'Synced', 'body': 'second words'},
    {'title': 'Look alike', 'body': 'same words'}]))
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id
check(f"an Update agreed to, then look-alikes skipped: the Update still happens ({_la_asked})",
      any('Skip them' in labels for labels in _la_asked)
      and app.find_note(9601)['body'] == 'second words'
      and sum(1 for n in app.notes if n.get('title') == 'Look alike') == 1)
app.notes = [n for n in app.notes if n.get('id') not in (9601, 9602)]
# A known note answered "Add it as a new note" is not asked about again as a
# look-alike: differing only in its colour, it was, and the default Cancel
# undid the Add unsaid.
def _la_add(*a, **k):
    labels = [label for label, _v in k.get('buttons') or []]
    _la_asked.append(labels)
    return ('add' if any('new note' in label for label in labels)
            else 'skip' if any(label.startswith('Skip') for label in labels) else 'cancel')


_la_ways = {}
for _la_way, _la_code in (('one note', [{'uid': 'la-add', 'title': 'Paint', 'body': 'walls', 'color': '#e57373'}]),
                          ('a batch', [{'uid': 'la-add', 'title': 'Paint', 'body': 'walls', 'color': '#e57373'},
                                       {'title': 'Fresh', 'body': 'brand new'}])):
    app.notes = [n for n in app.notes if n.get('title') not in ('Paint', 'Fresh')]
    app.notes.append(NO.normalize_note({'id': 9603, 'uid': 'la-add', 'title': 'Paint', 'body': 'walls'}))
    app.save_notes(); app.new_note(); app.update()
    _la_asked = []
    app._themed_dialog = _la_add
    if not app._is_placed(app.import_panel):
        app.toggle_import_panel(); app.update()
    app.import_box.delete('1.0', 'end')
    app.import_box.insert('1.0', NO.encode_share_code(_la_code))
    app._do_inline_import()
    app.update()
    app._themed_dialog = _real_dlg_id
    # One note opens in the editor, a new note its first save makes.
    app._autosave_now(); app.update()
    _la_ways[_la_way] = (_la_asked, sum(1 for n in app.notes if n.get('title') == 'Paint'),
                         sum(1 for n in app.notes if n.get('title') == 'Fresh'))
check(f"a known note added as a new one is not asked about again as a look-alike ({_la_ways})",
      _la_ways['one note'][0:2] == ([['Cancel', 'Add as a new note', 'Update this note']], 2)
      and len(_la_ways['a batch'][0]) == 1 and _la_ways['a batch'][1:] == (2, 1))
# ...but as a look-alike of a copy added before, it is: the same code added
# twice made a second copy unasked.
app.notes = [n for n in app.notes if n.get('title') not in ('Paint', 'Fresh')]
app.notes.append(NO.normalize_note({'id': 9603, 'uid': 'la-add', 'title': 'Paint', 'body': 'walls'}))
app.notes.append(NO.normalize_note({'id': 9677, 'title': 'Paint', 'body': 'walls', 'color': '#e57373'}))
app.save_notes(); app.new_note(); app.update()
_la_asked = []
app._themed_dialog = _la_add
if not app._is_placed(app.import_panel):
    app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', NO.encode_share_code(
    [{'uid': 'la-add', 'title': 'Paint', 'body': 'walls', 'color': '#e57373'}]))
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id
check(f"...but as a look-alike of a copy added before, it is ({_la_asked})",
      _la_asked == [['Cancel', 'Add as a new note', 'Update this note'], ['Cancel', 'Add it anyway']]
      and sum(1 for n in app.notes if n.get('title') == 'Paint') == 2)
# "Added 1 note", not "Added 1 notes": one fresh note in, one look-alike skipped.
app.notes = [n for n in app.notes if n.get('title') not in ('Paint', 'Fresh')]
app.notes.append(NO.normalize_note({'id': 9604, 'title': 'Paint', 'body': 'walls'}))
app.save_notes(); app.new_note(); app.update()
_la_asked = []
app._themed_dialog = _la_add
if not app._is_placed(app.import_panel):
    app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', NO.encode_share_code([{'title': 'Paint', 'body': 'walls'},
                                                   {'title': 'Solo', 'body': 'only this'}]))
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id
_la_said = str(app.import_status.cget('text'))
check(f"...and one note added is said as one note ({_la_said!r})",
      _la_said.startswith('Added 1 note ✓') and 'Added 1 notes' not in _la_said)
# A Cancel at the code's question says so, the last import's "Added …" no
# longer under the new code.
_la_id = max((n['id'] for n in app.notes), default=0) + 1     # an id no note holds
app.notes.append(NO.normalize_note({'id': _la_id, 'uid': 'la-cancel', 'title': 'Fence', 'body': 'paint it'}))
app.save_notes()
app._themed_dialog = lambda *a, **k: 'cancel'
if not app._is_placed(app.import_panel):
    app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', NO.encode_share_code([{'uid': 'la-cancel', 'title': 'Fence', 'body': 'paint it green'}]))
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id
_la_cancel = str(app.import_status.cget('text'))
_la_fence = [(n.get('id'), n.get('body')) for n in app.notes if n.get('title') == 'Fence']
check(f"a Cancel at a code's question says nothing was imported ({_la_cancel!r}, {_la_fence})",
      _la_cancel == 'Nothing was imported.' and _la_fence == [(_la_id, 'paint it')])
app.notes = [n for n in app.notes if n.get('title') != 'Fence']
app.notes = [n for n in app.notes if n.get('title') not in ('Paint', 'Fresh', 'Solo')]
app.save_notes()
app.save_notes()

# A note saved while the code's question waited -- a backup's merge, a new
# note's autosave -- took the id the import had counted before it asked, and
# two notes wore one id: opening one wrote over the other.
_ni_keep = list(app.notes)
app.notes = [NO.normalize_note({'id': 9701, 'title': 'Here already', 'body': 'same words'})]
app.save_notes()


def _ni_answer(*a, **k):
    labels = [label for label, _v in k.get('buttons') or []]
    if any(label.startswith('Skip') for label in labels):
        app.notes.append(NO.normalize_note({'id': max(n['id'] for n in app.notes) + 1,
                                            'title': 'Saved meanwhile', 'body': 'x'}))
        return 'skip'
    return 'cancel'


app._themed_dialog = _ni_answer
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', NO.encode_share_code([
    {'title': 'Here already', 'body': 'same words'}, {'title': 'Arrived', 'body': 'fresh'}]))
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id
_ni_ids = [n['id'] for n in app.notes]
check(f"a note saved while a code's question waits keeps its own id ({_ni_ids})",
      len(_ni_ids) == 3 and len(set(_ni_ids)) == 3)
# ...and a backup's merge waits for a question already open, rather than
# running inside it.
_pi_merged = []
app._merge_finished_import = lambda state: _pi_merged.append(state)
try:
    app._import_state = {'phase': 'copying', 'total': 1, 'current': 1, 'done': True}
    app._modal_depth = 1
    app._poll_import_progress()
    _pi_waited = not _pi_merged and app._import_state is not None
    _pi_said = str(app.export_progress_lbl.cget('text'))
    app._modal_depth = 0
    if _pi_waited:   # the wait re-armed the poll; merged at once, nothing was
        app.after_cancel(app._export_poll_job)
    app._poll_import_progress()
finally:
    app.__dict__.pop('_merge_finished_import', None)
    app._modal_depth = 0
    app._import_state = None
check(f"a backup's merge waits while a question is open, then runs ({_pi_waited}, {len(_pi_merged)})",
      _pi_waited and len(_pi_merged) == 1)
# ...and its bar says it waits, not "0 / 1 attachments".
check(f"a backup's merge waiting on a question says so ({_pi_said!r})", 'waiting' in _pi_said)
# ...and it waits for a file chooser or a posted menu as well: under one, its
# questions opened behind the chooser.
_pi_merged = []
app._merge_finished_import = lambda state: _pi_merged.append(state)
try:
    app._import_state = {'phase': 'copying', 'total': 1, 'current': 1, 'done': True}
    app._while_native(app._poll_import_progress)
    _pi_waited = not _pi_merged and app._import_state is not None
    if _pi_waited:
        app.after_cancel(app._export_poll_job)
    app._poll_import_progress()
finally:
    app.__dict__.pop('_merge_finished_import', None)
    app._import_state = None
check(f"a backup's merge waits while a file chooser or a menu is up, then runs ({_pi_waited}, {len(_pi_merged)})",
      _pi_waited and len(_pi_merged) == 1 and not getattr(app, '_natives_open', 0))
# A restore whose save fails takes back exactly the notes it brought: a new
# note's autosave inside the error's wait came after them, and a cut by count
# threw it away.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Kept here', 'body': 'k'}),
             NO.normalize_note({'id': 2, 'title': 'Sent away', 'body': 's'})]
app.trash = []
app.save_notes(); NO.save_trash(app.trash)
app._delete_note(app.find_note(2), None); app.update()   # asked yes: line 26
_rb_new = NO.normalize_note({'id': 9, 'title': 'Typed meanwhile', 'body': 'x'})
# The autosave inside the wait writes the file, the restored note in it.
app.save_notes = lambda *a, **k: (app.notes.append(_rb_new), NO.core_save_notes(app.notes), False)[2]
try:
    _rb_back = app._restore_trash_entries(list(app.trash))
finally:
    app.__dict__.pop('save_notes', None)
with open(NO.DATA_FILE, encoding='utf-8') as _rb_fh:
    _rb_file = [n.get('title') for n in json.load(_rb_fh)]
check(f"a restore whose save fails keeps a note saved meanwhile "
      f"({_rb_back}, {[n.get('title') for n in app.notes]})",
      _rb_back is None and any(n is _rb_new for n in app.notes)
      and not any(n.get('title') == 'Sent away' for n in app.notes))
# ...and the file is put back as well: written inside the wait, the note stood
# in the list and in the Trash at the next start.
check(f"a restore whose save fails leaves the notes file without it ({_rb_file})",
      'Sent away' not in _rb_file and 'Typed meanwhile' in _rb_file)
app.notes = _ni_keep
app.save_notes()

# The other answer. "Add as a new note" must land a SECOND note -- and
# strip the identity on the way, or the two would be one note wearing two
# ids, which is the collision the whole field exists to prevent.
app.open_blank_tab()
app.update()
_again = NO.encode_share_code([{
    'uid': _sent_uid, 'title': 'Departed', 'body': 'another version',
    'formatting': [], 'paragraphs': [], 'comments': '',
    'category': 'General', 'date': '', 'color': '', 'checklist': [],
}])
_real_dlg_id = app._themed_dialog
app._themed_dialog = lambda *a, **k: 'add'
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _again)
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_id

# A single imported note opens in the editor UNSAVED, by design -- the
# user reviews it, then saves. The promise lands at the save, so the
# check follows it there.
#
# Which note the editor holds, not whether a save has happened yet: the
# autosave that follows an import (_open_imported_note_in_editor says
# so) can create the copy inside the update() above on a loaded machine,
# and "selected_note_id is None" then went red with nothing wrong --
# seen during a mutant run, reproduced by pausing past the debounce.
# Either answer keeps the promise: unsaved, or saved as a note of its
# own holding the copy's text; never the old note.
_add_sel = app.capture_editor_state().get('selected_note_id')
check('choosing Add opens the copy as a NEW note, not over the old one',
      _add_sel != _ident_note['id']
      and (_add_sel is None
           or (app.find_note(_add_sel) or {}).get('body', '').rstrip('\n')
           == 'another version'))
app.save_current_note(auto=False)
app.update()
check('...and once saved it is a second note',
      len(app.notes) == _ident_base + 2)
check('...with an identity of its OWN',
      len(app.notes) >= 2 and app.notes[-1]['uid'] != _sent_uid)

del app.notes[_ident_base:]
app.save_notes()
app.open_blank_tab()
app.update()

# A code carrying SEVERAL notes takes the bulk route, which appends
# straight into the notebook instead of opening an editor. "Add" there
# must strip the arriving identity itself -- normalize_note keeps a uid
# it is handed, so two notes would end up wearing one.
app.open_blank_tab()
app.update()
_bulk_base = len(app.notes)
app.notes.append(NO.normalize_note({'id': 9002, 'title': 'Lot',
                                    'body': 'text original'}))
app.save_notes()
_bulk_uid = app.notes[-1]['uid']
_bulk_code = NO.encode_share_code([
    {'uid': _bulk_uid, 'title': 'Batch', 'body': 'edited carelessly',
     'formatting': [], 'paragraphs': [], 'comments': '',
     'category': 'General', 'date': '', 'color': '', 'checklist': []},
    {'title': 'AllNew', 'body': 'zzz', 'formatting': [],
     'paragraphs': [], 'comments': '', 'category': 'General',
     'date': '', 'color': '', 'checklist': []},
])
_real_dlg_b = app._themed_dialog
app._themed_dialog = lambda *a, **k: 'add'
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _bulk_code)
app._do_inline_import()
app.update()
app._themed_dialog = _real_dlg_b

check('a bulk Add brings in both notes',
      len(app.notes) == _bulk_base + 3)
_bulk_uids = [n['uid'] for n in app.notes[_bulk_base:]]
check('...and every one of them has its own identity',
      len(set(_bulk_uids)) == len(_bulk_uids))

del app.notes[_bulk_base:]
app.save_notes()
app.open_blank_tab()
app.update()

# A code holding notes exactly as they are here: whether to add them again
# is asked (field pass), Skip being the answer that changes nothing -- and
# a copy asked for meets no look-alike question after it.
_uc_base = len(app.notes)
app.notes.append(NO.normalize_note({'id': 9003, 'title': 'Same', 'body': 'same text'}))
app.notes.append(NO.normalize_note({'id': 9004, 'title': 'Twin', 'body': 'twin text'}))
app.save_notes()
_uc_one = NO.encode_share_code([app.notes[-2]])
_uc_two = NO.encode_share_code(app.notes[-2:])
_uc_seen = {}
_real_dlg_uc = app._themed_dialog
for _uc_name, _uc_code, _uc_answer in (('one, skipped', _uc_one, 'skip'),
                                       ('one, copied', _uc_one, 'copies'),
                                       ('two, skipped', _uc_two, 'skip'),
                                       ('two, copied', _uc_two, 'copies')):
    _uc_asked = []
    app._themed_dialog = lambda *a, _w=_uc_answer, **k: (_uc_asked.append(a[0]), _w)[1]
    app.open_blank_tab(); app.update()
    _uc_before = len(app.notes)
    app.import_box.delete('1.0', 'end')
    app.import_box.insert('1.0', _uc_code)
    app._do_inline_import()
    app.update()
    app._themed_dialog = _real_dlg_uc
    if _uc_name == 'one, copied':
        # A single note opens for review, unsaved; the save makes it a note.
        _uc_review = app.title_entry.get()
        app.save_current_note(auto=False); app.update()
        _uc_seen[_uc_name] = (_uc_asked, len(app.notes) - _uc_before, _uc_review)
    else:
        _uc_seen[_uc_name] = (_uc_asked, len(app.notes) - _uc_before,
                              str(app.import_status.cget('text')))
app._themed_dialog = _real_dlg_uc
_uc_uids = [n['uid'] for n in app.notes[_uc_base:]]
check(f'a code holding notes exactly as they are here asks once, Skip adds '
      f'nothing, and a copy is a note of its own ({_uc_seen})',
      _uc_seen['one, skipped'][:2] == (['Already here, unchanged'], 0)
      and 'already here' in _uc_seen['one, skipped'][2]
      and _uc_seen['one, copied'][:2] == (['Already here, unchanged'], 1)
      and _uc_seen['one, copied'][2] == 'Same'
      and _uc_seen['two, skipped'][:2] == (['Already here, unchanged'], 0)
      and _uc_seen['two, copied'][:2] == (['Already here, unchanged'], 2)
      and len(set(_uc_uids)) == len(_uc_uids))
del app.notes[_uc_base:]
app.save_notes()
app.open_blank_tab()
app.update()


# ---- A TABLE THROUGH A SHARE CODE, END TO END ----
# Not just the text: the separator's hand-set column width and the
# table's place on the page (paragraphs) must arrive AND render -- the
# imported note opens with a real grid built from them.
_tbl_code = NO.encode_share_code([{
    'title': 'TableViaCode',
    'body': '| Head | G |\n| :-------------: | --- |\n| one | two |',
    'formatting': [],
    'paragraphs': [{'line': 0, 'align': 'center'},
                   {'line': 1, 'align': 'center'},
                   {'line': 2, 'align': 'center'}],
    'comments': '', 'category': 'General', 'date': '', 'color': '',
    'recurrence': {},
}])
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _tbl_code)
# A single-note code opens straight in the EDITOR (unsaved), it is not
# added to the list -- the check follows the real flow.
app._do_inline_import()
app.update()
check('the table note opens in the editor from the code',
      app.title_entry.get() == 'TableViaCode')
_g3 = app._grid_at_line(1)
from noteorganizer.core import tables as _ct
_sep3 = (_ct.parse_separator(app.body_text.get('2.0', '2.end'))
         if _g3 is not None else [])
check('and opens as a drawn grid, data rows only',
      _g3 is not None and _g3['data_rows'] == 2 and _g3['ncols'] == 2)
check(f'with the hand-set column width intact '
      f'(W={_sep3[0]["width"] if _sep3 else None})',
      bool(_sep3) and _sep3[0]['width'] == 15)
check('and its place on the page still centred',
      app._grid_table_align_of(1) == 'center')

# ---- IMPORT CODE: single-note duplicate detection (the exact scenario a
# user found by hand: copying a code from a note you already have, then
# re-importing it, used to silently open it for editing with no warning) ----
single_dup_code = NO.encode_share_code([
    {'title':'ShareMe','body':'share body','comments':'','category':'General','date':'','color':'','recurrence':{}}
])
app.open_blank_tab()  # a clean, properly-flushed editor state before each import attempt —
app.update()          # directly clearing title_entry instead risked corrupting/flushing
                       # whatever note was previously open in the editor
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', single_dup_code)
app.wait_variable = lambda var: click_dialog_button(app, 'Cancel')
app._do_inline_import()
app.update()
check('single-note import warns on an exact duplicate and Cancel skips it',
      app.title_entry.get() != 'ShareMe')

app.open_blank_tab()
app.update()
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', single_dup_code)
app.wait_variable = lambda var: click_dialog_button(app, 'Add it anyway')
_sd_before = len(app.notes)
app._do_inline_import()
app.update()
check('single-note import allows opening the duplicate anyway if chosen',
      app.title_entry.get() == 'ShareMe')
# The button says Add, since the note is saved at once: "Open it anyway"
# read as a look, and a second copy was in the list.
app._autosave_now()
app.update()
check(f'...and "Add it anyway" adds it, as its word says ({_sd_before} -> {len(app.notes)})',
      len(app.notes) == _sd_before + 1)

# a genuinely fresh single note still opens directly, no dialog needed
fresh_single_code = NO.encode_share_code([
    {'title':'GenuinelyFresh','body':'zzz','comments':'','category':'General','date':'','color':'','recurrence':{}}
])
app.open_blank_tab()
app.update()
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', fresh_single_code)
app._do_inline_import()
app.update()
check('single-note import with no duplicate opens directly, no dialog needed',
      app.title_entry.get() == 'GenuinelyFresh')

# Clean editor state before the tests that follow, so nothing left over here
# leaks into them the same way.
app.open_blank_tab()
app.update()

# ---- EXPORT: background thread, non-blocking ----
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
for i in range(15):
    with open(os.path.join(NO.ATTACHMENTS_DIR, f'qa3_att{i}.bin'), 'wb') as f:
        f.write(b'x'*200000)  # enough real work that the progress bar is observable
zip_path = os.path.join(tempfile.gettempdir(), 'qa3_export.zip')
# The system temp dir outlives runs: a zip left by a PREVIOUS qa3 run
# made "export produced a real zip file" pass even when this export
# never moved its file into place. Fresh target, every time.
if os.path.exists(zip_path):
    os.remove(zip_path)
fd.asksaveasfilename = lambda **k: zip_path
# Whether the app SHOWED the panel, recorded at the call: export_data()
# polls once on its way out, and a worker done by then hides the panel
# again before any reading after it -- the race that broke the import
# below on a fast runner, which the 3 MB above only made unlikely here.
_ep_shown = []
_ep_place = app.export_progress_frame.place
app.export_progress_frame.place = lambda *a, **k: (_ep_shown.append(True),
                                                   _ep_place(*a, **k))[1]
app.export_data()
del app.export_progress_frame.place
app.update()
panel_visible_at_start = bool(_ep_shown)
t0=time.time()
interactions=0
while app._export_state is not None and time.time()-t0 < 5:
    app.update()
    interactions+=1
check('export progress bar appears', panel_visible_at_start)
check('export completes on its own', app._export_state is None)
check('export produced a real zip file', os.path.exists(zip_path))
check('progress bar hides after export completes', not app.export_progress_frame.winfo_ismapped())

# ---- IMPORT (zip, threaded) with duplicate detection ----
backup_notes = [
    {'title':'FreshOne','body':'fresh body','comments':'','category':'General','date':'','color':'','recurrence':{}},  # dup of what we have
    {'title':'BrandNewImport','body':'zzz','comments':'','category':'General','date':'','color':'','recurrence':{}},
]
backup_dir = tempfile.mkdtemp()
with open(os.path.join(backup_dir,'notes_data.json'),'w') as f:
    json.dump(backup_notes, f)
import_zip_path = os.path.join(tempfile.gettempdir(), 'qa3_import.zip')
with zipfile.ZipFile(import_zip_path,'w') as zf:
    zf.write(os.path.join(backup_dir,'notes_data.json'), 'notes_data.json')
fd.askopenfilename = lambda **k: import_zip_path

app.wait_variable = lambda var: click_dialog_button(app, 'Skip the duplicate')
before2 = len(app.notes)
app.import_data()
t0=time.time()
while app._import_state is not None and time.time()-t0 < 5:
    app.update()
app.update()
check('threaded zip import completes', app._import_state is None)
check('zip import with skip adds only the fresh note',
      len(app.notes)==before2+1 and any(n['title']=='BrandNewImport' for n in app.notes))

# ---- EXPORT is atomic: a failed export never destroys the old backup ----
# (audit Z05-F00) The zip used to be opened ON the target, so a mid-write
# failure — or the app dying — truncated the very backup being replaced.
# Now it writes save_path+".tmp" and moves it into place only when whole.
app.show_error = lambda *a, **k: True  # the failed export reports; don't block
_atomic_zip = os.path.join(tempfile.gettempdir(), 'qa3_atomic.zip')
with open(_atomic_zip, 'wb') as f:
    f.write(b'OLD-BACKUP-BYTES')
class _FailingZip(zipfile.ZipFile):
    def write(self, *a, **k):
        raise IOError('disk exploded (test)')
_real_zipfile_cls = NO.zipfile.ZipFile
NO.zipfile.ZipFile = _FailingZip
fd.asksaveasfilename = lambda **k: _atomic_zip
try:
    app.export_data()
    t0 = time.time()
    while app._export_state is not None and time.time() - t0 < 120:
        app.update()
finally:
    NO.zipfile.ZipFile = _real_zipfile_cls
check('a failed export leaves the existing backup byte-identical',
      open(_atomic_zip, 'rb').read() == b'OLD-BACKUP-BYTES')
check('and leaves no .tmp litter behind',
      not os.path.exists(_atomic_zip + '.tmp'))
if os.path.exists(_atomic_zip):
    os.remove(_atomic_zip)

# A backup the import would refuse is not put in place: the export asks what
# it wrote by the import's own rules. Here, an attachment shaped like a zip
# bomb, with the threshold brought down to a size a test can write.
from noteorganizer.core import sharing as _qa3_sharing
_self_zip = os.path.join(tempfile.gettempdir(), 'qa3_selfcheck.zip')
with open(_self_zip, 'wb') as f:
    f.write(b'OLD-BACKUP-BYTES')
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
_zeros = os.path.join(NO.ATTACHMENTS_DIR, 'qa3_zeros.bin')
with open(_zeros, 'wb') as f:
    f.write(b'\0' * 3_000_000)
_self_errors = []
_kept_show_error = app.show_error
app.show_error = lambda *a, **k: (_self_errors.append(' '.join(map(str, a))), True)[1]
_kept_min = _qa3_sharing.BOMB_MIN_BYTES
fd.asksaveasfilename = lambda **k: _self_zip
try:
    _qa3_sharing.BOMB_MIN_BYTES = 1_000_000
    app.export_data()
    t0 = time.time()
    while app._export_state is not None and time.time() - t0 < 120:
        app.update()
finally:
    _qa3_sharing.BOMB_MIN_BYTES = _kept_min
    app.show_error = _kept_show_error
    os.remove(_zeros)
check(f'a backup its own import would refuse is not put in place, and the '
      f'export says why ({[e[:90] for e in _self_errors]})',
      open(_self_zip, 'rb').read() == b'OLD-BACKUP-BYTES'
      and not os.path.exists(_self_zip + '.tmp')
      and any('would not import back' in e and 'qa3_zeros.bin' in e
              for e in _self_errors))
os.remove(_self_zip)

# The single-note export is the same class (it wrote straight onto the
# chosen file): a write failure must leave the existing file intact.
_se_path = os.path.join(tempfile.gettempdir(), 'qa3_single.txt')
with open(_se_path, 'w', encoding='utf-8') as f:
    f.write('OLD-NOTE')
_builtin_open = open
def _fail_write_open(p, mode='r', *a, **k):
    if isinstance(p, str) and p.startswith(_se_path) and 'w' in str(mode):
        # Open for real first — a genuine 'w' open TRUNCATES the target
        # before any write, which is exactly the damage the tmp protocol
        # exists to keep away from the user's file. A fake handle that
        # never touched the disk let the direct-write mutant survive.
        _fh = _builtin_open(p, mode, *a, **k)
        class _FW:
            def __enter__(s): return s
            def __exit__(s, *e):
                _fh.close()
                return False
            def write(s, d): raise IOError('disk exploded (test)')
        return _FW()
    return _builtin_open(p, mode, *a, **k)
fd.asksaveasfilename = lambda **k: _se_path
NO.open = _fail_write_open
try:
    app.export_note_as_file(app.notes[0], 'txt')
finally:
    del NO.open
check('a failed single-note export leaves the existing file intact',
      open(_se_path, encoding='utf-8').read() == 'OLD-NOTE'
      and not os.path.exists(_se_path + '.tmp'))
os.remove(_se_path)
app.show_error = NO.NoteOrganizer.show_error.__get__(app)  # restore the real one

# ---- CLOSE waits for an in-flight worker (audit Z05-F01) ----
# destroy() used to kill a daemon export/import thread mid-file. The app
# now remembers its I/O workers and on_app_close waits (capped) for them.
# Both checks use the DEFAULT cap on purpose: passing an explicit cap
# here let a mutant gut the default (cap_s=0) — "closing waits" fully
# broken — while the checks stayed green.
_slow_done = {'flag': False}
def _slow_worker():
    time.sleep(0.6)
    _slow_done['flag'] = True
app._start_io_worker(_slow_worker)
app._wait_for_io_workers()
check('the close-time wait lets an in-flight I/O worker finish',
      _slow_done['flag'])

# End-to-end: the REAL on_app_close (destroy stubbed) must let a live
# worker finish — this also fails if the call site shrinks the cap.
_slow_done2 = {'flag': False}
def _slow_worker2():
    time.sleep(0.6)
    _slow_done2['flag'] = True
_real_destroy3 = app.destroy
app.destroy = lambda: None
try:
    app._start_io_worker(_slow_worker2)
    app.on_app_close()
finally:
    app.destroy = _real_destroy3
check('on_app_close itself waits for an in-flight worker before destroy',
      _slow_done2['flag'])

# ---- The write-failure callback reaches the SCREEN (audit Z01-F06) ----
# The core half (return + crash log + callback) lives in
# test_data_safety; this is the UI half: the app registers the callback
# at startup and a failure shows the error toast naming the file.
from noteorganizer.core import storage as _st3
check('the app registers core storage\'s write-failure callback',
      _st3.on_write_failure is not None)
if _st3.on_write_failure is not None:
    _st3.on_write_failure(os.path.join('x', 'trash.json'), OSError('disk full'))
    t0 = time.time()
    while time.time() - t0 < 2:
        app.update()
        if 'trash.json' in str(app.toast_lbl.cget('text')):
            break
    check('a failed write shows the toast naming the file',
          'trash.json' in str(app.toast_lbl.cget('text')))

# ---- The backup carries the WHOLE notebook (audit Z05-F07) ----
# templates.json and trash.json were silently left out of the export and
# never read on import — moving devices lost both. Full round-trip:
# export with a template and a trashed note, wipe them locally, import,
# and both come back (additively — nothing local replaced).
app.templates.append(NO.normalize_template(
    {'name': 'RoundTripTpl', 'title': 'T', 'body': 'tpl body'}))
NO.save_templates(app.templates)
# Deleted of late: one older than the 30 days the next start keeps stays in the backup.
app.trash.append({'id': 900, 'title': 'TrashedRT', 'body': 'rt',
                  'category': 'General',
                  'deleted_at': time.strftime('%Y-%m-%d %H:%M:%S',
                                              time.localtime(time.time() - 2 * 86400)),
                  'attachments': []})
NO.save_trash(app.trash)
_rt_zip = os.path.join(tempfile.gettempdir(), 'qa3_fullrt.zip')
if os.path.exists(_rt_zip):
    os.remove(_rt_zip)
fd.asksaveasfilename = lambda **k: _rt_zip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()
check('full-notebook export completes', os.path.exists(_rt_zip))
# Wipe the two locally, then import the backup back.
app.templates = [t for t in app.templates if t.get('name') != 'RoundTripTpl']
NO.save_templates(app.templates)
app.trash = [e for e in app.trash if e.get('title') != 'TrashedRT']
NO.save_trash(app.trash)
app.ask_yes_no = lambda *a, **k: True
app._themed_dialog = lambda *a, **k: 'all'
fd.askopenfilename = lambda **k: _rt_zip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
check('the template comes back from the backup',
      any(t.get('name') == 'RoundTripTpl' for t in app.templates))
check('the trashed note comes back from the backup',
      any(e.get('title') == 'TrashedRT' for e in app.trash))
# Re-importing the SAME backup must not double the trash.
_trash_count_rt = len(app.trash)
fd.askopenfilename = lambda **k: _rt_zip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
check('re-importing the same backup does not double the trash',
      len(app.trash) == _trash_count_rt)
os.remove(_rt_zip)

# A CRAFTED backup: trash.json with a non-string deleted_at and an
# attachment pointing at a file an ACTIVE note owns. The entry must
# arrive normalized (the Trash panel's sort crashed on deleted_at=5)
# and with its OWN copy of the file (delete-forever on the import must
# never destroy the active note's attachment).
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
_own_att = '20260202020202020202_own.txt'
with open(os.path.join(NO.ATTACHMENTS_DIR, _own_att), 'w') as f:
    f.write('mine')
# The file's owner is a LOCAL TRASH entry — the exact hole the review
# found: claimed was built from active notes only, so an imported twin
# shared a trashed note's file and delete-forever on either destroyed
# the other's attachment.
app.trash.append({'id': 951, 'title': 'TrashOwner', 'body': 'to',
                  'category': 'General',
                  'deleted_at': '2026-01-02 00:00:00',
                  'attachments': [{'filename': 'own.txt',
                                   'stored_as': _own_att}]})
NO.save_trash(app.trash)
_cz = os.path.join(tempfile.gettempdir(), 'qa3_crafted_trash.zip')
with zipfile.ZipFile(_cz, 'w') as zf:
    zf.writestr('notes_data.json', '[]')
    zf.writestr('trash.json', json.dumps([
        {'id': 1, 'title': 'ForeignTrash', 'body': 'ft',
         'category': 'General', 'deleted_at': 5,
         'attachments': [{'filename': 'own.txt',
                          'stored_as': _own_att}]}]))
    zf.writestr('attachments/' + _own_att, 'mine')
fd.askopenfilename = lambda **k: _cz
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
_ft = next((e for e in app.trash if e.get('title') == 'ForeignTrash'), None)
check('a foreign trash entry arrives normalized (deleted_at is a str)',
      _ft is not None and isinstance(_ft.get('deleted_at'), str))
check('an imported trash attachment never shares a LOCAL TRASH file',
      _ft is not None and _ft.get('attachments')
      and _ft['attachments'][0]['stored_as'] != _own_att
      and os.path.isfile(os.path.join(
          NO.ATTACHMENTS_DIR, _ft['attachments'][0]['stored_as'])))
os.remove(_cz)

# A sound backup with no room for it on a nearly full disk: said as that
# alone. It opened with "That file couldn't be read as a backup".
_nr_zip = os.path.join(tempfile.gettempdir(), 'qa3_no_room.zip')
with zipfile.ZipFile(_nr_zip, 'w') as zf:
    zf.writestr('notes_data.json', '[]')
_nr_said, _nr_err_was, _nr_unpack_was = [], app.show_error, NO._safe_extract_zip


def _nr_no_room(*_a, **_k):
    raise NO.BackupRefused("There isn't enough free space to import this backup: it needs about 9 GB.")


app.show_error = lambda *a, **k: _nr_said.append(' '.join(map(str, a)))
NO._safe_extract_zip = _nr_no_room
fd.askopenfilename = lambda **k: _nr_zip
try:
    app.import_data()
    t0 = time.time()
    while app._import_state is not None and time.time() - t0 < 30:
        app.update()
finally:
    NO._safe_extract_zip = _nr_unpack_was
    app.show_error = _nr_err_was
os.remove(_nr_zip)
check(f"a sound backup with no room for it is said as that alone, not as a file that could not be read "
      f"({_nr_said!r})",
      any('enough free space' in s for s in _nr_said) and not any("couldn't be read" in s for s in _nr_said))
# The disk filling up during the unpacking: said as that, and a damaged
# stream (zlib.error) as a file that could not be read, not "unexpectedly".
_nr_seen = {}
for _nr_name, _nr_raise in (('full', OSError(errno.ENOSPC, 'No space left on device')),
                            ('stream', zlib.error('Error -3 while decompressing data'))):
    with zipfile.ZipFile(_nr_zip, 'w') as zf:
        zf.writestr('notes_data.json', '[]')
    _nr_said.clear()

    def _nr_fails(*_a, _e=_nr_raise, **_k):
        raise _e
    app.show_error = lambda *a, **k: _nr_said.append(' '.join(map(str, a)))
    NO._safe_extract_zip = _nr_fails
    try:
        app.import_data()
        t0 = time.time()
        while app._import_state is not None and time.time() - t0 < 30:
            app.update()
    finally:
        NO._safe_extract_zip = _nr_unpack_was
        app.show_error = _nr_err_was
    os.remove(_nr_zip)
    _nr_seen[_nr_name] = ' '.join(_nr_said)
check(f"a disk that fills up while a backup unpacks is said as that ({_nr_seen.get('full', '')[:120]!r})",
      'disk filled up' in _nr_seen.get('full', '') and "couldn't be read" not in _nr_seen.get('full', ''))
check(f"...and a damaged stream as a file that could not be read, not as unexpected "
      f"({_nr_seen.get('stream', '')[:120]!r})",
      "couldn't be read as a backup" in _nr_seen.get('stream', '')
      and 'unexpectedly' not in _nr_seen.get('stream', ''))

# A CRAFTED backup's settings.json: a million day colours under keys that are
# no dates, and markers 100,000 characters long. Adopted whole, every note
# then took three seconds to open -- each open rewrote the 62 MB file -- and
# restart took twenty, for good (2026-10-28). Real days only, as the
# calendar writes them, markers as the picker makes them, and at most
# MAX_DAY_DECORATIONS of each.
_dc_before = dict(app.day_colors)
_de_before = dict(app.day_emoji)
_dz = os.path.join(tempfile.gettempdir(), 'qa3_day_decor.zip')
_dz_colors = {'not-a-date-%06d' % i: '#ff0000' for i in range(30000)}
_dz_colors.update({'2031-%02d-%02d' % (m, d): '#00aa00'
                   for m in range(1, 13) for d in range(1, 29)})
_dz_colors.update({'2031-1-5': '#00aa00', ' 2031-02-02': '#00aa00'})
_dz_marks = {'2031-03-03': ['⭐' * 100000, '\U0001F382'],
             '2031-03-04': ['\U0001F382']}
with zipfile.ZipFile(_dz, 'w') as zf:
    zf.writestr('notes_data.json', '[]')
    zf.writestr('settings.json', json.dumps({'day_colors': _dz_colors,
                                             'day_emoji': _dz_marks}))
fd.askopenfilename = lambda **k: _dz
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
_dz_new = {d: c for d, c in app.day_colors.items() if d not in _dc_before}
check(f'a backup\'s day colours come in for real days only '
      f'({len(_dz_new)} of {len(_dz_colors):,})',
      len(_dz_new) == 12 * 28
      and all(NO.parse_date(d) and len(d) == 10 for d in app.day_colors))
check(f'...and its markers as the picker makes them '
      f'({app.day_emoji.get("2031-03-03")})',
      app.day_emoji.get('2031-03-03') == ['\U0001F382']
      and app.day_emoji.get('2031-03-04') == ['\U0001F382'])
_dz_saved = NO.load_settings()
check('...and the settings file keeps what was kept, not what came',
      len(_dz_saved.get('day_colors') or {}) == len(app.day_colors)
      and os.path.getsize(NO.SETTINGS_FILE) < 1_000_000)
# Past the ceiling, a backup's days stop coming in and this device's stay.
import datetime as _dzdt
_dz_many = {(_dzdt.date(1900, 1, 1) + _dzdt.timedelta(days=i)).isoformat(): '#0000aa'
            for i in range(NO.MAX_DAY_DECORATIONS)}
with zipfile.ZipFile(_dz, 'w') as zf:
    zf.writestr('notes_data.json', '[]')
    zf.writestr('settings.json', json.dumps({'day_colors': _dz_many}))
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
check(f'a backup carrying more days than the app keeps fills it to '
      f'{NO.MAX_DAY_DECORATIONS:,} and no further ({len(app.day_colors):,})',
      len(app.day_colors) == NO.MAX_DAY_DECORATIONS
      and all(app.day_colors.get(d) == c for d, c in _dz_new.items()))
app.day_colors = dict(_dc_before)
app.day_emoji = dict(_de_before)
NO.save_setting('day_colors', dict(app.day_colors))
NO.save_setting('day_emoji', dict(app.day_emoji))
os.remove(_dz)
# The start reads this device's own file the same way, and writes back
# what it kept: left in the file, every settings write carried it on.
_ds = NO.load_settings()
_ds['day_colors'] = dict(_dz_colors)
_ds['day_emoji'] = dict(_dz_marks)
_ds['collapsed_groups'] = [{'a': 1}, 'General']
NO.save_settings(_ds)
app._load_day_decorations()
_ds_after = NO.load_settings()
check(f'the start keeps real days only and writes back what it kept '
      f'({len(app.day_colors)} colours, {len(_ds_after.get("day_colors") or {})} in the file)',
      len(app.day_colors) == 12 * 28
      and len(_ds_after.get('day_colors') or {}) == 12 * 28
      and app.day_emoji.get('2031-03-03') == ['\U0001F382'])
app.day_colors = dict(_dc_before)
app.day_emoji = dict(_de_before)
NO.save_setting('day_colors', dict(app.day_colors))
NO.save_setting('day_emoji', dict(app.day_emoji))
NO.save_setting('collapsed_groups', [])

# A CRAFTED backup with more templates than anyone keeps: 20,000 in 49 KB
# took fourteen seconds to import -- each name checked against every one
# before it -- and the picker five to open (2026-10-28). The import stops at
# MAX_TEMPLATES, and the doors refuse the next one, so a start never drops one.
_tp_before = list(app.templates)
_tpz = os.path.join(tempfile.gettempdir(), 'qa3_many_templates.zip')
with zipfile.ZipFile(_tpz, 'w') as zf:
    zf.writestr('notes_data.json', '[]')
    zf.writestr('templates.json', json.dumps(
        [{'name': 'Imported %05d' % i, 'body': 'b'}
         for i in range(NO.MAX_TEMPLATES + 500)]))
fd.askopenfilename = lambda **k: _tpz
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
check(f'a backup with more templates than the app keeps fills it to '
      f'{NO.MAX_TEMPLATES:,} and no further ({len(app.templates):,})',
      len(app.templates) == NO.MAX_TEMPLATES
      and all(t in app.templates for t in _tp_before)
      and len(NO.load_templates()) == NO.MAX_TEMPLATES)
_tp_told = []
_tp_real_info = app.show_info
_tp_real_rename = app._show_inline_rename
app.show_info = lambda title, message, **k: _tp_told.append((title, message))
app._show_inline_rename = lambda _anchor, _default, on_name, **_limit: on_name('One too many')
try:
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'Has a title')
    app.save_current_as_template()
    app.update()
finally:
    app.show_info = _tp_real_info
    app._show_inline_rename = _tp_real_rename
check(f'...and saving one more by hand is refused, and that is said '
      f'({[t for t, _m in _tp_told]})',
      len(app.templates) == NO.MAX_TEMPLATES
      and not any(t.get('name') == 'One too many' for t in app.templates)
      and [t for t, _m in _tp_told] == ['Too many templates'])
app.templates = _tp_before
NO.save_templates(app.templates)
os.remove(_tpz)
# ...and one the disk refuses is said not saved: "Saved template" showed.
_ts_real_save = NO.save_templates
NO.save_templates = lambda _t: (False, OSError(28, 'No space left on device'))
app._show_inline_rename = lambda _anchor, _default, on_name, **_limit: on_name('Refused one')
try:
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'Has a title')
    app.save_current_as_template()
    app.update()
    _ts_status = str(app.status_lbl.cget('text'))
    # ...and not listed: kept on screen alone, it was gone at the next start.
    _ts_listed = any(t.get('name') == 'Refused one' for t in app.templates)
finally:
    NO.save_templates, app._show_inline_rename = _ts_real_save, _tp_real_rename
app.templates = _tp_before
NO.save_templates(app.templates)
check(f"a template the disk refuses is said not saved, and not listed ({_ts_status!r}, "
      f"listed {_ts_listed})",
      'not saved' in _ts_status and 'Saved template' not in _ts_status and not _ts_listed)

# ---- SHARE-CODE decode: every refusal branch (coverage-lift C16) ----
# Each malformed-input class must raise ValueError with a HUMAN message
# (the UI shows it verbatim) — never a raw exception, never success.
from noteorganizer.core import sharing as _sh
_bad_inputs = [
    ('not a string', 12345),
    ('empty after whitespace', '  \n  '),
    ('absurd length', 'NOTE1:' + 'A' * (_sh.MAX_SHARE_CODE_CHARS + 1)),
    ('wrong prefix', 'XYZ:abcdef'),
    ('broken base64', 'NOTE1:@@@not-base64@@@'),
    ('valid b64, broken zlib', 'NOTE1:' + __import__('base64').urlsafe_b64encode(b'not zlib data').decode()),
    ('valid zlib, broken json', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{broken')).decode()),
    ('json but no notes key', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{"v":1}')).decode()),
    ('newer version', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{"v":9,"notes":[{}]}')).decode()),
    ('empty notes list', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{"v":1,"notes":[]}')).decode()),
]
_all_refused = True
for _why, _code in _bad_inputs:
    try:
        _sh.decode_share_code(_code)
        _all_refused = False
        print('    (decode ACCEPTED the %s case!)' % _why)
    except ValueError as e:
        if not str(e).strip():
            _all_refused = False
            print('    (%s: empty message)' % _why)
    except Exception as e:
        _all_refused = False
        print('    (%s: raw %s escaped)' % (_why, type(e).__name__))
check('every malformed share code is refused with a human ValueError',
      _all_refused)
_over = {'v': 1, 'notes': [{'title': 'x'}] * (_sh.MAX_SHARED_NOTES + 1)}
_over_code = 'NOTE1:' + __import__('base64').urlsafe_b64encode(
    __import__('zlib').compress(__import__('json').dumps(_over).encode())).decode()
try:
    _sh.decode_share_code(_over_code)
    _cap_ok = False
except ValueError as e:
    _cap_ok = str(_sh.MAX_SHARED_NOTES) in str(e)
check('a code over the note cap names the cap in its refusal', _cap_ok)

# ---- A restored backup keeps its categories (product review T0-3) ----
# settings.json - where the categories live - was always written INTO the
# zip and never read back out, so on a new machine every imported note
# whose category did not exist yet was silently re-filed under "General"
# by normalize_note. The whole filing system of a restored notebook, gone.
NO.CATEGORY_COLORS['Big Projects'] = '#ff8800'
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'The Plan', 'body': 'x',
              'category': 'Big Projects', 'updated': '2026-01-01 00:00',
              'created': '2026-01-01 00:00', 'checklist': [],
              'attachments': []}]
app.save_notes()
# Calendar day decor rides the same settings.json: two valid entries
# and one garbage colour a hand-editor (or hostile zip) could carry.
NO.save_setting('day_colors', {'2026-03-03': '#112233',
                               '2026-03-05': '#zzzzzz'})
# A marker written with the emoji variation selector, as older pickers
# wrote it: Tk draws that character as a gap, so it must come in without.
_VS3 = chr(0xFE0F)
NO.save_setting('day_emoji', {'2026-03-04': ['\u2b50'],
                              '2026-03-06': [chr(0x2764) + _VS3]})
app.day_colors = {'2026-03-03': '#112233'}
app.day_emoji = {'2026-03-04': ['\u2b50'], '2026-03-06': [chr(0x2764) + _VS3]}
_catzip = os.path.join(tempfile.gettempdir(), 'qa3_categories.zip')
if os.path.exists(_catzip):
    os.remove(_catzip)
fd.asksaveasfilename = lambda **k: _catzip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()
check('the backup zip carries settings.json', os.path.exists(_catzip))

# Now become a device that has never heard of that category.
del NO.CATEGORY_COLORS['Big Projects']
NO.persist_categories()
NO.save_setting('day_colors', {})
NO.save_setting('day_emoji', {})
app.day_colors = {}
app.day_emoji = {}
app.notes = []
app.save_notes()
app.ask_yes_no = lambda *a, **k: True
app._themed_dialog = lambda *a, **k: 'all'
fd.askopenfilename = lambda **k: _catzip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
check('importing the backup brings the category back',
      'Big Projects' in NO.CATEGORY_COLORS
      and NO.get_setting('categories', {}).get('Big Projects') == '#ff8800')
check('and the note keeps its filing instead of falling to General',
      any(n.get('category') == 'Big Projects' for n in app.notes))
# The calendar decor is user data the backup has always carried and the
# import used to drop wholesale -- and its colours are as untrusted as
# any other imported value: the garbage one must NOT come back.
check('day colours and markers come back with the backup',
      app.day_colors.get('2026-03-03') == '#112233'
      and app.day_emoji.get('2026-03-04') == ['\u2b50']
      and NO.get_setting('day_colors', {}).get('2026-03-03') == '#112233')
check(f"a marker the backup carries with the variation selector comes back "
      f"without it ({app.day_emoji.get('2026-03-06')!r})",
      app.day_emoji.get('2026-03-06') == [chr(0x2764)])
check('a garbage day colour from the backup is refused at the door',
      '2026-03-05' not in app.day_colors
      and '2026-03-05' not in NO.get_setting('day_colors', {}))
os.remove(_catzip)
NO.CATEGORY_COLORS.pop('Big Projects', None)
NO.persist_categories()
NO.save_setting('day_colors', {})
NO.save_setting('day_emoji', {})
app.day_colors = {}
app.day_emoji = {}

# ---- The category merge runs BEFORE the duplicate scan ----
# The scan normalizes each incoming note, and normalize re-files an
# unknown category to General. Scanned in that state, a distinct note
# read as a duplicate of a local General twin and the import offered to
# skip it -- while the dialog claimed its category matched. With the
# merge first, the same import must sail through with no question.
NO.CATEGORY_COLORS['Order'] = '#123456'
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'Same', 'body': 'y', 'category': 'Order',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
_ordzip = os.path.join(tempfile.gettempdir(), 'qa3_order.zip')
if os.path.exists(_ordzip):
    os.remove(_ordzip)
fd.asksaveasfilename = lambda **k: _ordzip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()
# The amnesiac device again -- but THIS one already owns a General note
# with the identical text, the collision the old order manufactured.
NO.CATEGORY_COLORS.pop('Order', None)
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'Same', 'body': 'y', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
_dlg_asked = []
_real_dlg3 = app._themed_dialog
app._themed_dialog = lambda *a, **k: (_dlg_asked.append(a), 'all')[1]
fd.askopenfilename = lambda **k: _ordzip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
app._themed_dialog = _real_dlg3
check('with categories merged first, the twin is no duplicate: no dialog',
      _dlg_asked == [])
check('and it lands under its own category, alongside the local twin',
      len(app.notes) == 2
      and any(n.get('category') == 'Order' for n in app.notes))
os.remove(_ordzip)
NO.CATEGORY_COLORS.pop('Order', None)
NO.persist_categories()

# ---- An oversized pasted note SAYS it was trimmed ----
# The ceilings truncate silently by design (right for a hostile code,
# wrong for a person), so the import announces it. The announcement was
# dead code: it set a status that _open_imported_note_in_editor
# overwrote one frame later with its own, and a ledger row recorded it
# as shipped. It is passed down now, so the one status line that
# survives carries it.
_big_code = NO.encode_share_code({
    'title': 'Too big', 'body': 'x', 'category': 'General',
    'checklist': [{'text': 'item %d' % i, 'done': False}
                  for i in range(NO.MAX_CHECKLIST_ITEMS + 50)]})
app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _big_code)
_trim_said = []
_real_info_trim = app.show_info
app.show_info = lambda t, m, **k: (_trim_said.append((t, m)), True)[1]
try:
    app._do_inline_import()
    app.update()
finally:
    app.show_info = _real_info_trim
check('an oversized pasted note is trimmed to the ceiling',
      len(app.capture_editor_state().get('checklist', []))
      == NO.MAX_CHECKLIST_ITEMS)
# NOT the status bar: the autosave that follows an import overwrites it
# with "Auto-saved ..." before anyone could read it (measured -- the
# first version of this check caught exactly that).
check('...and the user is TOLD, through a channel nothing overwrites',
      len(_trim_said) == 1 and 'trimmed' in _trim_said[0][1].lower()
      and str(NO.MAX_CHECKLIST_ITEMS) in _trim_said[0][1])
app.new_note(); app.update()

# ---- Cancelling an import cancels the categories too ----
# The category merge has to happen BEFORE the duplicate scan (the scan
# normalizes, and normalize re-files an unknown category to General) --
# but it was also PERSISTED there, so answering "Cancel" at the
# duplicate dialog still left a stranger's categories installed in the
# sidebar and saved to disk, with no note to explain them. The merge is
# provisional now: in memory for the scan, rolled back on cancel, written
# only once the user has agreed.
# The note stays in General on BOTH sides, so it is a genuine duplicate
# and the dialog is guaranteed to appear. The category under test rides
# along in the backup's palette WITHOUT being used by that note -- which
# separates the two things cleanly: the dialog is about the note, the
# rollback is about the category.
NO.CATEGORY_COLORS['Foreign'] = '#abcdef'
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'Double', 'body': 'z', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
_cxzip = os.path.join(tempfile.gettempdir(), 'qa3_cancel.zip')
if os.path.exists(_cxzip):
    os.remove(_cxzip)
fd.asksaveasfilename = lambda **k: _cxzip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()

# A device that never heard of it, but DOES hold the identical note, so
# the duplicate dialog is guaranteed to appear and can be cancelled.
NO.CATEGORY_COLORS.pop('Foreign', None)
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'Double', 'body': 'z', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
_before_cx = len(app.notes)
app._themed_dialog = lambda *a, **k: 'cancel'
fd.askopenfilename = lambda **k: _cxzip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
check('cancelling an import adds no notes', len(app.notes) == _before_cx)
check('and leaves no stranger category in the palette',
      'Foreign' not in NO.CATEGORY_COLORS)
check('...nor on disk',
      'Foreign' not in NO.get_setting('categories', {}))

# Agreeing installs it, which is what makes the check above meaningful.
app._themed_dialog = lambda *a, **k: 'all'
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
check('while agreeing DOES install it (the cancel was the difference)',
      'Foreign' in NO.CATEGORY_COLORS
      and NO.get_setting('categories', {}).get('Foreign') == '#abcdef')
os.remove(_cxzip)
NO.CATEGORY_COLORS.pop('Foreign', None)
NO.persist_categories()
app.notes = []
app.save_notes()

# ---- Share-as-code asks the SHARED content question ----
# The seventh hand-rolled emptiness gate: it enumerated title|body and
# refused a checklist-only or comments-only note with "Write something
# before copying a code" -- about a note the app itself had just saved
# as real content, and whose code would have carried it fine (checklist
# and comments are both in SHAREABLE_FIELDS). It now asks the shared
# predicate with `attachments` masked out, because that one field is
# the only thing a code genuinely cannot carry.


def _share_code_for(setup):
    """Drive the real gesture and return the code it rendered, if any."""
    app.open_blank_tab(); app.update()
    for _w in app.editor_code_area.winfo_children():
        _w.destroy()
    setup()
    app.update()
    app.share_current_note_as_code()
    app.update()
    _found = []

    def _walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Text):
                _txt = c.get('1.0', 'end-1c').strip()
                if _txt:
                    _found.append(_txt)
            _walk(c)
    _walk(app.editor_code_area)
    return _found[0] if _found else None


_sg_list = [{'text': 'milk', 'done': False}, {'text': 'eggs', 'done': True}]
_sg_code = _share_code_for(
    lambda: setattr(app, '_working_checklist', [dict(i) for i in _sg_list]))
check('a checklist-only note can be shared as a code', _sg_code is not None)
check('...and the code really carries the checklist',
      _sg_code is not None
      and NO.decode_share_code(_sg_code)[0].get('checklist') == _sg_list)

_sg_code2 = _share_code_for(
    lambda: app.comments_text.insert('1.0', 'just one comment'))
check('a comments-only note can be shared too',
      _sg_code2 is not None
      and NO.decode_share_code(_sg_code2)[0].get('comments')
      == 'just one comment')

# The guard must keep its teeth: a truly empty editor still refuses, and
# says what a code actually carries instead of "write something".
_sg_status = []
_real_status = app.set_status
app.set_status = lambda m: (_sg_status.append(m), _real_status(m))[1]
try:
    _sg_empty = _share_code_for(lambda: None)
finally:
    app.set_status = _real_status
check('a truly empty editor is still refused', _sg_empty is None)
# The mask earns its keep here and nowhere else: attachments are the one
# thing a code cannot carry, so an attachment-ONLY editor has nothing to
# share even though the shared content test would call it content.
_sg_att = _share_code_for(
    lambda: setattr(app, 'current_attachments',
                    [{'filename': 'x.pdf', 'stored_as': 'x.pdf'}]))
app.current_attachments = []
check('an attachment-only editor is refused: a code cannot carry files',
      _sg_att is None)
check('...with a message that names what a code carries',
      any('checklist' in m for m in _sg_status)
      and not any('Write something' in m for m in _sg_status))
app.open_blank_tab(); app.update()

# ---- A styling bomb, through the editor door it actually arrives by ----
# The pure suite holds the 2,000-span shapes that used to hang Tk; this
# one is deliberately just OVER the ceiling instead, so that removing the
# clamp turns this check red in a third of a second rather than hanging
# the whole run before it can print its footer.
#
# What is witnessed here is the seam the pure suite cannot see: the
# editor reads a note's formatting back OUT of the text widget when it
# saves, so whatever the ceiling does to the data has to survive that
# round trip. The first attempt at this fix skipped the DRAWING instead
# of the data, which would have made the very next save write an empty
# formatting list over the user's styled note.
_lc_body = "x" * 9000
_lc_spans = [{'start': (3 * i) % 8000, 'end': (3 * i) % 8000 + 2,
              'style': 'highlight',
              'value': '#%06x' % (i * 4001 % 0xffffff)}
             for i in range(NO.MAX_SPANS_PER_LINE + 100)]
_lc_note = NO.normalize_note({
    'id': 808080, 'title': 'ceiling', 'body': _lc_body,
    'formatting': _lc_spans, 'category': 'General',
    'created': '2026-01-01 00:00', 'updated': '2026-01-01 00:00'})
check('a note arriving over the per-line ceiling is trimmed to it',
      len(_lc_note['formatting']) == NO.MAX_SPANS_PER_LINE)
app.notes = [n for n in app.notes if n.get('id') != 808080] + [_lc_note]
app.save_notes()
app.load_note(_lc_note)
app.update()
_lc_state = app.capture_editor_state()
check('...it opens, with its whole text present',
      app.body_text.get('1.0', 'end-1c') == _lc_body)
# The round trip, which is the whole reason the ceiling sits in the data
# and not at the draw: what the editor would SAVE right now is what the
# note holds -- neither more nor, far worse, nothing at all.
check('...and what the editor would save back matches what it was given',
      len(_lc_state.get('formatting', [])) == len(_lc_note['formatting']))
_lc_reopened = NO.normalize_note(dict(_lc_note, formatting=_lc_state['formatting']))
check('...so saving and reopening it does not shed its styling',
      len(_lc_reopened['formatting']) == len(_lc_note['formatting']))

# The asymmetry at the gesture: an ordinary styled note is not trimmed
# and still draws its colours.
_ord_spans = [{'start': 3 * i, 'end': 3 * i + 2, 'style': 'highlight',
               'value': '#ffee88'} for i in range(40)]
_ord_note = NO.normalize_note({
    'id': 808081, 'title': 'ordinary', 'body': _lc_body,
    'formatting': [dict(s) for s in _ord_spans], 'category': 'General',
    'created': '2026-01-01 00:00', 'updated': '2026-01-01 00:00'})
check('an ordinary styled note keeps every span it had',
      _ord_note['formatting'] == _ord_spans)
app.notes = [n for n in app.notes if n.get('id') != 808081] + [_ord_note]
app.save_notes()
app.load_note(_ord_note)
app.update()
check('...and the editor really draws them',
      any(t.startswith('highlight_') and app.body_text.tag_ranges(t)
          for t in app.body_text.tag_names()))

app.notes = [n for n in app.notes if n.get('id') not in (808080, 808081)]
app.save_notes()
app.open_blank_tab(); app.update()


# ---- FIELD CASES AUTOMATED (test plan 13, 96, 99, 120) ----
_b4_saved_notes, _b4_saved_trash = list(app.notes), list(app.trash)


def _b4_all_checkbuttons(widget, found=None):
    if found is None:
        found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Checkbutton):
            found.append(child)
        _b4_all_checkbuttons(child, found)
    return found


def _b4_find(widget, label, kind=tk.Button):
    for child in widget.winfo_children():
        if isinstance(child, kind) and label in str(child.cget('text')):
            return child
        found = _b4_find(child, label, kind)
        if found:
            return found
    return None


# 13: deleting one trashed note forever leaves the others alone.
app.notes = []
app.trash = [{'id': 900 + i, 'title': 'Deleted %d' % i, 'body': 'x',
              'category': 'General', 'deleted_at': '2026-01-0%d 00:00:00' % (i + 1)}
             for i in range(3)]
app.save_notes()
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()
_b4_forever = _b4_find(app.settings_trash_panel, 'Delete')
check('a trashed note offers a permanent delete (plan 13)', _b4_forever is not None)
if _b4_forever is not None:
    app.ask_yes_no = lambda *a, **k: True
    _b4_forever.invoke(); app.update()
    check('...and using it removes exactly one, leaving the rest (plan 13)',
          len(app.trash) == 2)
    # The panel lists the most recently deleted first, so the button at
    # the top belongs to the LAST one trashed -- the check said which two
    # should be left by assuming the opposite, and was wrong about the
    # app rather than the app being wrong.
    check('...and the two left are the two it was not aimed at',
          len(set(e['title'] for e in app.trash)) == 2
          and all(e['title'].startswith('Deleted') for e in app.trash))
app.hide_settings_page(); app.update()

# 96: the share panel pages instead of drawing 200 rows at once.
app.trash = []
app.notes = [NO.normalize_note({'id': 1000 + i, 'title': 'Note %03d' % i,
                                'body': 'body', 'category': 'General'})
             for i in range(200)]
app.save_notes()
app.refresh_note_list(); app.update()
_b4_t0 = time.perf_counter()
app.toggle_share_panel(); app.update()
_b4_open_ms = (time.perf_counter() - _b4_t0) * 1000
# The promise is the batch, checked next; the clock only guards a hang, as the
# Trash panel's does above.
check('the share panel opens without hanging with 200 notes (%.0fms) (plan 96)'
      % _b4_open_ms, _b4_open_ms < 10000)
check('...by drawing a first batch rather than all 200 (plan 96)',
      len(app._share_vars) <= 120)
check('...and offering the rest behind Show more',
      _b4_find(app.share_panel, 'Show') is not None)
app.toggle_share_panel(); app.update()

# 120: the share panel is built from the notebook as it is NOW, so a
# change made elsewhere is there the next time it opens.
app.notes = app.notes[:5]
app.save_notes()
app.toggle_share_panel(); app.update()
# Counted by what the panel DREW, not by _share_vars: that dict is kept
# between openings and still holds the ids of notes that are gone, which
# is exactly the kind of thing a check reading the app's bookkeeping
# instead of its output fails to notice.
_b4_rows = [w for w in _b4_all_checkbuttons(app.share_panel)]
check('the share panel reflects a change made while it was closed (plan 120)',
      len(_b4_rows) == 5)
app.toggle_share_panel(); app.update()

# 99: clearing a pasted code empties the box and the message with it.
app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', 'NOTE1:' + ('x' * 900))
app._do_inline_import()          # fails: it is not a real code
app.update()
_b4_clear = _b4_find(app.import_panel, 'Clear')
check('the import panel offers a Clear (plan 99)', _b4_clear is not None)
if _b4_clear is not None:
    _b4_clear.invoke(); app.update()
    check('...and it empties the box completely (plan 99)',
          app.import_box.get('1.0', 'end-1c').strip() == '')
    _b4_msg = getattr(app, 'import_status', None)
    if _b4_msg is not None:
        check('...and takes the failure message with it, ready for a new code',
              str(_b4_msg.cget('text')).strip() == '')
app.toggle_import_panel(); app.update()

app.notes = list(_b4_saved_notes)
app.trash = list(_b4_saved_trash)
app.save_notes()
app.new_note(); app.update()


# ---------------------------------------------------------------------
# Undo on the delete toast
#
# A delete used to leave only a status line. The way back was Settings ->
# Recently deleted, which asks the user to already know the trash exists.
# The toast now carries the way back with it.
#
# What these checks are really about is the CLICK still finding the right
# note eight seconds later. The trash is a list other actions rewrite, so
# "the last thing deleted" is a guess; the toast remembers an id AND the
# deletion stamp, and the restore hands back a note with a NEW id. Every
# check below is aimed at one of those three facts.
# ---------------------------------------------------------------------
def _undo_reset():
    """Empty notebook and trash, with the editor let go of first.

    Order matters, and getting it wrong cost an hour: rewriting
    app.notes while the editor still holds a note leaves a pending
    autosave aimed at that note's id, and the id is then worn by
    whichever note this function seeds next -- the autosave lands on a
    stranger and renames it. new_note() clears selected_note_id, so the
    stale save has nothing to aim at. The app itself never reaches this
    state (a restore takes a NEW id precisely so ids are not reused);
    only a test rebuilding the list by hand can.
    """
    app.new_note()
    app.update()
    app.notes = []
    app.trash = []
    app.save_notes()
    NO.save_trash(app.trash)
    app.refresh_note_list()
    app.update()


_undo_reset()


def _undo_seed(title):
    app.notes.append(NO.normalize_note(
        {'id': max([n['id'] for n in app.notes], default=0) + 1,
         'title': title, 'body': title.lower(), 'category': 'General'}))
    app.save_notes()
    return app.notes[-1]


def _titles():
    return [n.get('title') for n in app.notes]


def _trash_titles():
    return [e.get('title') for e in app.trash]


_u_keep = _undo_seed('UndoKeepMe')
_u_gone = _undo_seed('UndoDeleteMe')
app.refresh_note_list(); app.update()

# Open when it goes: its Undo opens it again (one deleted from the list
# while another is open does not take the editor -- qa6).
app.open_note_in_tab(_u_gone); app.update()
app._delete_note(_u_gone, None); app.update()
check('a single delete puts the note in the trash',
      'UndoDeleteMe' in _trash_titles() and 'UndoDeleteMe' not in _titles())
check('...and the toast offers a way back',
      app.toast_frame.winfo_ismapped() and app.toast_action_lbl.winfo_ismapped())
check('...saying Undo', str(app.toast_action_lbl.cget('text')) == 'Undo')

_qa_click(app.toast_action_lbl); app.update()
check('Undo brings the note back out of the trash',
      'UndoDeleteMe' in _titles() and 'UndoDeleteMe' not in _trash_titles())
check('...without disturbing the note beside it',
      'UndoKeepMe' in _titles() and len(app.notes) == 2)
check('...and the toast goes away with the offer it carried',
      not app.toast_frame.winfo_ismapped())
_u_back = next((n for n in app.notes if n.get('title') == 'UndoDeleteMe'), None)
check('...and the restored note, open when it went, is opened again',
      _u_back is not None and app.selected_note_id == _u_back['id'])

# Clicking Undo twice must not leave two copies of one note. What stops
# it is not the toast forgetting its offer -- it does, twice over -- but
# the offer naming a note that is no longer in the trash to take out.
# Proved by the mutant that makes the restore grab the LAST trash entry
# instead of the marked one: that one restores on every click.
_u_count = len(app.notes)
_qa_click(app.toast_action_lbl); app.update()
check('clicking Undo again does not put back a second copy',
      len(app.notes) == _u_count)

# Something else deleted in between. The toast from the FIRST delete must
# still put back its own note and leave the second one in the trash --
# this is what identifying by (id, deleted_at) buys over "the last entry".
_undo_reset()
_u_first = _undo_seed('UndoFirstGone')
_u_second = _undo_seed('UndoSecondGone')
app.refresh_note_list(); app.update()

app._delete_note(_u_first, None); app.update()
_u_stale_action = app._toast_action          # the offer as it stood then
app._delete_note(_u_second, None); app.update()
check('two deletes leave two notes in the trash', len(app.trash) == 2)
_u_stale_action(); app.update()
check('the older toast puts back ITS note, not the newer one',
      'UndoFirstGone' in _titles() and 'UndoFirstGone' not in _trash_titles())
check('...and leaves the newer delete alone in the trash',
      _trash_titles() == ['UndoSecondGone'])

# The trash emptied under a toast that is still on screen. Nothing to put
# back is an answer, not a crash.
_undo_reset()
_u_doomed = _undo_seed('UndoEmptiedUnderIt')
app.refresh_note_list(); app.update()
app._delete_note(_u_doomed, None); app.update()
_u_orphan_action = app._toast_action
app.trash = []
NO.save_trash(app.trash)
app.update()
_u_orphan_action(); app.update()
check('Undo after the trash was emptied puts back nothing',
      app.notes == [] or 'UndoEmptiedUnderIt' not in _titles())
check('...and says so rather than failing silently',
      'put back' in str(app.toast_lbl.cget('text')).lower())

# The bulk route -- the easiest one to regret, since the list it acts on
# was filtered by whatever was in the search box.
_undo_reset()
_u_b1 = _undo_seed('UndoBulkOne')
_u_b2 = _undo_seed('UndoBulkTwo')
_u_b3 = _undo_seed('UndoBulkKept')
app.refresh_note_list(); app.update()
app.selected_note_ids = {_u_b1['id'], _u_b2['id']}
app._bulk_move_to_trash(); app.update()
check('a bulk delete trashes exactly what was ticked',
      sorted(_trash_titles()) == ['UndoBulkOne', 'UndoBulkTwo']
      and _titles() == ['UndoBulkKept'])
check('...and the toast offers Undo for the batch',
      app.toast_action_lbl.winfo_ismapped())
_qa_click(app.toast_action_lbl); app.update()
check('Undo brings back every note the batch took',
      sorted(_titles()) == ['UndoBulkKept', 'UndoBulkOne', 'UndoBulkTwo']
      and app.trash == [])

# A plain toast must look exactly as it did before any of this: no
# stranded Undo label left over from the delete before it.
app._show_toast('plain as before'); app.update()
check('a toast with nothing to undo carries no action word',
      not app.toast_action_lbl.winfo_ismapped())

# The round trip through the heavy features. A note is not a title and a
# line of prose: it carries a table (which lives in the body TEXT, so
# every formatting offset after it depends on the characters surviving
# unchanged), character formatting, a checklist and an attachment record.
# The restore goes through normalize_note, which rebuilds a note from a
# known schema -- exactly the kind of place a field quietly goes missing.
_undo_reset()
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'UndoRichNote')
app.body_text.insert('1.0', 'bold word here\n| Cheese | 2 |\ncentred line')
app.body_text.tag_add('sel', '1.0', '1.4')
app._fmt_buttons['bold'].invoke()
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.mark_set('insert', '3.0')
app._set_paragraph_align('center')
app._working_checklist = [{'text': 'pack bags', 'done': True},
                          {'text': 'call venue', 'done': False}]
app.update()
app.save_current_note(); app.update()
_u_rich = next((n for n in app.notes if n.get('title') == 'UndoRichNote'), None)
_u_rich['attachments'] = [{'filename': 'receipt.png', 'stored_as': 'receipt.png'}]
app.save_notes()
_u_rich_before = {k: _u_rich[k] for k in
                  ('title', 'body', 'formatting', 'paragraphs',
                   'checklist', 'attachments')}
app.refresh_note_list(); app.update()

app._delete_note(_u_rich, None); app.update()
check('a note carrying a table and formatting goes to the trash whole',
      'UndoRichNote' in _trash_titles())
_qa_click(app.toast_action_lbl); app.update()
_u_rich_after = next((n for n in app.notes
                      if n.get('title') == 'UndoRichNote'), None)
check('Undo brings the rich note back at all', _u_rich_after is not None)
check('...with its body character for character, table row included',
      _u_rich_after is not None
      and _u_rich_after['body'] == _u_rich_before['body']
      and '| Cheese | 2 |' in _u_rich_after['body'])
check('...with its formatting offsets still pointing at the same words',
      _u_rich_after is not None
      and _u_rich_after['formatting'] == _u_rich_before['formatting']
      and any(sp.get('style') == 'bold'
              for sp in _u_rich_after.get('formatting', [])))
check('...with its paragraph alignment',
      _u_rich_after is not None
      and _u_rich_after['paragraphs'] == _u_rich_before['paragraphs'])
check('...with its checklist and the ticks on it',
      _u_rich_after is not None
      and _u_rich_after['checklist'] == _u_rich_before['checklist'])
check('...and with the file that was attached to it',
      _u_rich_after is not None
      and [a.get('filename') for a in _u_rich_after.get('attachments', [])]
      == ['receipt.png'])

# Theming x the toast. The toast is recoloured on every appearance rather
# than tracked, so a theme switched WHILE it is on screen is the seam.
# It survives on the straggler sweep, which walks the whole widget tree --
# but the window that sweep has to cover grew from 1.8 seconds to 8 the
# moment the toast started holding a decision, so it is checked here
# rather than assumed.
_u_theme_before = app.theme_name
_undo_reset()
_u_themed = _undo_seed('UndoThroughATheme')
app.refresh_note_list(); app.update()
app._delete_note(_u_themed, None); app.update()
_u_other = next((t for t in NO.LIGHT_THEMES + NO.DARK_THEMES
                 if NO.THEMES[t]['success'].lower()
                 != NO.THEMES[app.theme_name]['success'].lower()), None)
if _u_other is None:
    check('every theme shares one success colour, so nothing can go stale', True)
else:
    app.set_theme(_u_other); app.update()
    check('a theme switched under a live toast recolours it too',
          str(app.toast_frame.cget('bg')).lower()
          == NO.THEMES[_u_other]['success'].lower())
    check('...including the Undo word inside it',
          str(app.toast_action_lbl.cget('bg')).lower()
          == NO.THEMES[_u_other]['success'].lower())
    check('...and its words are re-picked for the new fill',
          {str(app.toast_lbl.cget('fg')).lower(),
           str(app.toast_action_lbl.cget('fg')).lower()}
          == {NO.letters_on(NO.THEMES[_u_other]['success']).lower()})
    check('...and it still works after the switch',
          app._toast_action is not None)
    _qa_click(app.toast_action_lbl); app.update()
    check('...putting the note back in the new theme',
          'UndoThroughATheme' in _titles())
app.set_theme(_u_theme_before); app.update()

_undo_reset()


# ---------------------------------------------------------------------
# A repeating series says so wherever it can be deleted.
#
# A series is ONE note in every list and every count, and deleting it
# takes every occurrence it has. The single-note delete has always asked
# "Delete this entire repeating series?". None of the routes that act on
# a selection said anything at all -- not the bulk move to trash, and
# neither of the two permanent deletes in the Trash, where there is no
# way back. Field-reported: "it doesn't tell me one of them is a series".
# ---------------------------------------------------------------------
_undo_reset()
app.show_settings_page = getattr(app, 'show_settings_page')
_sr_plain = NO.normalize_note({'id': 910, 'title': 'JustANote', 'body': 'b',
                               'category': 'General'})
_sr_series = NO.normalize_note({'id': 911, 'title': 'WaterThePlants',
                                'body': 'b', 'category': 'General',
                                'date': '2026-09-01',
                                'recurrence': {'freq': 'weekly', 'weekdays': [0], 'count': 10}})
app.notes = [_sr_plain, _sr_series]
app.save_notes()
app.refresh_note_list()
app.update()

_sr_said = {}
_sr_real_ask = app.ask_yes_no
app.ask_yes_no = lambda t, m, **k: (_sr_said.__setitem__('msg', m), True)[1]

# A selection with no series in it must not mention one.
app.selected_note_ids = {910}
app._bulk_move_to_trash()
app.update()
check('a bulk delete of ordinary notes says nothing about series',
      'series' not in _sr_said.get('msg', '').lower())
check('...and stops saying "note(s)" while it is at it',
      'note(s)' not in _sr_said.get('msg', ''))

_undo_reset()
app.notes = [NO.normalize_note(dict(_sr_plain)),
             NO.normalize_note(dict(_sr_series))]
app.save_notes()
app.refresh_note_list()
app.update()
app.selected_note_ids = {910, 911}
app._bulk_move_to_trash()
app.update()
_sr_msg = _sr_said.get('msg', '')
check('a bulk delete naming a series says so',
      'repeating series' in _sr_msg)
check('...and says what goes with it',
      'every occurrence' in _sr_msg)
check('...counting it, since a series is one note in the count, and '
      'agreeing with itself',
      '1 of them is a repeating series' in _sr_msg)
check('the series really did go to the trash whole',
      any(e.get('id') == 911 and e.get('recurrence') for e in app.trash))

# The Trash panel. This is the list where deleting cannot be undone, and
# the only one in the app that never marked a series.
app.show_settings_page()
app.toggle_settings_panel('trash')
app.update()


def _trash_rows():
    """Every row frame holding a Restore/Delete pair.

    Matched on the button TEXTS, not on "a frame with two buttons" --
    the retention card above the list is also a frame with buttons in
    it, and counting it made three checks fail for the wrong reason.
    """
    out = []

    def walk(w):
        labels = set()
        for k in w.winfo_children():
            if isinstance(k, tk.Button):
                try:
                    labels.add(str(k.cget('text')))
                except tk.TclError:
                    pass
        if {'Restore', 'Delete'} <= labels:
            out.append(w)
        for k in w.winfo_children():
            walk(k)
    walk(app.settings_trash_panel)
    return out


def _row_text(row):
    texts = []

    def walk(w):
        try:
            texts.append(str(w.cget('text')))
        except tk.TclError:
            pass
        for k in w.winfo_children():
            walk(k)
    walk(row)
    return ' '.join(texts)


_sr_rows = _trash_rows()
check('the trash panel drew a row per deleted note', len(_sr_rows) == 2)
_sr_series_row = next((r for r in _sr_rows if 'WaterThePlants' in _row_text(r)), None)
_sr_plain_row = next((r for r in _sr_rows if 'JustANote' in _row_text(r)), None)
check('a trashed series is marked as one',
      _sr_series_row is not None and '🔁' in _row_text(_sr_series_row))
check('...and says how often it repeats',
      _sr_series_row is not None and 'repeats' in _row_text(_sr_series_row))
check('an ordinary trashed note carries no such marks',
      _sr_plain_row is not None and '🔁' not in _row_text(_sr_plain_row)
      and 'repeats' not in _row_text(_sr_plain_row))

# The buttons' space is RESERVED, not left over. The packer hands out the
# cavity in pack order, so this is about order, not about today's window
# size: with the expanding text frame packed first, a longer title or a
# longer "repeats ..." line ate the room Restore and Delete needed.
for _r in _sr_rows:
    _slaves = _r.pack_slaves()
    _btns = [i for i, w in enumerate(_slaves) if isinstance(w, tk.Button)]
    _frames = [i for i, w in enumerate(_slaves) if isinstance(w, tk.Frame)]
    check('the row packs its buttons before the text that can be shortened',
          bool(_btns) and bool(_frames) and max(_btns) < min(_frames))
    for _w in _slaves:
        if isinstance(_w, tk.Button):
            check('...so %s is drawn at least as wide as it asks'
                  % str(_w.cget('text')),
                  _w.winfo_width() >= _w.winfo_reqwidth())

# Reserving the buttons' width left the text less room, and a series'
# second line is long: "deleted ... · 84 day(s) left · repeats every week
# on mon, 10 times". Drawn on one line it was cut mid-word with nothing
# to say so -- reported the same hour the buttons were fixed, one
# clipping traded for another. It wraps at its own width now. The measure
# is the one the Settings labels taught: what the label ASKED for against
# what it was GIVEN.
for _r in _sr_rows:
    for _frame in [w for w in _r.pack_slaves() if isinstance(w, tk.Frame)]:
        for _lbl in _frame.winfo_children():
            if not isinstance(_lbl, tk.Label):
                continue
            check('a trash row draws its text inside the room it has (%s)'
                  % str(_lbl.cget('text'))[:26].replace('\n', ' '),
                  _lbl.winfo_reqwidth() <= _lbl.winfo_width() + 1)

# Delete permanently, on the series. No way back from here.
_sr_said.clear()
# Found first, invoked once. Pressing Delete redraws the whole list, so
# carrying on through the loop afterwards reads widgets that no longer
# exist -- which is a crash in the test, not a finding.
_sr_del_btn = None
for _r in _sr_rows:
    if 'WaterThePlants' not in _row_text(_r):
        continue
    for _w in _r.winfo_children():
        if isinstance(_w, tk.Button) and 'Delete' in str(_w.cget('text')):
            _sr_del_btn = _w
            break
    break
check('the trashed series has a Delete button of its own',
      _sr_del_btn is not None)
if _sr_del_btn is not None:
    _sr_del_btn.invoke()
    app.update()
check('deleting a series for good warns that it is one',
      'repeating series' in _sr_said.get('msg', ''))
check('...and still says it cannot be undone',
      "can't be undone" in _sr_said.get('msg', ''))

# Empty trash, counting what is in there.
app.trash = [
    {'id': 920, 'title': 'P1', 'body': 'b', 'category': 'General',
     'deleted_at': '2026-09-01 10:00:00'},
    {'id': 921, 'title': 'S1', 'body': 'b', 'category': 'General',
     'recurrence': {'freq': 'daily'}, 'deleted_at': '2026-09-01 10:00:00'},
    {'id': 922, 'title': 'S2', 'body': 'b', 'category': 'General',
     'recurrence': {'freq': 'weekly'}, 'deleted_at': '2026-09-01 10:00:00'},
]
NO.save_trash(app.trash)
app.toggle_settings_panel('trash')
app.toggle_settings_panel('trash')
app.update()
_sr_said.clear()
_sr_empty = find_btn(app.settings_trash_panel, 'Empty trash')
if _sr_empty is not None:
    _sr_empty.invoke()
    app.update()
check('emptying the trash counts the series in it',
      '2 of them are repeating series' in _sr_said.get('msg', ''))

# Yes deletes the entries the question counted, and only them. Read after
# the answer, a note that reached the Trash while the question waited was
# deleted for good with the rest -- by the one question in the app that
# cannot be undone. It stays in the Trash now.
_et_now = time.strftime('%Y-%m-%d %H:%M:%S')
app.trash = [{'id': 940, 'title': 'Counted', 'body': 'b',
              'category': 'General', 'deleted_at': _et_now}]
NO.save_trash(app.trash)
app.toggle_settings_panel('trash')
app.toggle_settings_panel('trash')
app.update()
_et_stub = app.ask_yes_no


def _et_yes(t, m, **k):
    _sr_said['msg'] = m
    app.trash.append({'id': 941, 'title': 'Arrived while asking', 'body': 'b',
                      'category': 'General', 'deleted_at': _et_now})
    return True


app.ask_yes_no = _et_yes
_et_btn = find_btn(app.settings_trash_panel, 'Empty trash')
if _et_btn is not None:
    _et_btn.invoke()
    app.update()
app.ask_yes_no = _et_stub
check('Empty trash deletes the notes its question counted, and keeps one '
      'that reached the Trash while it waited (%s, on disk %s, %r)'
      % ([e.get('title') for e in app.trash],
         [e.get('title') for e in NO.load_trash()], _sr_said.get('msg')),
      _et_btn is not None
      and [e.get('title') for e in app.trash] == ['Arrived while asking']
      and [e.get('title') for e in NO.load_trash()] == ['Arrived while asking']
      and 'all 1 note ' in _sr_said.get('msg', ''))

# The Trash written first, then the files: deleted first, a Trash the disk
# refused kept an entry naming files that were gone.
import noteorganizer.ui.settings_page as _sp3
_tw_file = os.path.join(NO.ATTACHMENTS_DIR, 'tw_kept.bin')
with open(_tw_file, 'w') as _tw_f:
    _tw_f.write('x')
app.trash = [{'id': 945, 'title': 'Holds a file', 'body': 'b', 'category': 'General',
              'deleted_at': _et_now,
              'attachments': [{'filename': 'tw_kept.bin', 'stored_as': 'tw_kept.bin'}]}]
NO.save_trash(app.trash)
app.toggle_settings_panel('trash')
app.toggle_settings_panel('trash')
app.update()
_tw_real, _tw_warn, _tw_said = _sp3.save_trash, app.show_warning, []
_sp3.save_trash = lambda t: (False, OSError(28, 'No space left on device'))
app.show_warning = lambda title, msg, **k: _tw_said.append(title)
app.ask_yes_no = lambda t, m, **k: True
try:
    _tw_btn = find_btn(app.settings_trash_panel, 'Empty trash')
    if _tw_btn is not None:
        _tw_btn.invoke()
        app.update()
finally:
    _sp3.save_trash, app.show_warning = _tw_real, _tw_warn
    app.ask_yes_no = _et_stub
check('a Trash that cannot be written deletes nothing: the entry and its file '
      'stay (%s)' % _tw_said,
      _tw_btn is not None and os.path.isfile(_tw_file)
      and [e.get('title') for e in app.trash] == ['Holds a file']
      and _tw_said == ['Nothing was deleted'])
app.ask_yes_no = lambda t, m, **k: True
_tw_btn = find_btn(app.settings_trash_panel, 'Empty trash')
if _tw_btn is not None:
    _tw_btn.invoke()
    app.update()
app.ask_yes_no = _et_stub
check('written, Empty trash then takes the file with it',
      _tw_btn is not None and not os.path.isfile(_tw_file) and app.trash == [])

# A corrupt recurrence must not break the sentence -- the trash holds
# whatever was on disk, and normalize_note does not run on the way out.
app.trash = [
    {'id': 930, 'title': 'Broken', 'body': 'b', 'category': 'General',
     'recurrence': 'not a dict at all', 'deleted_at': '2026-09-01 10:00:00'},
    {'id': 931, 'title': 'AlsoBroken', 'body': 'b', 'category': 'General',
     'recurrence': None, 'deleted_at': '2026-09-01 10:00:00'},
]
NO.save_trash(app.trash)
try:
    _sr_broken = app._series_warning(app.trash)
    check('a corrupt recurrence does not break the warning', True)
    check('...and is not mistaken for a series', 'series' not in _sr_broken)
except Exception as _e:
    check('a corrupt recurrence does not break the warning (%s)' % _e, False)
try:
    app.toggle_settings_panel('trash')
    app.toggle_settings_panel('trash')
    app.update()
    check('...and the trash panel still draws it', True)
except Exception as _e:
    check('...and the trash panel still draws it (%s)' % _e, False)

app.ask_yes_no = _sr_real_ask
app.hide_settings_page()
app.update()
_undo_reset()

# ======================================================================
# The "try to break it" audit of 2026-09-29: the Update route
# ======================================================================

# ---- Restore previous brings back EVERYTHING an update replaced ----
# The update dialog promised each update "can be undone with ↩ Restore
# previous", while the rescue copy held the text alone: the ticked list,
# the date, the yearly repeat and the colour were gone for good.
app.open_blank_tab()
app.update()
app.notes = [NO.normalize_note({
    'id': 1, 'title': 'Passport', 'body': 'renew',
    'checklist': [{'text': 'photo', 'done': True},
                  {'text': 'form', 'done': True},
                  {'text': 'fee', 'done': False}],
    'date': '2026-10-01', 'recurrence': {'freq': 'yearly'},
    'color': '#ff0000'})]
app.save_notes()
_pp = app.notes[0]
_pp_code = NO.encode_share_code([{
    'uid': _pp['uid'], 'title': 'Passport', 'body': 'renew (from phone)',
    'comments': '', 'category': 'General', 'date': '', 'color': '',
    'recurrence': {}, 'checklist': [{'text': 'photo', 'done': False}]}])
_real_dlg_pp = app._themed_dialog
_real_ask_pp = app.ask_yes_no
app._themed_dialog = lambda *a, **k: 'update'
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _pp_code)
app._do_inline_import()
app.update()
check('a share-code update replaced the checklist, date, repeat and colour',
      len(_pp['checklist']) == 1 and _pp['date'] == ''
      and not _pp['recurrence'].get('freq') and _pp['color'] == '')
_pp_asked = []
app.ask_yes_no = lambda *a, **k: (_pp_asked.append(a), True)[1]
app.load_note(_pp)
app.update()
app.restore_previous_version()
app.update()
check('Restore previous brings the checklist back, ticks and all',
      [(i['text'], i['done']) for i in _pp['checklist']]
      == [('photo', True), ('form', True), ('fee', False)])
check('...and the date, the yearly repeat and the colour',
      _pp['date'] == '2026-10-01'
      and _pp['recurrence'].get('freq') == 'yearly'
      and _pp['color'] == '#ff0000' and 'renew' == _pp['body'].strip())
check('...into the editor too, not only the file (shown day first)',
      len(app.capture_editor_state().get('checklist', [])) == 3
      and app.date_entry.get() == '01.10.2026')
check('...and its question names what comes back, not just "text"',
      bool(_pp_asked) and 'checklist' in _pp_asked[-1][1]
      and 'repeat rule' in _pp_asked[-1][1])
app._themed_dialog = _real_dlg_pp
app.ask_yes_no = _real_ask_pp

# ---- A backup's Update brings what its copy owns ----
# A backup is the user's own notebook. Routed like a share code, its
# attachments, skipped days, per-day edits and pin were dropped without a
# word, on the route people use to move a notebook to a new PC.
app.open_blank_tab()
app.update()
_bk_name = 'qa3_ticket_upd.txt'
_bk_path = os.path.join(NO.ATTACHMENTS_DIR, _bk_name)
with open(_bk_path, 'w', encoding='utf-8') as _f:
    _f.write('ticket')
app.trash = []
NO.save_trash(app.trash)
app.notes = [NO.normalize_note({
    'id': 1, 'title': 'Trip', 'body': 'laptop version',
    'date': '2026-09-01', 'recurrence': {'freq': 'weekly'},
    'exceptions': ['2026-09-08'],
    'overrides': {'2026-09-15': {'body': 'moved to Wed'}},
    'pinned': True,
    'attachments': [{'filename': 'ticket.txt', 'stored_as': _bk_name}]})]
app.save_notes()
_trip_uid = app.notes[0]['uid']
_bkzip = os.path.join(tempfile.gettempdir(), 'qa3_update_backup.zip')
if os.path.exists(_bkzip):
    os.remove(_bkzip)
fd.asksaveasfilename = lambda **k: _bkzip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()
# The other PC: the same note, from before the laptop's changes.
os.remove(_bk_path)
app.notes = [NO.normalize_note({
    'id': 1, 'uid': _trip_uid, 'title': 'Trip', 'body': 'desktop version',
    'date': '2026-09-01', 'recurrence': {'freq': 'weekly'},
    'checklist': [{'text': 'visa', 'done': False}]})]
app.save_notes()
_real_dlg_bk = app._themed_dialog
app._themed_dialog = lambda *a, **k: 'update'
fd.askopenfilename = lambda **k: _bkzip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
app._themed_dialog = _real_dlg_bk
_trips = [n for n in app.notes if n.get('uid') == _trip_uid]
_trip = _trips[0] if _trips else {}
check('a backup Update adds no second copy of the note', len(_trips) == 1)
check("...and brings the backup's skipped days, per-day edits and pin",
      _trip.get('exceptions') == ['2026-09-08']
      and (_trip.get('overrides') or {}).get('2026-09-15', {}).get('body')
      == 'moved to Wed'
      and _trip.get('pinned') is True)
_trip_files = [a.get('stored_as') for a in _trip.get('attachments') or []]
check("...and the file attached on the other PC, present on disk",
      len(_trip_files) == 1
      and os.path.isfile(os.path.join(NO.ATTACHMENTS_DIR, _trip_files[0])))
app.load_note(_trip)
app.update()
app.ask_yes_no = lambda *a, **k: True
app.restore_previous_version()
app.update()
app.ask_yes_no = _real_ask_pp
check('Restore previous after a backup Update puts this PC\'s version back whole',
      'desktop version' in _trip.get('body', '')
      and _trip.get('exceptions') == [] and _trip.get('overrides') == {}
      and _trip.get('pinned') is False
      and [i['text'] for i in _trip.get('checklist', [])] == ['visa'])
check('...while the file the backup brought stays attached (an update only adds files)',
      [a.get('stored_as') for a in _trip.get('attachments') or []] == _trip_files)
os.remove(_bkzip)

# ---- A backup's Trash keeps an entry that only RESEMBLES a local one ----
# Re-importing your own backup must not double the Trash, and the skip
# that prevents it runs with nobody asked. It used the fuzzy duplicate key,
# which ignores the date, so a trashed note differing from a local one in
# its date was dropped -- the only copy of it, on a route that says it
# adds and never removes.
app.open_blank_tab()
app.update()
app.notes = []
app.save_notes()
_tr_days_ago = lambda n: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - n * 86400))
app.trash = [dict(NO.normalize_note({'id': 7, 'title': 'Old plan', 'body': 'x',
                                     'date': '2026-01-01'}),
                  deleted_at=_tr_days_ago(3))]
NO.save_trash(app.trash)
_trzip = os.path.join(tempfile.gettempdir(), 'qa3_trash_strict.zip')
if os.path.exists(_trzip):
    os.remove(_trzip)
fd.asksaveasfilename = lambda **k: _trzip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()
app.trash = [dict(NO.normalize_note({'id': 7, 'title': 'Old plan', 'body': 'x',
                                     'date': '2026-02-02'}),
                  deleted_at=_tr_days_ago(2))]
NO.save_trash(app.trash)
_real_dlg_tr = app._themed_dialog
app._themed_dialog = lambda *a, **k: 'all'
fd.askopenfilename = lambda **k: _trzip
for _round in range(2):
    app.import_data()
    t0 = time.time()
    while app._import_state is not None and time.time() - t0 < 120:
        app.update()
    if _round == 0:
        check("a backup's trashed note that differs in its date is kept",
              sorted(e.get('date') for e in app.trash
                     if e.get('title') == 'Old plan')
              == ['2026-01-01', '2026-02-02'])
app._themed_dialog = _real_dlg_tr
check('...and importing the same backup again still does not double the Trash',
      len([e for e in app.trash if e.get('title') == 'Old plan']) == 2)
os.remove(_trzip)
app.trash = []
NO.save_trash(app.trash)
app.notes = []
app.save_notes()

# ---- NOTHING TYPED IS LOST: WHAT A DELETE, AN IMPORT AND A RESTORE TOUCH ----
# The break-it wave of 2026-09-30 found routes where work already saved,
# or still on screen, was replaced without a word. Each block names its
# route; docs/ISSUES_LOG.md has the stories.
if getattr(app, '_settings_open', False):
    app.hide_settings_page()
app.new_note(); app.update()

# A delete elsewhere leaves the open note alone. Deleting some OTHER note
# used to "switch" the editor to its one tab -- the note already on screen
# -- restoring it from the copy taken when it was opened, so a version
# saved since was put back, and the next switch wrote it over the new one.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Recipe', 'body': 'first version'}),
             NO.normalize_note({'id': 2, 'title': 'Old list', 'body': 'eggs'})]
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
app.notes[0]['body'] = 'second version'   # saved behind the tab's copy,
app.save_notes()                          # as "Restore previous" does
app.load_note(app.notes[0]); app.update()
app._delete_note(app.find_note(2), None)
app.update()
check('deleting another note leaves the open one on its latest version',
      app.body_text.get('1.0', 'end-1c') == 'second version')
app._flush_autosave(); app.update()
check('...so the next save cannot put the older version back',
      app.find_note(1)['body'] == 'second version')

# An import the person would not let replace the note on screen. Going back
# to fix a date its save could not store means stay -- but the import went
# on, loaded the note it carried into the repeating note still on screen
# (whose next save wrote it over the whole series), and had already cleared
# the code. (Found with a day's own question, "this occurrence or the whole
# series?", whose Cancel did the same; a day now saves to itself.)
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Yoga', 'body': 'stretch',
                                'date': '2026-09-01',
                                'recurrence': {'freq': 'weekly'}})]
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
app.body_text.insert('end', '\nbring the mat')
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '31/09/2026')
_nt_code = NO.encode_share_code([{'title': 'Lasagne', 'body': 'layers',
                                  'category': 'General'}])
if not app._is_placed(app.import_panel):
    app.toggle_import_panel()
app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _nt_code)
_nt_asked = []
_nt_real_dialog = app._themed_dialog
app._themed_dialog = lambda title, *a, **k: (_nt_asked.append(title), False)[1]
try:
    app._do_inline_import()
finally:
    app._themed_dialog = _nt_real_dialog
app.update()
check(f"going back to fix a date keeps the note in the editor, not the import "
      f"({_nt_asked})",
      _nt_asked == ["Part of this note isn't saved"]
      and app.title_entry.get() == 'Yoga' and app.selected_note_id == 1
      and 'bring the mat' in app.body_text.get('1.0', 'end-1c')
      and app._typed_date() == '31/09/2026')
check('...the code stays in the box, to try again',
      app.import_box.get('1.0', 'end').strip() == _nt_code.strip())
check('...and the series is untouched',
      [n['title'] for n in app.notes] == ['Yoga']
      and app.notes[0]['recurrence']['freq'] == 'weekly')
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
app.new_note(); app.update()
if app._is_placed(app.import_panel):
    app.toggle_import_panel()

# An update that would change nothing changes nothing. It rewrote the
# rescue copy with a duplicate of the note itself, so importing the same
# backup twice left this device's newer text in no file at all.
_nt_mine = NO.normalize_note({'id': 1, 'title': 'Report', 'body': 'v2 - newer'})
_nt_theirs = {'uid': _nt_mine['uid'], 'title': 'Report', 'body': 'v1 - older'}
NO.apply_shared_update(_nt_mine, _nt_theirs, NO.UPDATABLE_FROM_BACKUP)
check('an update keeps the text it replaced as the rescue copy',
      _nt_mine['_prev']['body'] == 'v2 - newer')
NO.apply_shared_update(_nt_mine, _nt_theirs, NO.UPDATABLE_FROM_BACKUP)
check('...and the same update again leaves that rescue copy alone',
      _nt_mine['_prev']['body'] == 'v2 - newer')
app.notes = [_nt_mine]; app.save_notes()
_nt_asked = []
app._themed_dialog = lambda *a, **k: (_nt_asked.append((a, k)), 'update')[1]
_nt_res = app._take_known_notes([dict(_nt_theirs)], 'backup')
app._themed_dialog = _real_dialog
check(f'a note arriving exactly as it is here is not offered as an update '
      f'({[q[0][0] for q in _nt_asked]})',
      [q[0][0] for q in _nt_asked] == ['Already here, unchanged']
      and _nt_res[2] == [] and _nt_res[3] == 1 and _nt_res[4] == [])
# ...but whether to add it again is asked (field pass: re-importing a
# backup skipped such notes without a word, and the choice was wanted).
# Skipping is the safe answer, and the one Escape and Enter give.
_nt_kw = _nt_asked[0][1] if _nt_asked else {}
check(f'the question about unchanged notes skips unless told otherwise '
      f'({_nt_kw.get("buttons")}; default {_nt_kw.get("default")!r})',
      bool(_nt_kw.get('buttons')) and _nt_kw['buttons'][0][1] == 'skip'
      and _nt_kw.get('default') == _nt_kw['buttons'][0][0])
app._themed_dialog = lambda *a, **k: 'copies'
_nt_res = app._take_known_notes([dict(_nt_theirs)], 'backup')
app._themed_dialog = _real_dialog
check('...and "Add copies anyway" hands back a copy without the identity',
      _nt_res[0] and _nt_res[1] == [] and _nt_res[3] == 0
      and len(_nt_res[4]) == 1 and 'uid' not in _nt_res[4][0]
      and _nt_res[4][0]['body'] == 'v1 - older')
# One edited elsewhere and one unchanged: the two questions, one after the
# other, count the same batch. The first said "All 1 note" -- it chose its
# "All" without the unchanged notes, asked about straight after.
_nt_other = NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'other text'})
app.notes = [_nt_mine, _nt_other]; app.save_notes()
_nt_asked = []
app._themed_dialog = lambda *a, **k: (_nt_asked.append(a[1]), 'cancel-ish')[1]
app._take_known_notes([{'uid': _nt_mine['uid'], 'title': 'Report',
                        'body': 'edited on the laptop'}, dict(_nt_other)], 'backup')
app._themed_dialog = _real_dialog
check(f'two questions about one batch count it the same way ({_nt_asked})',
      len(_nt_asked) == 2
      and all('1 of the 2 notes in this backup' in m for m in _nt_asked))
# A backup's note that differs by a file alone takes the file and keeps no
# copy: the question promised Restore previous of it, and warned it OLDER.
_nf_mine = NO.normalize_note({'id': 3, 'title': 'Ticket', 'body': 'trip',
                              'updated': '2026-11-10 10:00:00'})
_nf_theirs = dict(_nf_mine, updated='2026-11-01 10:00:00',
                  attachments=[{'filename': 'ticket.pdf', 'stored_as': '20261101_ticket.pdf'}])
app.notes = [_nf_mine]; app.save_notes()
_nf_asked = []
app._themed_dialog = lambda *a, **k: (_nf_asked.append(a[1]), 'cancel')[1]
app._take_known_notes([_nf_theirs], 'backup')
app._themed_dialog = _real_dialog
_nf_said = _nf_asked[0] if _nf_asked else ''
check(f"a note differing by a file alone is said to take the file, no Restore previous, no OLDER "
      f"({_nf_said[-120:]!r})",
      'adds the attached files it lacks, nothing else' in _nf_said
      and 'Restore previous' not in _nf_said and 'OLDER' not in _nf_said)
# ...and words typed in it just before, saved by Update's own flush, make it a
# note Update rewrites: asked again, in those words, not updated on a promise
# of "nothing else" (its rescue copy replaced without a word).
_nw_mine = NO.normalize_note({'id': 7, 'title': 'Ticket two', 'body': 'trip',
                              'updated': '2026-11-10 10:00:00'})
_nw_theirs = dict(_nw_mine, updated='2026-11-01 10:00:00',
                  attachments=[{'filename': 'ticket.pdf', 'stored_as': '20261101_ticket.pdf'}])
app.notes = [_nw_mine]; app.save_notes()
app.open_note_in_tab(app.find_note(7)); app.update()
app.body_text.insert('end', ' and the hotel')
_nw_asked = []
app._themed_dialog = lambda *a, **k: (_nw_asked.append(a[1]), 'update')[1]
try:
    app._take_known_notes([_nw_theirs], 'backup')
finally:
    app._themed_dialog = _real_dialog
app.open_blank_tab(); app.update()
check(f"words typed in a file-alone note before Update are asked about again "
      f"({len(_nw_asked)} asked, {[s[-60:] for s in _nw_asked]})",
      len(_nw_asked) == 2 and 'nothing else' in _nw_asked[0]
      and 'Restore previous' in _nw_asked[1])
# ...and a note whose words differ, most of them cut just before: the flush's
# rescue copy of them is one Update replaces, asked again saying so.
_nc_mine = NO.normalize_note({'id': 8, 'title': 'Long one', 'body': 'word ' * 120,
                              'updated': '2026-11-01 10:00:00'})
_nc_theirs = dict(_nc_mine, body='the backup\'s short version', updated='2099-01-01 10:00:00')
app.notes = [_nc_mine]; app.save_notes()
app.open_note_in_tab(app.find_note(8)); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'kept')
_nc_asked = []
app._themed_dialog = lambda *a, **k: (_nc_asked.append(a[1]), 'update')[1]
try:
    app._take_known_notes([_nc_theirs], 'backup')
finally:
    app._themed_dialog = _real_dialog
app.open_blank_tab(); app.update()
check(f"a rescue copy made by Update's flush is asked about again ({len(_nc_asked)} asked)",
      len(_nc_asked) == 2 and 'earlier version' not in _nc_asked[0]
      and 'earlier version' in _nc_asked[1])
# ...and one a word typed just before makes newer than the backup's: asked
# again, the backup's version now OLDER.
_no_mine = NO.normalize_note({'id': 9, 'title': 'Short one', 'body': 'plain',
                              'updated': '2026-11-01 10:00:00'})
_no_theirs = dict(_no_mine, body='plain, from the backup', updated='2026-11-10 10:00:00')
app.notes = [_no_mine]; app.save_notes()
app.open_note_in_tab(app.find_note(9)); app.update()
app.body_text.insert('end', ' and more')
_no_asked = []
app._themed_dialog = lambda *a, **k: (_no_asked.append(a[1]), 'update')[1]
try:
    app._take_known_notes([_no_theirs], 'backup')
finally:
    app._themed_dialog = _real_dialog
app.open_blank_tab(); app.update()
check(f"a backup made OLDER by Update's flush is asked about again ({len(_no_asked)} asked)",
      len(_no_asked) == 2 and 'OLDER' not in _no_asked[0] and 'OLDER' in _no_asked[1])
# ...and a share code's Update the same: words cut just before, kept by the
# flush as a rescue copy, are said replaced, asked again.
_sc_note = NO.normalize_note({'id': 10, 'title': 'Coded', 'body': 'word ' * 120})
app.notes = [_sc_note]; app.save_notes()
app.load_note(app.find_note(10)); app.update()
app.share_current_note_as_code(); app.update()
_sc_code = find_text_widget(app.editor_code_area).get('1.0', 'end-1c')
# Changed here through the editor, so the code differs from the note (changed
# behind the open editor, the panel's own save put the old version back).
app.title_entry.insert('end', ' here')
app.save_current_note(); app.update()
_sc_asked = []
app._themed_dialog = lambda *a, **k: (_sc_asked.append(a[1]), 'update')[1]
try:
    # The panel opened first (opening it saves the editor), the words cut after.
    app.toggle_import_panel(); app.update()
    app.import_box.delete('1.0', 'end')
    app.import_box.insert('1.0', _sc_code)
    app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'kept')
    app._do_inline_import(); app.update()
finally:
    app._themed_dialog = _real_dialog
app.open_blank_tab(); app.update()
check(f"a share code's Update whose flush made a rescue copy is asked about again "
      f"({len(_sc_asked)} asked)",
      len(_sc_asked) == 2 and 'is replaced by the one from before' not in _sc_asked[0]
      and 'is replaced by the one from before' in _sc_asked[1])
# ...and one differing by a field a newer version wrote alone is no Update
# (D2), but the question says the backup holds it: "nothing" was untrue.
_nu_mine = NO.normalize_note({'id': 4, 'title': 'Plan', 'body': 'b'})
_nu_theirs = dict(_nu_mine, reminder_at='2026-11-20 09:00')
app.notes = [_nu_mine]; app.save_notes()
_nu_asked = []
app._themed_dialog = lambda *a, **k: (_nu_asked.append((a[0], a[1])), 'skip')[1]
app._take_known_notes([_nu_theirs], 'backup')
app._themed_dialog = _real_dialog
_nu_said = _nu_asked[0] if _nu_asked else ('', '')
check(f"a note differing by a newer version's field alone is said so, and that Skip leaves it out "
      f"({_nu_said[0]!r}, {_nu_said[1][-110:]!r})",
      _nu_said[0] == 'Already here, unchanged' and 'fields a newer version wrote' in _nu_said[1]
      and 'Skipping leaves those fields out' in _nu_said[1])
# ...but only fields the import brings: this device's own, absent from an
# older backup or from a share code (which carries none), were said its.
_nr_mine = NO.normalize_note(dict({'id': 6, 'title': 'Plan', 'body': 'b'},
                                  reminder_at='2026-11-20 09:00'))
_nr_theirs = {k: v for k, v in _nr_mine.items() if k != 'reminder_at'}
_nr_said = []
for _nr_source in ('backup', 'code'):
    app.notes = [_nr_mine]; app.save_notes()
    _nr_asked = []
    app._themed_dialog = lambda *a, **k: (_nr_asked.append((a[0], a[1])), 'skip')[1]
    app._take_known_notes([dict(_nr_theirs)], _nr_source)
    app._themed_dialog = _real_dialog
    _nr_said.append(_nr_asked[0] if _nr_asked else ('', ''))
check(f"the device's own newer field, absent from an older backup or a code, is not said the import's "
      f"({[s[1][-70:] for s in _nr_said]!r})",
      all(t == 'Already here, unchanged' and 'newer version' not in s
          and 'Skipping changes nothing' in s for t, s in _nr_said))
app.notes = [_nt_mine]; app.save_notes()

# "Update" waits for the import's last answer. The updates were applied
# at once, so Cancel on the duplicate question that follows left them in
# memory, and the next unrelated save wrote them to disk.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Report', 'body': 'local v2'})]
app.save_notes()
app._themed_dialog = lambda *a, **k: 'update'
_nt_res = app._take_known_notes(
    [{'uid': app.notes[0]['uid'], 'title': 'Report', 'body': 'laptop v1'}],
    'backup')
app._themed_dialog = _real_dialog
check('"Update" hands the update back rather than making it',
      _nt_res[0] and len(_nt_res[2]) == 1
      and app.notes[0]['body'] == 'local v2')
app._apply_known_updates(_nt_res[2], 'backup')
check('...and it happens when the import applies it, after its last question',
      app.notes[0]['body'] == 'laptop v1')

# A note under review from a code keeps the identity it arrived with. The
# review editor dropped it, so a note sent out, edited elsewhere and sent
# back arrived as a stranger and became a second copy.
app.notes = []; app.save_notes()
app.new_note(); app.update()
app._open_imported_note_in_editor(
    {'uid': 'qa3-arrived-0001', 'title': 'Trip plan', 'body': 'flights'})
app.save_current_note(); app.update()
check('a note saved from the import review keeps the identity it arrived with',
      [n.get('uid') for n in app.notes] == ['qa3-arrived-0001'])
app._open_imported_note_in_editor(
    {'uid': 'qa3-arrived-0001', 'title': 'Trip plan', 'body': 'another'})
app.save_current_note(); app.update()
check('...but never one a note here already wears',
      len({n.get('uid') for n in app.notes}) == 2)
app.new_note(); app.update()
# Ctrl+Z starts from the note as it arrived, as after every other load. The
# import was the first step on Tk's undo stack: Ctrl+Z took the whole body
# back, and the autosave then stored the imported note empty.
app._open_imported_note_in_editor({'title': 'Shopping',
                                   'body': 'List for Saturday'})
app.update()
check(f'an imported note gives Ctrl+Z nothing to take back '
      f'({app._can_edit_undo(app.body_text)}; '
      f'{app.body_text.get("1.0", "end-1c")!r})',
      not app._can_edit_undo(app.body_text)
      and app.body_text.get('1.0', 'end-1c').startswith('List for Saturday'))
app._cancel_pending_autosave()
app.new_note(); app.update()

# A batch comes back from the Trash in one pass: each file written once,
# the notes first. Note by note, every restore rewrote the whole trash
# file (an Undo of a thousand notes froze the app for over half a
# minute), and the trash was written before the notes, so a failed notes
# write left a note in neither file.
app.trash = []; NO.save_trash(app.trash)
app.notes = [NO.normalize_note({'id': i, 'title': 'Bulk %d' % i, 'body': 'x'})
             for i in range(1, 61)]
app.save_notes()
_nt_marks = [(e.get('id'), e.get('deleted_at'))
             for e in app._move_notes_to_trash(list(app.notes))]
app.notes = []; app.save_notes()
_nt_writes = []
_nt_real_save_trash = NO.save_trash
_nt_real_save_notes = app.save_notes
NO.save_trash = lambda t, _r=_nt_real_save_trash: (_nt_writes.append('trash'), _r(t))[1]
app.save_notes = lambda _r=_nt_real_save_notes: (_nt_writes.append('notes'), _r())[1]
app._undo_trash(_nt_marks)
NO.save_trash = _nt_real_save_trash
del app.save_notes
app.update()
check('an Undo of sixty notes moved to the Trash brings all sixty back',
      len(app.notes) == 60 and not app.trash)
check('...writing each file once, the notes before the trash',
      _nt_writes == ['notes', 'trash'])

# The Trash's rows hold the entries they were drawn for. After a restore
# made from outside the panel, a stale row's Restore brought back a
# second copy, and its Delete destroyed the file the restored note showed.
app.notes = []; app.save_notes()
_nt_file = 'qa3_stale_row.txt'
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
with open(os.path.join(NO.ATTACHMENTS_DIR, _nt_file), 'w') as _fh:
    _fh.write('keep me')


def _nt_trashed():
    return dict(NO.normalize_note({
        'id': 1, 'title': 'Holiday plans', 'body': 'x',
        'attachments': [{'name': 'plan.txt', 'stored_as': _nt_file}]}),
        deleted_at='2026-09-30 10:00:00')


app.trash = [_nt_trashed()]; NO.save_trash(app.trash)
app.show_settings_page(); app.toggle_settings_panel('trash'); app.update()
_nt_restore = find_btn(_trash_rows()[0], 'Restore')
app._restore_trash_entries(list(app.trash)); app.update()
_nt_restore.invoke(); app.update()
check("a stale Trash row's Restore does not bring a second copy back",
      len([n for n in app.notes if n['title'] == 'Holiday plans']) == 1)
app.notes = []; app.save_notes()
app.trash = [_nt_trashed()]; NO.save_trash(app.trash)
app.toggle_settings_panel('trash'); app.update()
_nt_delete = find_btn(_trash_rows()[0], 'Delete')
app._restore_trash_entries(list(app.trash)); app.update()
_nt_delete.invoke(); app.update()
check("...and its Delete leaves the restored note's file on disk",
      os.path.isfile(os.path.join(NO.ATTACHMENTS_DIR, _nt_file)))
# ...and the toast's Undo redraws the rows itself, so none goes stale.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Undone', 'body': 'x'})]
app.save_notes()
app.trash = []; NO.save_trash(app.trash)
_nt_marks = [(e.get('id'), e.get('deleted_at'))
             for e in app._move_notes_to_trash(list(app.notes))]
app.notes = []; app.save_notes()
app.toggle_settings_panel('trash'); app.update()
_nt_rows_before = len(_trash_rows())
app._undo_trash(_nt_marks); app.update()
check("the toast's Undo takes the note's row off an open Trash panel",
      _nt_rows_before == 1 and not _trash_rows())
app.hide_settings_page(); app.update()
app.trash = []; NO.save_trash(app.trash)
app.notes = []; app.save_notes()

# The status line after a delete says how long the Trash really keeps a
# note: it said "30 days" to someone who had chosen seven.
NO.save_setting('trash_retention_days', 7)
app.notes = [NO.normalize_note({'id': 1, 'title': 'Short-lived', 'body': 'x'})]
app.save_notes()
app._delete_note(app.find_note(1), None)
app.update()
check('the status after a delete names the retention actually chosen',
      '7 days' in str(app.status_lbl.cget('text')))
NO.save_setting('trash_retention_days', NO.TRASH_RETENTION_DAYS)
app.trash = []; NO.save_trash(app.trash)
app.notes = []; app.save_notes()

# Closing the window while a backup's worker has just finished: the
# main-thread poll that would have finished the job never runs again. An
# import's copied files were left belonging to no note, its unpacked
# backup stayed in the temp folder, and a finished export went unrecorded.
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
_cl_orphan = 'qa3_close_orphan.txt'
_cl_owned = 'qa3_close_owned.txt'
for _cl_name in (_cl_orphan, _cl_owned):
    with open(os.path.join(NO.ATTACHMENTS_DIR, _cl_name), 'w') as _fh:
        _fh.write('x')
app.notes = [NO.normalize_note({
    'id': 1, 'title': 'Owns a file', 'body': 'x',
    'attachments': [{'name': 'owned.txt', 'stored_as': _cl_owned}]})]
app.save_notes()
_cl_temp = tempfile.mkdtemp(prefix='qa3_close_')
app._import_state = {'phase': 'copying', 'current': 2, 'total': 2,
                     'done': True, 'error': None, 'temp_dir': _cl_temp,
                     'imported_notes': [], 'copied': [_cl_orphan, _cl_owned]}
app._export_state = {'current': 1, 'total': 1, 'done': True, 'error': None,
                     'save_path': 'unused'}
NO.save_setting('last_export_at', '')
_cl_destroy = app.destroy
app.destroy = lambda: None          # the close itself, not the window
app.on_app_close()
del app.destroy
app.update()
check('closing on a finished import drops the files it copied for no note',
      not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _cl_orphan)))
check('...keeps a file a note uses',
      os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _cl_owned)))
check('...and removes the unpacked backup from the temp folder',
      not os.path.exists(_cl_temp))
check('closing on a finished export records it as the last one',
      bool(NO.get_setting('last_export_at', '')))
app._import_state = None
app._export_state = None
app.notes = []; app.save_notes()
# ...and on a REAL import: its worker copies the backup's files in, and
# the window closes before the main thread ever merges the notes.
import shutil as _ri_shutil
_ri_dir = tempfile.mkdtemp(prefix='qa3_ri_')
_ri_name = 'qa3_ri_attached.txt'
os.makedirs(os.path.join(_ri_dir, 'attachments'))
with open(os.path.join(_ri_dir, 'attachments', _ri_name), 'w') as _fh:
    _fh.write('from the backup')
with open(os.path.join(_ri_dir, 'notes_data.json'), 'w') as _fh:
    json.dump([{'title': 'Came with a file', 'body': 'x',
                'attachments': [{'name': 'a.txt', 'stored_as': _ri_name}]}], _fh)
_ri_zip = os.path.join(tempfile.gettempdir(), 'qa3_real_import_close.zip')
with zipfile.ZipFile(_ri_zip, 'w') as _zf:
    _zf.write(os.path.join(_ri_dir, 'notes_data.json'), 'notes_data.json')
    _zf.write(os.path.join(_ri_dir, 'attachments', _ri_name),
              'attachments/' + _ri_name)
_ri_shutil.rmtree(_ri_dir, ignore_errors=True)
fd.askopenfilename = lambda **k: _ri_zip
# import_data() polls once on its way out, and a worker that is already done
# by then is merged on the spot: a CI runner finished this tiny backup that
# fast, and there was no unmerged import left to close on. The poll that
# would merge it is held off, so the close below meets what it is about.
app._poll_import_progress = lambda: None
app.import_data()
_ri_state = app._import_state
t0 = time.time()
while (_ri_state is not None and not _ri_state['done']
       and time.time() - t0 < 120):
    time.sleep(0.05)   # no update(): the main-thread merge must not run
check('fixture: the import worker copied the backup file in',
      _ri_state is not None and _ri_state['done']
      and os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _ri_name)))
_ri_temp = (_ri_state or {}).get('temp_dir')
app.destroy = lambda: None
app.on_app_close()
del app.destroy
app.update()
check('...closing before its merge leaves no file behind that no note owns',
      not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _ri_name)))
check('...and no unpacked backup in the temp folder',
      not (_ri_temp and os.path.exists(_ri_temp)))
del app._poll_import_progress
os.remove(_ri_zip)
app._import_state = None
app.notes = []; app.save_notes()

# ...and on an import still working: the close stops it at once, between
# two chunks, where it waited 30 s and the process then died mid-file. A
# huge file is a read or write held until the stop is asked (_Held).
from noteorganizer.core import sharing as _hs
_held = {'on': None, 'seen': False}


class _Held(_hs.StoppableFile):
    def _check(self):
        if (_held['on'] and not _held['seen']
                and str(getattr(self._raw, 'name', '')).endswith(_held['on'])):
            _held['seen'] = True
            t0 = time.time()
            while not self._stop() and time.time() - t0 < 20:
                time.sleep(0.01)
            time.sleep(0.3)        # the disk still finishes its chunk
        super()._check()


_kept_stoppable = (NO.StoppableFile, _hs.StoppableFile)
NO.StoppableFile = _hs.StoppableFile = _Held
_hb_name = 'qa3_held_film.bin'
_hb_zip = os.path.join(tempfile.gettempdir(), 'qa3_held_import.zip')
with zipfile.ZipFile(_hb_zip, 'w') as _zf:
    _zf.writestr('notes_data.json', json.dumps([{
        'title': 'Film', 'body': 'x',
        'attachments': [{'name': 'film.bin', 'stored_as': _hb_name}]}]))
    _zf.writestr('attachments/' + _hb_name, b'film' * 1000)
_he_zip = os.path.join(tempfile.gettempdir(), 'qa3_held_export.zip')
fd.askopenfilename = lambda **k: _hb_zip
# What was cut short is said at the next start: a closing window cannot,
# and nothing said it before -- the work simply looked done.
NO.save_setting('backup_cut_short', None)
app.destroy = lambda: None
app.on_app_close()
del app.destroy
check('a close with no backup running leaves no word for the next start',
      NO.get_setting('backup_cut_short') is None)
app._export_state = {'current': 1, 'total': 1, 'done': True, 'error': None,
                     'save_path': _he_zip}
app._settle_background_work_at_close()
check('...nor one whose export finished in time',
      NO.get_setting('backup_cut_short') is None and app._export_state is None)
_said = []
_kept_info = app.show_info


def _next_start_says():
    _said.clear()
    app.show_info = lambda *a, **k: _said.append(' '.join(map(str, a)))
    try:
        app.announce_startup_changes()
    finally:
        app.show_info = _kept_info
    return ' '.join(_said)


# ...but one finished as the window closed that held only the session's notes,
# or left a held file out, was recorded as the notebook's backup, whole, and
# nothing said otherwise. What its message would have said, the
# next start says; a backup of the session alone is not remembered.
NO.save_setting('last_export_at', None)
app._export_state = {'current': 1, 'total': 1, 'done': True, 'error': None,
                     'save_path': _he_zip, 'session_only': 2, 'left_out': []}
app._settle_background_work_at_close()
_pe_session = (NO.get_setting('last_export_at'), _next_start_says())
app._export_state = {'current': 1, 'total': 1, 'done': True, 'error': None,
                     'save_path': _he_zip, 'left_out': ['20250101_tax.xlsx']}
app._settle_background_work_at_close()
_pe_left = (NO.get_setting('last_export_at') is not None, _next_start_says())
check(f'an export of the session alone, finished at the close, is not taken for the '
      f'backup, and the next start says what it holds ({_pe_session[0]}, '
      f'{_pe_session[1][:90]!r})',
      _pe_session[0] is None and 'holds only the 2 notes' in _pe_session[1])
check(f'...and one that left a held file out says so at the next start '
      f'({_pe_left[1][:120]!r})',
      _pe_left[0] and 'not all of it' in _pe_left[1] and '20250101_tax.xlsx' in _pe_left[1]
      and NO.get_setting('backup_cut_short') is None)
NO.save_setting('last_export_at', None)

app._poll_import_progress = lambda: None
try:
    for _hb_phase, _hb_marker in (('unpacking', 'qa3_held_import.zip'),
                                  ('copying', _hb_name)):
        _held.update(on=_hb_marker, seen=False)
        app.import_data()
        t0 = time.time()
        while not _held['seen'] and time.time() - t0 < 10:
            time.sleep(0.02)
        _hb_temp = (app._import_state or {}).get('temp_dir')
        _hb_part = os.path.join(NO.ATTACHMENTS_DIR, _hb_name + '.part')
        check(f'fixture: an import is held mid-{_hb_phase}',
              _held['seen'] and (_hb_phase == 'unpacking' or os.path.exists(_hb_part)))
        app.destroy = lambda: None
        t0 = time.time()
        app.on_app_close()
        _hb_took = time.time() - t0
        del app.destroy
        check(f'closing the window stops an import held mid-{_hb_phase} at once '
              f'({_hb_took:.1f} s)', _hb_took < 5)
        check(f'...leaving no unpacked backup in the temp folder ({_hb_phase})',
              not (_hb_temp and os.path.exists(_hb_temp)))
        check(f'...and nothing of it among the attachments ({_hb_phase})',
              not os.path.exists(_hb_part)
              and not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _hb_name)))
        # Done or not, the word names what it copied and unpacked: the cleanup
        # after it takes time too.
        _hb_word = dict(NO.get_setting('backup_cut_short') or {})
        check(f'...and it leaves word for the next start, naming what it unpacked ({_hb_phase}, {_hb_word!r})',
              _hb_word.get('kind') == 'import' and _hb_word.get('file') == _hb_zip
              and 'when' not in _hb_word and isinstance(_hb_word.get('copied'), list)
              and _hb_word.get('temp_dir') == _hb_temp)
        _words = _next_start_says()
        check(f'the next start says the import was cut short, nothing kept, '
              f'and to import it again ({_words[:140]!r})',
              'qa3_held_import.zip' in _words and 'nothing from it was kept' in _words
              and 'import it again' in _words)
        check('...once', NO.get_setting('backup_cut_short') is None
              and 'cut short' not in _next_start_says())
        app._import_state = None
    # An export still writing when the close stops waiting is stopped the
    # same way, and takes its unfinished file away.
    with open(_he_zip, 'wb') as _fh:
        _fh.write(b'OLD-BACKUP-BYTES')
    fd.asksaveasfilename = lambda **k: _he_zip
    _held.update(on='qa3_held_export.zip.tmp', seen=False)
    app.export_data()
    t0 = time.time()
    while not _held['seen'] and time.time() - t0 < 10:
        time.sleep(0.02)
    check('fixture: an export is held mid-write, its .tmp on disk',
          _held['seen'] and os.path.exists(_he_zip + '.tmp'))
    app._wait_for_io_workers(cap_s=0.5)
    check('an export still writing when the close stops waiting is stopped, '
          'its unfinished file taken away',
          not os.path.exists(_he_zip + '.tmp'))
    with open(_he_zip, 'rb') as _fh:
        check('...and the earlier backup is left as it was',
              _fh.read() == b'OLD-BACKUP-BYTES')
    app._settle_background_work_at_close()
    # With the file's state as it was ("before"), to tell at the next start
    # an export that landed after all.
    _he_cut = dict(NO.get_setting('backup_cut_short') or {})
    _he_before = _he_cut.pop('before', 'none kept')
    check(f'...and the export cut short leaves word for the next start ({_he_cut!r}, {_he_before!r})',
          _he_cut == {'kind': 'export', 'file': _he_zip} and _he_before != 'none kept')
    _words = _next_start_says()
    check(f'the next start says no new backup was made, and to export again '
          f'({_words[:140]!r})',
          'qa3_held_export.zip' in _words and 'no new backup was made' in _words
          and 'export again' in _words)
finally:
    NO.StoppableFile, _hs.StoppableFile = _kept_stoppable
    del app._poll_import_progress
    for _t in getattr(app, '_io_workers', []):
        _t.join(25)
    app._import_state = None
    app._export_state = None
for _p in (_he_zip, _he_zip + '.tmp'):
    if os.path.exists(_p):
        os.remove(_p)
app.notes = []; app.save_notes()


@contextlib.contextmanager
def _fx_no_import():
    """No import in the way while the export checks below run: export_data
    refuses one while an import's state is held, and the settles they call
    read an import's state as well as the export's."""
    was = (getattr(app, '_import_asking', None), app._import_state)
    app._import_asking, app._import_state = None, None
    try:
        yield
    finally:
        app._import_asking, app._import_state = was


def _fx_start_export():
    """export_data, its own first look at the worker held back: the checks
    below drive the poll themselves. A worker that failed or finished in
    that instant was seen done there, its message shown and its state gone
    before a check could read it -- red, or a crash, one run in three."""
    app._poll_export_progress = lambda: None
    try:
        app.export_data()
    finally:
        del app._poll_export_progress


# An export that FAILED on its own as the window closed, its error never
# shown, was said at the next start as one the close had cut short.
# Here it fails as a folder gone does: the worker cannot open its file.
NO.save_setting('backup_cut_short', None)
_fx_zip = os.path.join(os.getcwd(), 'qa3_no_such_folder', 'qa3_failed_export.zip')
fd.asksaveasfilename = lambda **k: _fx_zip
_fx_start_export()
for _t in getattr(app, '_io_workers', []):
    _t.join(25)
_fx_seen = {k: v for k, v in (app._export_state or {}).items()
            if k in ('done', 'error', 'stop', 'phase')}
check(f'fixture: the export failed on its own, not stopped by a close ({_fx_seen!r}, '
      f'import {app._import_state is not None}, status {app.status_lbl.cget("text")[:60]!r})',
      bool(app._export_state and app._export_state.get('done')
           and app._export_state.get('error') and not app._export_state.get('stop')))
app._settle_background_work_at_close()
_fx_cut = NO.get_setting('backup_cut_short') or {}
check(f'an export that failed as the window closed is recorded as failed, '
      f'with its reason ({_fx_cut!r})',
      _fx_cut.get('kind') == 'export_failed' and _fx_cut.get('file') == _fx_zip
      and _fx_cut.get('error'))
_fx_words = _next_start_says()
check(f'...and the next start says it failed, and why, not that the close '
      f'cut it short ({_fx_words[:160]!r})',
      'qa3_failed_export.zip failed as Note Organizer closed' in _fx_words
      and 'no new backup was made' in _fx_words and 'cut short' not in _fx_words
      and str(_fx_cut.get('error'))[:20] in _fx_words)
check('...once', NO.get_setting('backup_cut_short') is None)
try:
    app.after_cancel(app._export_poll_job)
except (tk.TclError, ValueError, AttributeError):
    pass
app._export_state = None


# The same failure just before Windows ends the session: the session's own
# settle recorded only an export still writing, and this one went unsaid.
NO.save_setting('backup_cut_short', None)
with _fx_no_import():
    _fx_start_export()
    for _t in getattr(app, '_io_workers', []):
        _t.join(25)
    _fx_session_ready = bool(app._export_state and app._export_state.get('done')
                             and app._export_state.get('error'))
    app._settle_backups_at_session_end()
_fx_cut = NO.get_setting('backup_cut_short') or {}
_fx_words = _next_start_says()
check(f'an export that failed just before the session ended is said at the next start, and why '
      f'({_fx_session_ready}, {_fx_cut!r}, {_fx_words[:160]!r})',
      _fx_session_ready and _fx_cut.get('kind') == 'export_failed'
      and 'qa3_failed_export.zip failed as Windows began to sign out or shut down' in _fx_words
      and 'cut short' not in _fx_words
      and bool(_fx_cut.get('error')) and str(_fx_cut.get('error'))[:20] in _fx_words)
try:
    app.after_cancel(app._export_poll_job)
except (tk.TclError, ValueError, AttributeError):
    pass
app._export_state = None


def _fx_session_then_poll(fail_after):
    """An export, Windows' question about ending the session, the question
    cancelled, then the export's own poll: what the poll said, with the word
    for the next start as it stood when the poll spoke."""
    NO.save_setting('backup_cut_short', None)
    with _fx_no_import():
        _fx_start_export()
        # Finished before "still writing" is faked: a live worker could set
        # done between the mark and the settle, and the settle saw it done.
        for _t in getattr(app, '_io_workers', []):
            _t.join(25)
        if fail_after:
            app._export_state['done'] = False       # still writing at the question
        app._settle_backups_at_session_end()
    if fail_after:
        app._export_state['done'] = True
    said, err_was = [], app.show_error
    # The word as it stands while the message is up: its kind, whether it
    # carries the reason the next start would give, and that it still says
    # the session's end (a word written afresh would say the window closed).
    app.show_error = lambda *a, **k: said.append(
        (a[0] if a else '', (NO.get_setting('backup_cut_short') or {}).get('kind'),
         bool((NO.get_setting('backup_cut_short') or {}).get('error')),
         (NO.get_setting('backup_cut_short') or {}).get('when')))
    try:
        app._poll_export_progress()
    finally:
        app.show_error = err_was
    try:
        app.after_cancel(app._export_poll_job)
    except (tk.TclError, ValueError, AttributeError):
        pass
    return said


# The session's question cancelled after the export failed: the settle had
# dropped the export, so its bar stayed frozen, "Export failed" was never
# said, and the next start told of a sign-out that never came.
_fx_said = _fx_session_then_poll(fail_after=False)
check(f'a session that goes on after a failed export still says it, hides the bar and leaves '
      f'no word for the next start ({_fx_said!r}, {NO.get_setting("backup_cut_short")!r})',
      _fx_said == [('Export failed', 'export_failed', True, 'session')]
      and not app._is_placed(app.export_progress_frame)
      and NO.get_setting('backup_cut_short') is None)
# Still writing at the question, failed after it: the poll took the word back
# before it looked at the error, and the failure, shown as Windows signed
# out, was said by nobody at the next start.
_fx_said = _fx_session_then_poll(fail_after=True)
check(f'an export that fails after the session\'s question is a failure in the word while its '
      f'message is up, with its reason and the session\'s end, and the word goes once it is read '
      f'({_fx_said!r})',
      _fx_said == [('Export failed', 'export_failed', True, 'session')]
      and NO.get_setting('backup_cut_short') is None)
app._export_state = None
# Finished just before the question, its poll not yet run, a file left out:
# the session's settle recorded nothing, where the close stamps "Last
# exported" and names what was left out.
NO.save_setting('backup_cut_short', None)
NO.save_setting('last_export_at', None)
fd.asksaveasfilename = lambda **k: os.path.join(os.getcwd(), 'qa3_session_done.zip')
with _fx_no_import():
    _fx_start_export()
    for _t in getattr(app, '_io_workers', []):
        _t.join(25)
    _fx_done = bool(app._export_state and app._export_state.get('done') and not app._export_state.get('error'))
    if _fx_done:
        app._export_state['left_out'] = ['20261113090000000001_held.bin']
    app._settle_backups_at_session_end()
_fx_cut = NO.get_setting('backup_cut_short') or {}
_fx_stamped = NO.get_setting('last_export_at')
_fx_info, _fx_info_was = [], app.show_info
app.show_info = lambda *a, **k: _fx_info.append(a[0] if a else '')
try:
    app._poll_export_progress()
finally:
    app.show_info = _fx_info_was
check(f'an export finished just before the session\'s question is recorded as the close records '
      f'it, and the poll takes the word back if the session goes on ({_fx_done}, {_fx_cut.get("kind")!r}, '
      f'{_fx_stamped!r}, {_fx_info!r})',
      _fx_done and _fx_cut.get('kind') == 'export_partial' and _fx_cut.get('when') == 'session'
      and bool(_fx_stamped) and _fx_info == ['Export complete, but not all of it']
      and NO.get_setting('backup_cut_short') is None)
NO.save_setting('backup_cut_short', dict(_fx_cut))
_fx_words = _next_start_says()
check(f'...and said at the next start as Windows signing out, not as the window closing '
      f'({_fx_words[:140]!r})',
      'qa3_session_done.zip finished as Windows began to sign out or shut down, but not all of it'
      in _fx_words)
try:
    app.after_cancel(app._export_poll_job)
except (tk.TclError, ValueError, AttributeError):
    pass
app._export_state = None
# ...and a partial export's word, like a failure's, is kept until its message
# is read: taken back first, the session's end that followed said nothing of
# the files left out.
NO.save_setting('backup_cut_short', None)
with _fx_no_import():
    _fx_start_export()
    for _t in getattr(app, '_io_workers', []):
        _t.join(25)                          # finished first, as above
    app._export_state['done'] = False        # still writing at the question
    app._settle_backups_at_session_end()
app._export_state['done'] = True
app._export_state['left_out'] = ['20261113090000000002_held.bin']
_fx_info, _fx_info_was = [], app.show_info
app.show_info = lambda *a, **k: _fx_info.append(
    (a[0] if a else '', (NO.get_setting('backup_cut_short') or {}).get('kind')))
try:
    app._poll_export_progress()
finally:
    app.show_info = _fx_info_was
check(f'a partial export\'s word is kept, as a partial one, while its message is up, and goes once read '
      f'({_fx_info!r}, {NO.get_setting("backup_cut_short")!r})',
      _fx_info == [('Export complete, but not all of it', 'export_partial')]
      and NO.get_setting('backup_cut_short') is None)
try:
    app.after_cancel(app._export_poll_job)
except (tk.TclError, ValueError, AttributeError):
    pass
app._export_state = None
# The close waits up to half a minute for an export, the window held: its
# word was written only after the wait, so a close ended there (Not
# Responding, a forced shut-down) said nothing, and the .tmp stayed.
NO.save_setting('backup_cut_short', None)
_fx_long = threading.Event()
_fx_at_wait = {}


class _FxWorker(threading.Thread):
    def join(self, timeout=None):
        # Read as the wait begins: what a window ended inside it leaves.
        # Read after the wait, a word written after it passed too.
        _fx_at_wait.setdefault('word', NO.get_setting('backup_cut_short'))
        return super().join(timeout)


_fx_worker = _FxWorker(target=_fx_long.wait, args=(3.0,), daemon=True)
_fx_worker.start()
_fx_workers_was = getattr(app, '_io_workers', [])
app._io_workers = [_fx_worker]
app._export_state = {'done': False, 'stop': False, 'error': None, 'current': 0, 'total': 1,
                     'save_path': os.path.join(os.getcwd(), 'qa3_close_wait.zip')}
try:
    app._wait_for_io_workers(cap_s=0.2)
    _fx_cut = _fx_at_wait.get('word') or {}
finally:
    _fx_long.set()
    app._io_workers = _fx_workers_was
    app._export_state = None
check(f'a close that waits for an export writes its word before the wait ({_fx_cut!r})',
      _fx_cut.get('kind') == 'export' and _fx_cut.get('file', '').endswith('qa3_close_wait.zip')
      and 'before' in _fx_cut)
# The word's file changed since (the export landed after all): said finished,
# not "no new backup was made" -- export again would have replaced the only copy.
with open(os.path.join(os.getcwd(), 'qa3_close_wait.zip'), 'wb') as _fh:
    _fh.write(b'landed')
_fx_words = _next_start_says()
check(f'...and an export that landed after the word is said finished, not cut short ({_fx_words[:140]!r})',
      'qa3_close_wait.zip finished as Note Organizer closed. Open it' in _fx_words
      and 'cut short' not in _fx_words)
NO.save_setting('backup_cut_short', {'kind': 'export', 'file': os.path.join(os.getcwd(), 'qa3_close_wait.zip'),
                                     'before': os.path.getmtime(os.path.join(os.getcwd(), 'qa3_close_wait.zip'))})
_fx_words = _next_start_says()
check(f'...while one whose file did not change is said cut short ({_fx_words[:120]!r})',
      'qa3_close_wait.zip was cut short when Note Organizer closed' in _fx_words)
# The usual case: an older backup of the same name, replaced by the export
# that landed (its time changed since the word), is said finished too.
_fx_cw = os.path.join(os.getcwd(), 'qa3_close_wait.zip')
NO.save_setting('backup_cut_short', {'kind': 'export', 'file': _fx_cw,
                                     'before': os.path.getmtime(_fx_cw) - 60})
_fx_words = _next_start_says()
check(f'...as is one that replaced an older backup of the same name ({_fx_words[:120]!r})',
      'qa3_close_wait.zip finished as Note Organizer closed' in _fx_words)
# The word kept until the start has asked the export's file: taken first, a
# start frozen on a share that is gone, and ended there, lost it.
NO.save_setting('backup_cut_short', {'kind': 'export', 'file': _fx_cw, 'before': 1.0})
_fx_at_ask, _fx_landed_was = {}, app._export_landed_after


def _fx_landed(cut):
    _fx_at_ask['word'] = NO.get_setting('backup_cut_short')
    return _fx_landed_was(cut)


app._export_landed_after = _fx_landed
try:
    _next_start_says()
finally:
    del app._export_landed_after
check(f'the start keeps the word until it has asked the export\'s file, then takes it back ({_fx_at_ask!r})',
      bool(_fx_at_ask.get('word')) and NO.get_setting('backup_cut_short') is None)
# An import's word too, before the wait: a large file's flush to disk can
# hold it, and a window ended there left the files it copied unnamed.
NO.save_setting('backup_cut_short', None)
_fx_at_wait.clear()
_fx_long = threading.Event()
_fx_worker = _FxWorker(target=_fx_long.wait, args=(3.0,), daemon=True)
_fx_worker.start()
_fx_workers_was, _fx_import_was = getattr(app, '_io_workers', []), app._import_state
_fx_copied = ['20261113100000000001_a.bin', '20261113100000000002_b.bin.part']
app._io_workers = [_fx_worker]
app._import_state = {'done': False, 'stop': False, 'copied': list(_fx_copied),
                     'zip': os.path.join(os.getcwd(), 'qa3_close_wait_import.zip'),
                     'temp_dir': os.path.join(tempfile.gettempdir(), 'notes_import_qa3_wait')}
try:
    app._wait_for_io_workers(cap_s=0.2)
    _fx_cut = _fx_at_wait.get('word') or {}
finally:
    _fx_long.set()
    app._io_workers, app._import_state = _fx_workers_was, _fx_import_was
check(f'a close that waits for an import writes its word before the wait, what it copied named ({_fx_cut!r})',
      _fx_cut.get('kind') == 'import' and _fx_cut.get('copied') == _fx_copied
      and str(_fx_cut.get('temp_dir', '')).endswith('notes_import_qa3_wait'))
NO.save_setting('backup_cut_short', None)
# Done but not merged when the window closes, no worker left to wait for:
# only the close's settle names it, and takes its unpacked folder out.
_fx_import_was = app._import_state
_fx_dir = tempfile.mkdtemp(prefix='notes_import_qa3_done_')
app._import_state = {'done': True, 'stop': False, 'copied': ['20261113110000000001_c.bin'],
                     'zip': os.path.join(os.getcwd(), 'qa3_done_import.zip'), 'temp_dir': _fx_dir}
try:
    app._settle_background_work_at_close()
    _fx_cut = dict(NO.get_setting('backup_cut_short') or {})
finally:
    app._import_state = _fx_import_was
check(f'an import done but not merged at the close leaves word naming what it copied ({_fx_cut!r})',
      _fx_cut.get('kind') == 'import' and _fx_cut.get('copied') == ['20261113110000000001_c.bin']
      and not os.path.exists(_fx_dir))
NO.save_setting('backup_cut_short', None)
# A word that named a file as ".part" (still flushing when it was written):
# renamed after, it stayed for good. Its own name goes too, unless in use.
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
# Its case kept, as a stored name keeps the file's ("<stamp>_Photo.JPG").
_fx_free, _fx_used = '20261113120000000001_film.bin', '20261113120000000002_Kept.bin'
for _n in (_fx_free, _fx_used):
    with open(os.path.join(NO.ATTACHMENTS_DIR, _n), 'wb') as _fh:
        _fh.write(b'x')
_fx_notes_was = app.notes
app.notes = _fx_notes_was + [NO.normalize_note({'title': 'Uses it', 'attachments': [
    {'name': 'kept.bin', 'stored_as': _fx_used}]})]
try:
    app._drop_unclaimed_import_files({'copied': [_fx_free + '.part', _fx_used + '.part']})
finally:
    app.notes = _fx_notes_was
check('a file named as ".part" in an import\'s word is taken out by its own name, one a note uses kept',
      not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _fx_free))
      and os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _fx_used)))
# A word another program wrote can name a note's file through an alias, as
# Windows reads names: a trailing dot or space dropped (in a name cut from
# ".part" too), another case, an 8.3 short name. On Linux each is another
# file, and the note's file is never at stake.
_fx_tried, _fx_remove_was = [], os.remove


def _fx_short_name(path):
    """Windows' 8.3 name for *path*, or None (Linux, or short names off)."""
    if os.name != 'nt':
        return None
    import ctypes
    buf = ctypes.create_unicode_buffer(520)
    if not ctypes.windll.kernel32.GetShortPathNameW(path, buf, 520):
        return None
    short = os.path.basename(buf.value)
    return short if short != os.path.basename(path) else None


_fx_aliases = [_fx_used + '.', _fx_used + ' ', _fx_used + '. .', _fx_used + '..part',
               _fx_used + ' .part', _fx_used + '. .part', _fx_used.upper(), _fx_used.lower()]
_fx_short = _fx_short_name(os.path.join(NO.ATTACHMENTS_DIR, _fx_used))
if _fx_short:
    _fx_aliases += [_fx_short, _fx_short + '.part']


def _fx_remove(path, *a, **k):
    _fx_tried.append(os.path.basename(path))
    return _fx_remove_was(path, *a, **k)


app.notes = _fx_notes_was + [NO.normalize_note({'title': 'Uses it', 'attachments': [
    {'name': 'kept.bin', 'stored_as': _fx_used}]})]
os.remove = _fx_remove
try:
    app._drop_unclaimed_import_files({'copied': list(_fx_aliases)})
finally:
    os.remove = _fx_remove_was
    app.notes = _fx_notes_was
check(f"...and a name in the word that is an alias of a note's file is never taken out "
      f"(short name {_fx_short!r}; tried {_fx_tried})",
      os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _fx_used)))
# Gone only when a broken guard took it: a red here stays a red, not a crash.
if os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _fx_used)):
    os.remove(os.path.join(NO.ATTACHMENTS_DIR, _fx_used))
fd.asksaveasfilename = lambda **k: _fx_zip
# An error without words (a MemoryError's) read as none: "Export complete",
# "Last exported" stamped, and no file written.
NO.save_setting('backup_cut_short', None)
_fx_ok_zip = os.path.join(os.getcwd(), 'qa3_wordless_error.zip')
fd.asksaveasfilename = lambda **k: _fx_ok_zip
_fx_check_was = NO.backup_entries_problem


def _fx_out_of_memory(_infos):
    raise MemoryError()


NO.backup_entries_problem = _fx_out_of_memory
try:
    with _fx_no_import():
        _fx_start_export()
        for _t in getattr(app, '_io_workers', []):
            _t.join(25)
finally:
    NO.backup_entries_problem = _fx_check_was
_fx_error = (app._export_state or {}).get('error')
_fx_failed_said, _fx_error_was = [], app.show_error
app.show_error = lambda *a, **k: _fx_failed_said.append(a[0] if a else '')
try:
    app._poll_export_progress()
finally:
    app.show_error = _fx_error_was
check(f'an export whose error has no words is said failed, and no file is put in place '
      f'({_fx_error!r}, {_fx_failed_said!r}, {os.path.exists(_fx_ok_zip)})',
      _fx_error == 'MemoryError' and _fx_failed_said == ['Export failed']
      and not os.path.exists(_fx_ok_zip))
try:
    app.after_cancel(app._export_poll_job)
except (tk.TclError, ValueError, AttributeError):
    pass
app._export_state = None

# The end of a Windows session is a question the person can still cancel
# (Tk answers WM_QUERYENDSESSION with it), so it tears down nothing the app
# needs if the session goes on. It stopped the export and dropped the import
# outright, behind a progress bar that never moved again. A file is held
# until the test lets it go (_sx['go']).
_sx = {'on': None, 'seen': False, 'go': False}


class _HeldTillGo(_hs.StoppableFile):
    def _check(self):
        if (_sx['on'] and not _sx['seen']
                and str(getattr(self._raw, 'name', '')).endswith(_sx['on'])):
            _sx['seen'] = True
            t0 = time.time()
            while not _sx['go'] and not self._stop() and time.time() - t0 < 20:
                time.sleep(0.01)
        super()._check()


def _sx_wait(cond, cap=10):
    t0 = time.time()
    while not cond() and time.time() - t0 < cap:
        app.update()
        time.sleep(0.02)


NO.StoppableFile = _hs.StoppableFile = _HeldTillGo
_sx_info = []
app.show_info = lambda *a, **k: _sx_info.append(a[0] if a else '')
try:
    NO.save_setting('backup_cut_short', None)
    fd.asksaveasfilename = lambda **k: _he_zip
    _sx.update(on='qa3_held_export.zip.tmp', seen=False, go=False)
    app.export_data()
    _sx_wait(lambda: _sx['seen'])
    t0 = time.time()
    app.on_session_end()
    _sx_took = time.time() - t0
    check(f'the end of a Windows session leaves an export writing, and does not '
          f'wait for it ({_sx_took:.1f} s)',
          _sx['seen'] and app._export_state is not None and _sx_took < 2)
    _he_cut = dict(NO.get_setting('backup_cut_short') or {})
    _he_before = _he_cut.pop('before', 'none kept')
    check(f'...leaving word for the next start in case the session does end ({_he_cut!r})',
          _he_cut == {'kind': 'export', 'file': _he_zip, 'when': 'session'} and _he_before != 'none kept')
    _sx['go'] = True
    _sx_wait(lambda: app._export_state is None)
    check(f'...and a session that goes on sees it finish: said, and the word for '
          f'the next start taken back ({_sx_info})',
          'Export complete' in _sx_info and os.path.exists(_he_zip)
          and NO.get_setting('backup_cut_short') is None
          and app.export_progress_frame.winfo_manager() == '')
    # An import is stopped and dropped -- killed half-copied it leaves files
    # no note points at -- and the screen says so at once.
    with zipfile.ZipFile(_hb_zip, 'w') as _zf:
        _zf.writestr('notes_data.json', json.dumps([{
            'title': 'Film', 'body': 'x',
            'attachments': [{'name': 'film.bin', 'stored_as': _hb_name}]}]))
        _zf.writestr('attachments/' + _hb_name, b'film' * 1000)
    fd.askopenfilename = lambda **k: _hb_zip
    _sx.update(on=_hb_name, seen=False, go=False)
    app.import_data()
    _sx_wait(lambda: _sx['seen'])
    _sx_temp = (app._import_state or {}).get('temp_dir')
    app.on_session_end(); app.update()
    check(f'the end of a Windows session stops an import and says so at once '
          f'({app.status_lbl.cget("text")[:60]!r})',
          _sx['seen'] and app._import_state is None
          and app.export_progress_frame.winfo_manager() == ''
          and 'stopped as Windows' in str(app.status_lbl.cget('text')))
    check('...leaving nothing of it behind',
          not (_sx_temp and os.path.exists(_sx_temp))
          and not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _hb_name))
          and not any(n.get('title') == 'Film' for n in app.notes))
    # Named what it copied and unpacked, kept through the cleanup.
    _sx_word = dict(NO.get_setting('backup_cut_short') or {})
    check(f'...and word for the next start, naming what it copied and unpacked ({_sx_word!r})',
          {k: _sx_word.get(k) for k in ('kind', 'file', 'when')}
          == {'kind': 'import', 'file': _hb_zip, 'when': 'session'}
          and isinstance(_sx_word.get('copied'), list) and _sx_word.get('temp_dir') == _sx_temp)
    _words = _next_start_says()
    check(f'the next start says Windows cut it short ({_words[:120]!r})',
          'qa3_held_import.zip' in _words and 'when Windows began to sign out' in _words)
    # ...and a re-import that finishes takes that word back: it said "nothing
    # was kept" after the person had done just what it asked.
    NO.save_setting('backup_cut_short',
                    {'kind': 'import', 'file': _hb_zip, 'when': 'session'})
    _sx.update(on=None)
    _sx_real_dlg = app._themed_dialog
    app._themed_dialog = lambda *a, **k: True
    try:
        app.import_data()
        _sx_wait(lambda: app._import_state is None, 15)
        app.update()
    finally:
        app._themed_dialog = _sx_real_dlg
    check('...and an import that then finishes takes that word back',
          NO.get_setting('backup_cut_short') is None
          and any(n.get('title') == 'Film' for n in app.notes))
    # An export the process died in leaves its unfinished file beside the
    # target; the next start that says so takes it away.
    with open(_he_zip + '.tmp', 'wb') as _fh:
        _fh.write(b'half')
    NO.save_setting('backup_cut_short',
                    {'kind': 'export', 'file': _he_zip, 'when': 'session'})
    _words = _next_start_says()
    check('the next start says an export was cut short by Windows, and takes '
          'its unfinished file away',
          'when Windows began to sign out' in _words and not os.path.exists(_he_zip + '.tmp'))
    # A session that ends while an import's question waits found no import
    # running: the files it had copied and its unpacked backup stayed, and
    # nothing was said. Word for the next start, which takes them out.
    _sq_film = next(n for n in app.notes if n.get('title') == 'Film')
    _sq_name = '20261029120000000001_cut.bin'
    with zipfile.ZipFile(_hb_zip, 'w') as _zf:
        _zf.writestr('notes_data.json', json.dumps([{
            'uid': _sq_film['uid'], 'title': 'Film', 'body': 'edited elsewhere',
            'created': _sq_film.get('created'),
            'attachments': [{'name': 'cut.bin', 'stored_as': _sq_name}]}]))
        _zf.writestr('attachments/' + _sq_name, b'cut' * 1000)
    _sq_seen = {}

    def _sq_dialog(*a, **k):
        if k.get('kind') != 'question' or 'already have' not in (a[0] if a else ''):
            return True
        app.on_session_end()
        _sq_seen['said'] = NO.get_setting('backup_cut_short')
        _sq_seen['file'] = os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _sq_name))
        return 'cancel'
    app._themed_dialog = _sq_dialog
    app._ending_session = False
    _sq_real_copy = NO.copy_file_until_stopped

    def _sq_copy(src, dst, stop):
        # What a process ended inside the copy would leave named.
        _sq_seen.setdefault('during', list((app._import_state or {}).get('copied') or []))
        return _sq_real_copy(src, dst, stop)
    NO.copy_file_until_stopped = _sq_copy
    try:
        app.import_data()
        _sx_wait(lambda: app._import_state is None, 15)
        app.update()
    finally:
        NO.copy_file_until_stopped = _sq_real_copy
        app._themed_dialog = _sx_real_dlg
        app._ending_session = False
    check(f'an import names the file it is copying while the copy runs '
          f'({_sq_seen.get("during")})',
          _sq_seen.get('during') == [_sq_name + '.part'])
    _sq_said = _sq_seen.get('said') or {}
    check(f'a session ending while an import asks leaves word naming what it copied, '
          f'and keeps the files for the answer ({sorted(_sq_said)}, {_sq_seen.get("file")})',
          _sq_said.get('kind') == 'import' and _sq_said.get('copied') == [_sq_name]
          and _sq_said.get('temp_dir') and _sq_seen.get('file') is True)
    check('...a session that goes on takes the word back with the answer',
          NO.get_setting('backup_cut_short') is None
          and not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _sq_name)))
    # The session ended after all: the files stayed, and the next start
    # takes them out, the Film note's own file untouched. Named here when the
    # word above left none, so a broken record fails this check, not the run.
    _sq_temp = _sq_said.get('temp_dir') or os.path.join(
        tempfile.gettempdir(), 'notes_import_qa3_session')
    os.makedirs(_sq_temp, exist_ok=True)
    with open(os.path.join(NO.ATTACHMENTS_DIR, _sq_name), 'wb') as _fh:
        _fh.write(b'cut')
    NO.save_setting('backup_cut_short', dict(
        {'kind': 'import', 'file': _hb_zip, 'when': 'session'}, **_sq_said))
    _words = _next_start_says()
    check(f'...and when it ended, the next start takes them out and says so '
          f'({_words[:60]!r})',
          'when Windows began to sign out' in _words
          and not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _sq_name))
          and not os.path.exists(_sq_temp)
          and os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _hb_name)))
    _ri_shutil.rmtree(_sq_temp, ignore_errors=True)
    if os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _sq_name)):
        os.remove(os.path.join(NO.ATTACHMENTS_DIR, _sq_name))
    # A session that ends while "Import complete" is on screen: the merge is
    # saved, yet the next start said the import kept nothing and asked for it
    # again. No word is left once the merge is saved.
    with zipfile.ZipFile(_hb_zip, 'w') as _zf:
        _zf.writestr('notes_data.json', json.dumps([{
            'uid': 'qa3-done-at-session-end', 'title': 'Done at sign-out', 'body': 'kept'}]))
    _ic_seen = {}

    def _ic_info(title, *a, **k):
        if title == 'Import complete':
            app.on_session_end()
            _ic_seen['said'] = NO.get_setting('backup_cut_short')
    app.show_info = _ic_info
    app._themed_dialog = lambda *a, **k: True
    app._ending_session = False
    try:
        app.import_data()
        _sx_wait(lambda: app._import_state is None, 15)
        app.update()
    finally:
        app._themed_dialog = _sx_real_dlg
        app._ending_session = False
    check(f'a session ending while "Import complete" is on screen leaves no word of an '
          f'import cut short ({_ic_seen})',
          'said' in _ic_seen and _ic_seen['said'] is None
          and any(n.get('title') == 'Done at sign-out' for n in app.notes))
    # A backup moving in a notebook from the phone's 0.13.0 -- a series turned
    # off and on as it was, the blank-looking day deleted -- makes a note of
    # the copy's words for that day, and "Import complete" says so: its banner
    # went under the dialog (found on the phone first).
    with zipfile.ZipFile(_hb_zip, 'w') as _zf:
        _zf.writestr('notes_data.json', json.dumps([{
            'uid': 'qa3-older-series', 'title': 'Gym older', 'body': 'plan', 'date': '2026-11-02',
            'recurrence': {'freq': 'weekly'}, 'exceptions': ['2026-11-09'],
            '_prev': {'title': 'Gym older', 'body': 'plan', 'comments': '', 'formatting': [],
                      'paragraphs': [], 'date': '2026-11-02', 'recurrence': {'freq': 'weekly'},
                      'exceptions': [], 'moved': {}, 'overrides': {'2026-11-09': {'body': 'knee'}}}}]))
    _et_said = []
    _et_info = app.show_info
    app.show_info = lambda title, msg='', *a, **k: _et_said.append((title, msg))
    app._themed_dialog = lambda *a, **k: True
    try:
        app.import_data()
        _sx_wait(lambda: app._import_state is None, 15)
        app.update()
    finally:
        app._themed_dialog = _sx_real_dlg
        app.show_info = _et_info
    check(f'"Import complete" says the earlier text a backup\'s series kept as a note ({_et_said})',
          any(t == 'Import complete' and 'Earlier text of 1 day of a repeating note' in m for t, m in _et_said)
          and any(n.get('title') == 'Gym older (earlier text)' and n.get('body') == 'knee' for n in app.notes))
    # An import's worker held past the session end's join (a file another
    # program holds): its word named nothing it copied or unpacked.
    app._import_state = {'zip': _hb_zip, 'done': False, 'stop': False,
                         'copied': ['20261030010000000001_held.bin'],
                         'temp_dir': os.path.join(tempfile.gettempdir(), 'notes_import_qa3_held')}
    try:
        app._settle_backups_at_session_end()
        _hw_said = NO.get_setting('backup_cut_short') or {}
    finally:
        app._import_state = None
    check(f'a session ending while an import is held mid-copy names what it copied '
          f'and unpacked ({sorted(_hw_said)})',
          _hw_said.get('copied') == ['20261030010000000001_held.bin']
          and _hw_said.get('temp_dir', '').endswith('notes_import_qa3_held'))
    # ...and the window closed while one still runs past the close's wait:
    # its word named neither, and the next start took nothing out.
    app._import_state = {'zip': _hb_zip, 'done': False, 'stop': True,
                         'copied': ['20261030010000000001_held.bin'],
                         'temp_dir': os.path.join(tempfile.gettempdir(), 'notes_import_qa3_held')}
    _hw_export_was, app._export_state = app._export_state, None
    try:
        app._settle_background_work_at_close()
        _hw_said = NO.get_setting('backup_cut_short') or {}
    finally:
        app._import_state, app._export_state = None, _hw_export_was
    NO.save_setting('backup_cut_short', None)
    check(f'a close while an import still runs past its wait names what it copied '
          f'and unpacked ({sorted(_hw_said)})',
          _hw_said.get('copied') == ['20261030010000000001_held.bin']
          and _hw_said.get('temp_dir', '').endswith('notes_import_qa3_held'))
    # A start that could not read the notes keeps those files (a file the
    # notes use would look free) -- and kept no word either, so no later start
    # took them out. The word stays, said once.
    _uw_name = '20261030010000000002_left.bin'
    with open(os.path.join(NO.ATTACHMENTS_DIR, _uw_name), 'wb') as _fh:
        _fh.write(b'left')
    # Its unpacked folder too, which holds no file a note uses: that one goes
    # at once, readable or not.
    _uw_dir = os.path.join(tempfile.gettempdir(), 'notes_import_qa3_unread')
    os.makedirs(_uw_dir, exist_ok=True)
    NO.save_setting('backup_cut_short', {'kind': 'import', 'file': _hb_zip,
                                         'when': 'session', 'copied': [_uw_name],
                                         'temp_dir': _uw_dir})
    _uw_real = app._notes_file_unread
    app._notes_file_unread = lambda: True
    try:
        _uw_first = _next_start_says()
        _uw_kept = NO.get_setting('backup_cut_short') or {}
        _uw_there = os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _uw_name))
        _uw_dir_gone = not os.path.exists(_uw_dir)
    finally:
        app._notes_file_unread = _uw_real
        _ri_shutil.rmtree(_uw_dir, ignore_errors=True)
    check(f'a start that cannot read the notes takes an import\'s unpacked folder out at once '
          f'({_uw_dir_gone})', _uw_dir_gone)
    _uw_second = _next_start_says()
    # Three checks, not one: a failure names the promise that broke.
    check(f'a start that cannot read the notes keeps the word for an import cut short, and its files '
          f'({sorted(_uw_kept)}, file kept: {_uw_there})',
          'was cut short' in _uw_first and _uw_kept.get('copied') == [_uw_name] and _uw_there)
    check(f'a start that cannot read the notes says an import cut short once '
          f'(said again at the next start: {"was cut short" in _uw_second})',
          'was cut short' not in _uw_second)
    check('after a start that cannot read the notes, the next start takes the cut-short import\'s '
          'files out and lowers its word',
          not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _uw_name))
          and NO.get_setting('backup_cut_short') is None)
    # ...and so does one that read the notes but not the Trash: its files kept too.
    with open(os.path.join(NO.ATTACHMENTS_DIR, _uw_name), 'wb') as _fh:
        _fh.write(b'left')
    NO.save_setting('backup_cut_short', {'kind': 'import', 'file': _hb_zip,
                                         'when': 'session', 'copied': [_uw_name]})
    NO._core_paths.hold_writes(NO.TRASH_FILE)
    try:
        _ut_first = _next_start_says()
        _ut_kept = NO.get_setting('backup_cut_short') or {}
        _ut_there = os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _uw_name))
    finally:
        NO._core_paths.WRITES_HELD.discard(os.path.normcase(os.path.abspath(NO.TRASH_FILE)))
    _ut_second = _next_start_says()
    check(f'a start that cannot read the Trash keeps the word for an import cut short, and its files '
          f'({sorted(_ut_kept)}, file kept: {_ut_there})',
          'was cut short' in _ut_first and _ut_kept.get('copied') == [_uw_name] and _ut_there)
    check(f'a start that cannot read the Trash says an import cut short once '
          f'(said again at the next start: {"was cut short" in _ut_second})',
          'was cut short' not in _ut_second)
    check('after a start that cannot read the Trash, the next start takes the cut-short import\'s '
          'files out and lowers its word',
          not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _uw_name))
          and NO.get_setting('backup_cut_short') is None)
    # "Import failed" on screen when a session ends: Windows ends the app with
    # the dialog up, and the unpacked folder, removed only after it, stayed in
    # the temp folder for good, the word lowered before it.
    _if_dir = tempfile.mkdtemp(prefix='notes_import_qa3_failed_')
    _if_seen = {}
    _if_real_err = app.show_error
    app.show_error = lambda *a, **k: _if_seen.setdefault('there', os.path.exists(_if_dir))
    try:
        app._merge_finished_import({'error': 'qa3: the zip could not be read', 'stop': False,
                                    'temp_dir': _if_dir, 'copied': []})
    finally:
        app.show_error = _if_real_err
    check(f'"Import failed" is said with its unpacked folder already gone ({_if_seen})',
          _if_seen.get('there') is False and not os.path.exists(_if_dir))
finally:
    _sx['go'] = True
    NO.StoppableFile, _hs.StoppableFile = _kept_stoppable
    app.show_info = _kept_info
    for _t in getattr(app, '_io_workers', []):
        _t.join(25)
    app._import_state = None
    app._export_state = None
for _p in (_hb_zip, _he_zip, _he_zip + '.tmp'):
    if os.path.exists(_p):
        os.remove(_p)
app.notes = []; app.save_notes()

# A double-click on a Trash row's Restore restores that one note. The
# second press used to land on the row that slid up into its place when
# the first redrew the list, and restored that note too -- the checklist
# bin's hazard (qa1), and the same guard. Delivered as a pointer delivers
# it, at explicit screen points and times.
from _qa_support import fire as _dc_fire
app.trash = [
    dict(NO.normalize_note({'id': 1, 'title': 'Newer', 'body': 'x'}),
         deleted_at='2026-09-30 11:00:00'),
    dict(NO.normalize_note({'id': 2, 'title': 'Older', 'body': 'y'}),
         deleted_at='2026-09-30 10:00:00')]
NO.save_trash(app.trash)
app.show_settings_page(); app.toggle_settings_panel('trash'); app.update()


def _dc_restore(t, x=400, y=300):
    rows = _trash_rows()
    btn = find_btn(rows[0], 'Restore') if rows else None
    if btn is None:
        return
    _dc_fire(btn, '<Enter>')
    _dc_fire(btn, '<ButtonPress-1>', x=5, y=5, rootx=x, rooty=y, time=t)
    _dc_fire(btn, '<ButtonRelease-1>', x=5, y=5, rootx=x, rooty=y, time=t + 60)
    app.update()


_dc_restore(200000)
check('fixture: the first click of a double-click restores the top row',
      [n['title'] for n in app.notes] == ['Newer'])
_dc_restore(200250)
check('a double-click on a Trash row restores one note, not the next one too',
      [n['title'] for n in app.notes] == ['Newer'] and len(app.trash) == 1)
_dc_restore(201500)
check('...while a click of its own, later, still restores',
      sorted(n['title'] for n in app.notes) == ['Newer', 'Older'])
# Double-clicking "Restore N selected": the second press landed on Empty
# trash, slid up into its place, and asked to delete the rest.
app.trash = [dict(NO.normalize_note({'id': 3, 'title': 'Ticked', 'body': 'z'}),
                  deleted_at='2026-09-30 12:00:00'),
             dict(NO.normalize_note({'id': 4, 'title': 'Left', 'body': 'w'}),
                  deleted_at='2026-09-30 09:00:00')]
NO.save_trash(app.trash)
app.toggle_settings_panel('statistics'); app.toggle_settings_panel('trash'); app.update()
_rs_rows = _trash_rows()
_rs_tick = next((c for c in _rs_rows[0].winfo_children() if isinstance(c, tk.Checkbutton)), None) if _rs_rows else None
if _rs_tick is not None:
    _rs_tick.invoke(); app.update()
_rs_asked = []
_rs_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (_rs_asked.append(a[0]), False)[1]
try:
    for _rs_label, _rs_t in (('↩ Restore 1 selected', 202000), ('Empty trash', 202250)):
        _rs_btn = find_btn(app, _rs_label)
        if _rs_btn is not None:
            _dc_fire(_rs_btn, '<Enter>')
            _dc_fire(_rs_btn, '<ButtonPress-1>', x=5, y=5, rootx=420, rooty=330, time=_rs_t)
            _dc_fire(_rs_btn, '<ButtonRelease-1>', x=5, y=5, rootx=420, rooty=330, time=_rs_t + 60)
            app.update()
finally:
    app.ask_yes_no = _rs_ask
check(f"a double-click on Restore selected does not answer Empty trash ({_rs_asked}, {len(app.trash)})",
      _rs_tick is not None and 'Empty trash' not in _rs_asked and len(app.trash) == 1)
app.hide_settings_page(); app.update()
app.trash = []; NO.save_trash(app.trash)
app.notes = []; app.save_notes()

# Enter answers a question now (qa9), so a confirmation whose keyboard
# sits on Yes deletes on a reflexive Enter. The three that move notes to
# the Trash put it on No. Answered No here, so nothing moves.
_dn_asked = {}
_dn_said = {}
_dn_stub = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (_dn_asked.__setitem__(a[0], k.get('default')),
                                  _dn_said.__setitem__(a[0], a[1]), False)[2]
app.notes = [NO.normalize_note({'id': 1, 'title': 'Keep me', 'body': 'x'}),
             NO.normalize_note({'id': 2, 'title': 'Keep me', 'body': 'x'})]
app.save_notes()
app._delete_note(app.find_note(1), None)
app.selected_note_ids = {1}
app._bulk_move_to_trash()
app.selected_note_ids = set()


class _DnVar:
    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v


_dn_group = [app.find_note(1), app.find_note(2)]
app._cleanup_selected_duplicates(
    [(_DnVar(False), _dn_group[0], _dn_group), (_DnVar(True), _dn_group[1], _dn_group)],
    refresh=lambda: None)
app.ask_yes_no = _dn_stub
check('the confirmations that move notes to the Trash keep the keyboard on No (%s)'
      % _dn_asked,
      _dn_asked == {'Delete note': 'no', 'Move to trash': 'no',
                    'Move duplicates to trash': 'no'}
      and len(app.notes) == 2 and not app.trash)
# "Are you sure you want to delete this note?" read as gone for good, while
# the ticked delete beside it named the Trash and the days (the review panel).
check(f"...and a note's own Delete says it goes to the Trash and can be restored "
      f"({_dn_said.get('Delete note')!r})",
      (_dn_said.get('Delete note') or '').startswith('Move this note to the Trash? You can restore it')
      and 'Move 1 selected note to the trash? You can restore it' in (_dn_said.get('Move to trash') or ''))
app.notes = []; app.save_notes()

# ---- A DAY'S EDIT SAVED THIS SESSION IS NOT "EDITED ELSEWHERE" ----
# The occurrence save wrote the day's edit raw -- with an empty colour the
# load drops -- and the import compared that raw copy with the backup's
# normalised one. A backup holding this very note asked "already here,
# edited elsewhere", and Update spent the note's rescue copy on nothing.
app.open_blank_tab(); app.update()
app.trash = []; NO.save_trash(app.trash)
_ie_note = NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'every monday',
                              'date': '2026-09-07',
                              'recurrence': {'freq': 'weekly'}})
_ie_note['_prev'] = {'title': 'Weekly', 'body': 'THE ORIGINAL LONG TEXT',
                     'formatting': [], 'paragraphs': [], 'comments': ''}
app.notes = [_ie_note]; app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
app.title_entry.delete(0, 'end'); app._insert_title('Weekly (moved to 10:00)')
_ie_scope = app.ask_occurrence_scope
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app._flush_autosave(); app.update()
app.ask_occurrence_scope = _ie_scope
_ie_mem = app.find_note(1)
check("fixture: the edit is saved as that day's own",
      (_ie_mem['overrides'].get('2026-09-14') or {}).get('title')
      == 'Weekly (moved to 10:00)')
# The day, shared from here, travels as a note of that date: the series'
# identity and repeat went with the day's words, and an Update on the other
# device wrote that one day over the whole series.
app.share_current_note_as_code(copy=True); app.update()
_sc_day = NO.decode_share_code(app.clipboard_get())[0]
check(f"a day of a series shares as a note of that date, not as the series "
      f"({_sc_day.get('date')!r}, {(_sc_day.get('recurrence') or {}).get('freq')!r}, "
      f"{_sc_day.get('uid')!r})",
      _sc_day.get('date') == '2026-09-14'
      and not (_sc_day.get('recurrence') or {}).get('freq')
      and not _sc_day.get('uid')
      and _sc_day.get('title') == 'Weekly (moved to 10:00)')
check(f"a day's edit held in memory is the edit a restart reads back "
      f"({_ie_mem['overrides']})",
      _ie_mem['overrides']
      == NO.normalize_note(json.loads(json.dumps(_ie_mem)))['overrides'])
_ie_raw = dict(_ie_mem, overrides={'2026-09-14': dict(
    _ie_mem['overrides']['2026-09-14'], color='')})
check('...and an import compares a raw copy in memory like with like',
      not NO.shared_update_changes(_ie_raw, json.loads(json.dumps(_ie_raw)),
                                   NO.UPDATABLE_FROM_BACKUP))
_iezip = os.path.join(tempfile.gettempdir(), 'qa3_identical_backup.zip')
if os.path.exists(_iezip):
    os.remove(_iezip)
fd.asksaveasfilename = lambda **k: _iezip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()
_ie_asked = []
_ie_real_dlg = app._themed_dialog
app._themed_dialog = lambda *a, **k: (_ie_asked.append(a[0]), 'update')[1]
fd.askopenfilename = lambda **k: _iezip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
app._themed_dialog = _ie_real_dlg
check(f'importing a backup holding that note exactly as it is offers no '
      f'update, only whether to add a copy ({_ie_asked})',
      not any('already have' in t for t in _ie_asked)
      and [t for t in _ie_asked if t != 'Import notes']
      == ['Already here, unchanged'])
check('...and the rescue copy is untouched',
      len(app.notes) == 1
      and (app.find_note(1).get('_prev') or {}).get('body')
      == 'THE ORIGINAL LONG TEXT')
# The same backup again, answering "Add copies anyway": a second, separate
# note, with an identity of its own -- and no look-alike question after it,
# for the notes it was just asked about by name.
_ie_asked = []
app._themed_dialog = lambda *a, **k: (_ie_asked.append(a[0]), 'copies')[1]
_ie_info = []
_ie_real_info = app.show_info
app.show_info = lambda *a, **k: _ie_info.append(a[1])
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 120:
    app.update()
app._themed_dialog = _ie_real_dlg
app.show_info = _ie_real_info
_ie_uids = [n.get('uid') for n in app.notes]
check(f'"Add copies anyway" adds the note again as its own note '
      f'({_ie_asked}; {_ie_info})',
      [t for t in _ie_asked if t != 'Import notes']
      == ['Already here, unchanged'] and len(app.notes) == 2
      and len(set(_ie_uids)) == 2 and all(_ie_uids)
      and app.notes[1]['title'] == app.notes[0]['title']
      and any('Added 1 note from the backup.' in s for s in _ie_info))
if os.path.exists(_iezip):
    os.remove(_iezip)

# ---- YOUR OWN BACKUP AGAIN, WITH A FILE: EVERY ANSWER, END TO END ----
# The overlap the import's claimed-file rule exists for: the backup's note
# is the note already here, and its file is the file already here. Each
# answer must leave every note owning a file of its own and no file owned
# by nobody -- or deleting one note for good takes the other's file with
# it. The rule was covered through its helper and by review; this walks the
# real export and import, worker thread and Recently deleted included.
app.open_blank_tab(); app.update()
app.trash = []; NO.save_trash(app.trash)
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
_ra_file = 'qa3_reimport_receipt.txt'
with open(os.path.join(NO.ATTACHMENTS_DIR, _ra_file), 'w', encoding='utf-8') as _fh:
    _fh.write('the receipt')
app.notes = [NO.normalize_note({
    'id': 1, 'title': 'Receipts', 'body': 'March',
    'attachments': [{'filename': 'receipt.txt', 'stored_as': _ra_file}]})]
app.save_notes()
_ra_uid = app.notes[0]['uid']
_ra_zip = os.path.join(tempfile.gettempdir(), 'qa3_reimport_attached.zip')
if os.path.exists(_ra_zip):
    os.remove(_ra_zip)
fd.asksaveasfilename = lambda **k: _ra_zip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 120:
    app.update()
check('fixture: the backup holding the note and its file is written',
      os.path.isfile(_ra_zip))


def _ra_files():
    return sorted(os.listdir(NO.ATTACHMENTS_DIR))


def _ra_import(answer):
    """Import the backup, answering every question with *answer*; returns
    the questions' titles."""
    asked = []
    real_dlg, real_info = app._themed_dialog, app.show_info
    app._themed_dialog = lambda *a, **k: (
        asked.append(a[0]),
        _ra_focus.append((a[0], k['buttons'][app._dialog_focus_index(k['buttons'], k.get('default'))][0])),
        answer)[2]
    app.show_info = lambda *a, **k: None
    fd.askopenfilename = lambda **k: _ra_zip
    try:
        app.import_data()
        t0 = time.time()
        while app._import_state is not None and time.time() - t0 < 120:
            app.update()
    finally:
        app._themed_dialog, app.show_info = real_dlg, real_info
    return asked


_ra_focus = []      # (question, the button Enter presses), every import


def _ra_owned(note):
    return [a.get('stored_as') for a in note.get('attachments') or []]


_ra_before = _ra_files()
_ra_asked = _ra_import('skip')
check(f'your own backup with a file again asks only "already here" ({_ra_asked})',
      _ra_asked == ['Already here, unchanged'])
check('..."Skip it" leaves one note, its file, and no file nobody owns',
      len(app.notes) == 1 and _ra_owned(app.notes[0]) == [_ra_file]
      and _ra_files() == _ra_before)

_ra_import('copies')
_ra_copy = next((n for n in app.notes if n.get('uid') != _ra_uid), None)
_ra_copy_file = (_ra_owned(_ra_copy) or [None])[0] if _ra_copy else None
check('..."Add a copy anyway" gives the copy a file of its own',
      len(app.notes) == 2 and _ra_copy_file and _ra_copy_file != _ra_file
      and os.path.isfile(os.path.join(NO.ATTACHMENTS_DIR, _ra_copy_file)))
with open(os.path.join(NO.ATTACHMENTS_DIR, _ra_copy_file or _ra_file),
          encoding='utf-8') as _fh:
    _ra_copy_text = _fh.read()
check("...holding the backup's file as it was", _ra_copy_text == 'the receipt')
# A copy with no file of its own fails here rather than stops the script:
# sorting None among the names raised, and three mutants that the checks
# above had caught read as NO-RUN.
check('...and no file owned by nobody',
      _ra_copy_file is not None
      and sorted(set(_ra_before) | {_ra_copy_file}) == _ra_files())

# The copy deleted for good, from Settings -> Recently deleted, the way a
# person does it: the original's file must survive. With no copy made (as
# under a mutant), there is nothing to delete, and the checks below fail.
if _ra_copy is not None:
    app._delete_note(_ra_copy, None)
app.update()
app.show_settings_page(); app.update()
app.toggle_settings_panel('trash'); app.update()


def _ra_delete_button(w):
    for c in w.winfo_children():
        if isinstance(c, tk.Button) and str(c.cget('text')) == 'Delete':
            return c
        found = _ra_delete_button(c)
        if found is not None:
            return found
    return None


_ra_del = _ra_delete_button(app.settings_trash_panel)
check('fixture: the trashed copy has its Delete button', _ra_del is not None)
if _ra_del is not None:
    _ra_del.invoke()
    app.update()
app.hide_settings_page(); app.update()
check('deleting the copy for good removes its file',
      _ra_copy_file and not os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _ra_copy_file)))
check("...and leaves the original's file where it was",
      os.path.isfile(os.path.join(NO.ATTACHMENTS_DIR, _ra_file))
      and _ra_owned(app.find_note(1) or {}) == [_ra_file])

# Edited here since the backup, then updated from it: the backup's file is
# the one the note already has, so nothing is attached twice and nothing is
# left behind.
_ra_note = app.find_note(1)
_ra_note['body'] = 'March, paid'
_ra_note['updated'] = '2099-01-01 00:00:00'
app.save_notes()
# Cancel on its question says so: asked while the person may be typing, a
# stray Enter ended the import without a word.
app.set_status('')
_ra_import('cancel')
# ...and the autosave's "Auto-saved" that follows the person's typing does
# not write over it (it did, within a second).
app.set_status('Auto-saved 10:00', reassurance=True)
check(f"an import cancelled at its question says nothing was added ({app.status_lbl.cget('text')!r})",
      app.status_lbl.cget('text') == app._IMPORT_CANCELLED
      and (app.find_note(1) or {}).get('body') == 'March, paid')
_ra_before = _ra_files()
_ra_asked = _ra_import('update')
_ra_note = next((n for n in app.notes if n.get('uid') == _ra_uid), {})
check(f'an edited note offers Update ({_ra_asked})',
      _ra_asked == ['1 note you already have'])
# Asked from a timer once the backup is unpacked, while the person may be
# typing: a stray Space or Enter answered it, and the notes were replaced.
check(f'...and Enter there replaces nothing: Cancel holds the focus ({_ra_focus[-1:]})',
      _ra_focus[-1:] == [('1 note you already have', 'Cancel')])
# Every question with buttons of its own names the one Enter presses: left
# to the dialog, Enter pressed the last, which replaced or deleted.
import ast as _dq_ast
_dq_root = os.path.dirname(os.path.abspath(NO.__file__))
_dq_missing = []
for _dq_rel in ['note_organizer.py'] + ['noteorganizer/ui/' + _f for _f in
                                        sorted(os.listdir(os.path.join(_dq_root, 'noteorganizer', 'ui')))
                                        if _f.endswith('.py')]:
    _dq_src = open(os.path.join(_dq_root, _dq_rel), encoding='utf-8').read()
    for _dq_n in _dq_ast.walk(_dq_ast.parse(_dq_src)):
        if (isinstance(_dq_n, _dq_ast.Call) and isinstance(_dq_n.func, _dq_ast.Attribute)
                and _dq_n.func.attr == '_themed_dialog'):
            _dq_kw = {k.arg: k.value for k in _dq_n.keywords}
            _dq_b = _dq_kw.get('buttons')
            if (isinstance(_dq_b, (_dq_ast.List, _dq_ast.Tuple)) and len(_dq_b.elts) > 1
                    and 'default' not in _dq_kw):
                _dq_missing.append('%s:%d' % (_dq_rel, _dq_n.lineno))
check(f'every question with buttons of its own names the one Enter presses ({_dq_missing})',
      not _dq_missing)
_sc_focus = []
_sc_real = app._themed_dialog
app._themed_dialog = lambda *a, **k: (
    _sc_focus.append(k['buttons'][app._dialog_focus_index(k['buttons'], k.get('default'))][0]), None)[1]
try:
    app.ask_occurrence_scope('Delete', '2026-11-10')
finally:
    app._themed_dialog = _sc_real
check(f'deleting one day of a series: Enter keeps everything ({_sc_focus})', _sc_focus == ['Cancel'])
check('..."Update" attaches the shared file once, and leaves no file behind',
      len(app.notes) == 1 and _ra_owned(_ra_note) == [_ra_file]
      and _ra_files() == _ra_before)
os.remove(_ra_zip)

# A backup whose copy of the note lists one new file twice -- hand-edited,
# or written by a build that had that slip. Loading a note keeps a repeated
# attachment as it is, so the update itself must attach the file once.
_ra_scan = 'qa3_reimport_scan.txt'
_ra_note = next((n for n in app.notes if n.get('uid') == _ra_uid), {})
_ra_note['updated'] = '2099-01-01 00:00:00'
app.save_notes()
with zipfile.ZipFile(_ra_zip, 'w') as _zf:
    _zf.writestr('notes_data.json', json.dumps([{
        'id': 1, 'uid': _ra_uid, 'title': 'Receipts', 'body': 'March, scanned',
        'updated': '2026-01-01 00:00:00',
        'attachments': [{'filename': 'receipt.txt', 'stored_as': _ra_file},
                        {'filename': 'scan.txt', 'stored_as': _ra_scan},
                        {'filename': 'scan.txt', 'stored_as': _ra_scan}]}]))
    _zf.writestr('attachments/' + _ra_scan, 'the scan')
_ra_import('update')
_ra_note = next((n for n in app.notes if n.get('uid') == _ra_uid), {})
check('...and a backup listing one new file twice attaches it once',
      _ra_owned(_ra_note) == [_ra_file, _ra_scan])
os.remove(_ra_zip)
if os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _ra_scan)):
    os.remove(os.path.join(NO.ATTACHMENTS_DIR, _ra_scan))
app.notes = []; app.save_notes()
app.trash = []; NO.save_trash(app.trash)
for _ra_name in (_ra_file,):
    if os.path.exists(os.path.join(NO.ATTACHMENTS_DIR, _ra_name)):
        os.remove(os.path.join(NO.ATTACHMENTS_DIR, _ra_name))

# The one colour kept raw: "Reset to category" on a day of a COLOURED
# series. The stored form cannot hold it, and written as a load shapes it
# the editor's empty colour never matched the day's again -- an unsaved
# edit, and a question, at every exit.
app.open_blank_tab(); app.update()
app.notes = [NO.normalize_note({'id': 2, 'title': 'Coloured', 'body': 'x',
                                'color': '#cc3366', 'date': '2026-09-07',
                                'recurrence': {'freq': 'weekly'}})]
app.save_notes()
app.open_note_in_tab(app.find_note(2), occurrence_date='2026-09-14'); app.update()
app.open_color_picker(); app.update()
_ie_reset = find_btn(app._mini_popup, 'Reset to category') if app._mini_popup else None
if _ie_reset is not None:
    _ie_reset.invoke(); app.update()
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app._flush_autosave(); app.update()
app.ask_occurrence_scope = _ie_scope
check('fixture: the day of a coloured series had its colour reset and saved',
      _ie_reset is not None and app.current_note_color == ''
      and '2026-09-14' in app.find_note(2)['overrides'])
check('...and the day reads as saved afterwards, not as an edit forever',
      app.editor_state_matches_saved(app.capture_editor_state()))
app.open_blank_tab(); app.update()
app.notes = []; app.save_notes()

# ---- A BACKUP IMPORT THAT TAKES NOTHING LEAVES NO FILES BEHIND ----
# The worker copies a backup's files before anything is asked. Only the
# window's close removed them when the notes were never merged; Cancel on
# any of the import's questions, and skipping duplicates, left each file
# in the attachments folder belonging to nobody.
import shutil as _ic_shutil


def _ic_path(name):
    return os.path.join(NO.ATTACHMENTS_DIR, name)


def _ic_import(notes, files, answer, templates=None, settings=None):
    """Import a backup holding `notes`, the attachment `files` and any
    `templates` or `settings`, answering the import's own questions with
    `answer`."""
    src = tempfile.mkdtemp(prefix='qa3_ic_')
    os.makedirs(os.path.join(src, 'attachments'))
    for name in files:
        with open(os.path.join(src, 'attachments', name), 'w') as fh:
            fh.write('from the backup')
    with open(os.path.join(src, 'notes_data.json'), 'w') as fh:
        json.dump(notes, fh)
    zpath = os.path.join(tempfile.gettempdir(), 'qa3_import_takes_nothing.zip')
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, 'w') as zf:
        zf.write(os.path.join(src, 'notes_data.json'), 'notes_data.json')
        if templates is not None:
            zf.writestr('templates.json', json.dumps(templates))
        if settings is not None:
            zf.writestr('settings.json', json.dumps(settings))
        for name in files:
            zf.write(os.path.join(src, 'attachments', name), 'attachments/' + name)
    _ic_shutil.rmtree(src, ignore_errors=True)
    asked = []
    real = app._themed_dialog
    app._themed_dialog = lambda *a, **k: (asked.append(a[0]),
                                          answer(*a, **k) if callable(answer) else answer)[1]
    fd.askopenfilename = lambda **k: zpath
    app.import_data()
    t0 = time.time()
    while app._import_state is not None and time.time() - t0 < 120:
        app.update()
    app._themed_dialog = real
    os.remove(zpath)
    return asked


# A backup's categories the settings file refused are said not written, as
# its day markings are: "Also restored 1 category" read as kept, and their
# colours were gone at the next start.
app.open_blank_tab(); app.update()
app.notes = []; app.save_notes()
_cw_cats = sys.modules['noteorganizer.core.categories']
_cw_save_was, _cw_info_was, _cw_said = _cw_cats.save_settings, app.show_info, []
_cw_cats.save_settings = lambda _s: (False, OSError(28, 'No space left on device'))
app.show_info = lambda title, msg='', **k: _cw_said.append(msg)
try:
    _ic_import([{'title': 'Seedlings', 'body': 'tomatoes', 'category': 'Garden qa3'}], [],
               lambda *a, **k: (k.get('buttons') or [(None, True)])[-1][1],
               settings={'categories': {'Garden qa3': '#3a7d44'}})
finally:
    _cw_cats.save_settings, app.show_info = _cw_save_was, _cw_info_was
NO.CATEGORY_COLORS.pop('Garden qa3', None)
check(f"a backup's categories the settings file refused are said not written "
      f"({(_cw_said or [''])[-1][-140:]!r})",
      bool(_cw_said) and 'Also restored 1 category.' in _cw_said[-1]
      and 'The categories could not be written to disk; the backup still holds them' in _cw_said[-1])

app.open_blank_tab(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Groceries', 'body': 'milk'})]
app.trash = []
app.save_notes(); NO.save_trash(app.trash)
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
_ic_names = ['qa3_ic_dup.txt', 'qa3_ic_known.txt', 'qa3_ic_skip.txt',
             'qa3_ic_fresh.txt']
check('fixture: none of the backup files is in the attachments folder yet',
      not any(os.path.exists(_ic_path(n)) for n in _ic_names))
_ic_asked = _ic_import(
    [{'title': 'Groceries', 'body': 'milk',
      'attachments': [{'name': 'r.txt', 'stored_as': 'qa3_ic_dup.txt'}]}],
    ['qa3_ic_dup.txt'], 'cancel')
# A look-alike bringing a file its twin lacks is asked with Skip ('Possible
# duplicates'); Cancel there still keeps none.
check(f'Cancel on "all notes already imported" leaves no file no note owns '
      f'({_ic_asked})',
      any('already imported' in t or 'Possible duplicates' in t for t in _ic_asked)
      and not os.path.exists(_ic_path('qa3_ic_dup.txt')))
_ic_asked = _ic_import(
    [{'uid': app.find_note(1)['uid'], 'title': 'Groceries',
      'body': 'milk and eggs',
      'attachments': [{'name': 'k.txt', 'stored_as': 'qa3_ic_known.txt'}]}],
    ['qa3_ic_known.txt'], 'cancel')
check(f'...nor Cancel on "notes you already have" ({_ic_asked})',
      any('already have' in t for t in _ic_asked)
      and not os.path.exists(_ic_path('qa3_ic_known.txt'))
      and app.find_note(1)['body'].rstrip('\n') == 'milk')
_ic_asked = _ic_import(
    [{'title': 'Groceries', 'body': 'milk',
      'attachments': [{'name': 's.txt', 'stored_as': 'qa3_ic_skip.txt'}]},
     {'title': 'Fresh', 'body': 'new',
      'attachments': [{'name': 'f.txt', 'stored_as': 'qa3_ic_fresh.txt'}]}],
    ['qa3_ic_skip.txt', 'qa3_ic_fresh.txt'], 'skip')
_ic_fresh = [n for n in app.notes if n.get('title') == 'Fresh']
# Skipped, a look-alike's files go to the note it looks like: they were deleted
# with it, the date and files the twin lacked never brought in.
_ic_twin = [a.get('stored_as') for a in app.find_note(1).get('attachments') or []]
check(f"...and skipping the duplicates gives their files to the notes they look like ({_ic_asked}, {_ic_twin})",
      any('Possible duplicates' in t for t in _ic_asked)
      and 'qa3_ic_skip.txt' in _ic_twin
      and os.path.exists(_ic_path('qa3_ic_skip.txt')))
check('...while the note imported keeps its own file, on disk',
      len(_ic_fresh) == 1
      and [a.get('stored_as') for a in _ic_fresh[0].get('attachments') or []]
      == ['qa3_ic_fresh.txt']
      and os.path.exists(_ic_path('qa3_ic_fresh.txt')))
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
# ...and to the note open in the editor too: its next save put its own list of
# files back over the ones given.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Groceries', 'body': 'milk'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
_ic_import(
    [{'title': 'Groceries', 'body': 'milk',
      'attachments': [{'name': 's.txt', 'stored_as': 'qa3_ic_skip.txt'}]},
     {'title': 'Fresh', 'body': 'new'}],
    ['qa3_ic_skip.txt'], 'skip')
app.open_blank_tab(); app.update()
_ic_open = [a.get('stored_as') for a in app.find_note(1).get('attachments') or []]
check(f"...and to the note open in the editor, still there once it is left ({_ic_open})",
      'qa3_ic_skip.txt' in _ic_open)
# ...but "Go back and fix it" on the open note's date leaves it out: its save
# never made, the file given was read over by the typing.
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
app.notes = [NO.normalize_note({'id': 1, 'title': 'Groceries', 'body': 'milk'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
_ic_real_flush = app._flush_autosave
app._flush_autosave = lambda *a, **k: False
_ic_said = []
_ic_real_info = app.show_info
app.show_info = lambda *a, **k: (_ic_said.append(' '.join(str(x) for x in a)), True)[1]
_ic_asked = _ic_import(
    [{'title': 'Groceries', 'body': 'milk',
      'attachments': [{'name': 's.txt', 'stored_as': 'qa3_ic_skip.txt'}]},
     {'title': 'Fresh', 'body': 'new'}],
    ['qa3_ic_skip.txt'], 'skip')
app.show_info = _ic_real_info
app._flush_autosave = _ic_real_flush
_ic_open = [a.get('stored_as') for a in app.find_note(1).get('attachments') or []]
check(f"...but not when its save was sent back to fix a date ({_ic_asked}, {_ic_open})",
      any('Possible duplicates' in t for t in _ic_asked) and not _ic_open)
# ...which is said, with the note named: deleted unsaid, they were what Skip
# was offered for.
check(f"...and the files left out are said ({_ic_said[-1:]})",
      any('1 attached file for “Groceries” was not added' in s for s in _ic_said))
app._cancel_pending_autosave()
app.open_blank_tab(); app.update()
# ...and a look-alike bringing no file leaves the note open alone: read back
# for nothing, it lost its Ctrl+Z and its place.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Groceries', 'body': 'milk'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.insert('1.0', 'x'); app.body_text.edit_separator()
app.body_text.delete('1.0'); app.body_text.edit_separator()
_ic_asked = _ic_import([{'title': 'Groceries', 'body': 'milk'}, {'title': 'Fresh', 'body': 'new'}],
                       [], 'skip')
check(f"...and one bringing no file leaves the note open as it is, its Ctrl+Z too "
      f"({_ic_asked}, {app._can_edit_undo(app.body_text)})",
      any('Possible duplicates' in t for t in _ic_asked) and app._can_edit_undo(app.body_text))
app._cancel_pending_autosave()
app.open_blank_tab(); app.update()
# A backup of look-alikes that brings nothing but a file a twin lacks is
# offered Skip, which gives it the file: Cancel was the default, and deleted
# it.
app.notes = [NO.normalize_note({'id': 1, 'title': 'Groceries', 'body': 'milk'})]
app.save_notes()
_ic_offered = []


def _ic_skip_if_offered(*a, **k):
    labels = [label for label, _v in k.get('buttons') or []]
    _ic_offered.append(labels)
    return 'skip' if 'Skip them' in labels else 'cancel'


_ic_said = []
_ic_real_info = app.show_info
app.show_info = lambda *a, **k: (_ic_said.append(' '.join(str(x) for x in a)), True)[1]
_ic_import([{'title': 'Groceries', 'body': 'milk',
             'attachments': [{'name': 'd.txt', 'stored_as': 'qa3_ic_dup.txt'}]}],
           ['qa3_ic_dup.txt'], _ic_skip_if_offered)
app.show_info = _ic_real_info
_ic_only = [a.get('stored_as') for a in app.find_note(1).get('attachments') or []]
check(f"a backup of look-alikes bringing only a file a twin lacks offers Skip, which gives it "
      f"({_ic_offered}, {_ic_only})", 'qa3_ic_dup.txt' in _ic_only)
# ...and says so: "Added 0 note(s)" and nothing more read as nothing done.
check(f"...and the import says where the file went ({_ic_said[-1:]})",
      any('1 attached file went to the note the skipped ones look like' in s for s in _ic_said))
check(f"...and counts what it added in the form the number takes ({_ic_said[-1:]})",
      any('Added 0 notes from the backup.' in s for s in _ic_said))
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
# A backup's Update agreed to, its other notes all look-alikes: skipped, the
# Update still happens -- Cancel was the only no, and dropped it.
app.notes = [NO.normalize_note({'id': 1, 'uid': 'bk-known', 'title': 'Synced', 'body': 'first words'}),
             NO.normalize_note({'id': 2, 'title': 'Look alike', 'body': 'same words'})]
app.save_notes()
_bk_asked = []


def _bk_answer(*a, **k):
    labels = [label for label, _v in k.get('buttons') or []]
    _bk_asked.append(labels)
    return 'update' if 'Update it' in labels else ('skip' if 'Skip them' in labels else 'cancel')


_ic_import([{'uid': 'bk-known', 'title': 'Synced', 'body': 'second words'},
            {'title': 'Look alike', 'body': 'same words'}], [], _bk_answer)
check(f"a backup's Update agreed to, then look-alikes skipped: the Update still happens ({_bk_asked})",
      any('Skip them' in labels for labels in _bk_asked)
      and (app.find_note(1) or {}).get('body', '').rstrip('\n') == 'second words'
      and sum(1 for n in app.notes if n.get('title') == 'Look alike') == 1)
# ...and a skipped look-alike of the note as the Update leaves it gives that note its file: its
# twin was looked for in the notebook before the Update, none was found, and the file was
# dropped, where the phone gave it.
app.notes = [NO.normalize_note({'id': 1, 'uid': 'bk-known', 'title': 'Trip', 'body': 'old plan'})]
app.save_notes()
_bk_asked = []
_ic_import([{'uid': 'bk-known', 'title': 'Trip', 'body': 'new plan'},
            {'title': 'Trip (copy)', 'body': 'new plan',
             'attachments': [{'name': 'p.txt', 'stored_as': 'qa3_ic_skip.txt'}]}],
           ['qa3_ic_skip.txt'], _bk_answer)
_bk_files = [a.get('stored_as') for a in (app.find_note(1) or {}).get('attachments') or []]
check(f"...and a skipped look-alike of the note as the Update leaves it gives that note its file "
      f"({_bk_asked}, {_bk_files})",
      any('Skip them' in labels for labels in _bk_asked)
      and (app.find_note(1) or {}).get('body', '').rstrip('\n') == 'new plan'
      and 'qa3_ic_skip.txt' in _bk_files and len(app.notes) == 1)
# ...and of two notes here that look alike, the first in the file takes it, as on the phone:
# the same backup put the file on another note on each app.
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
app.notes = [NO.normalize_note({'id': 1, 'title': 'Trip', 'body': 'plan'}),
             NO.normalize_note({'id': 2, 'title': 'Trip (copy)', 'body': 'plan'})]
app.save_notes()
_bk_asked = []
_ic_import([{'title': 'Trip', 'body': 'plan',
             'attachments': [{'name': 'p.txt', 'stored_as': 'qa3_ic_skip.txt'}]}],
           ['qa3_ic_skip.txt'], _bk_answer)
_bk_where = [n.get('id') for n in app.notes
             if any(a.get('stored_as') == 'qa3_ic_skip.txt' for a in n.get('attachments') or [])]
check(f"...and of two look-alikes here the first in the file takes the file ({_bk_asked}, {_bk_where})",
      any('Skip them' in labels for labels in _bk_asked) and _bk_where == [1] and len(app.notes) == 2)
# ...and the files go after the updates: a photo the update brings and its Duplicate's copy (another
# stored name, the same bytes) is given once, by the update, which took files alone. Given first,
# the update read as "Updated 1 ... Restore previous undoes" for a note with no rescue copy.
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
app.notes = [NO.normalize_note({'id': 1, 'uid': 'bk-known', 'title': 'Trip', 'body': 'plan'})]
app.save_notes()
_bk_asked = []
_bk_said = []
_bk_real_info = app.show_info
app.show_info = lambda *a, **k: (_bk_said.append(' '.join(str(x) for x in a)), True)[1]
_ic_import([{'uid': 'bk-known', 'title': 'Trip', 'body': 'plan',
             'attachments': [{'filename': 'p.txt', 'stored_as': 'qa3_ic_known.txt'}]},
            {'title': 'Trip (copy)', 'body': 'plan',
             'attachments': [{'filename': 'p.txt', 'stored_as': 'qa3_ic_skip.txt'}]}],
           ['qa3_ic_known.txt', 'qa3_ic_skip.txt'], _bk_answer)
app.show_info = _bk_real_info
_bk_files = [a.get('stored_as') for a in (app.find_note(1) or {}).get('attachments') or []]
check(f"...and a file the update brings is given once, by the update, said as files alone "
      f"({_bk_asked}, {_bk_files}, {_bk_said[-1:]})",
      _bk_files == ['qa3_ic_known.txt']
      and any('1 note you already had took attached files' in s for s in _bk_said)
      and not any('Updated 1 note' in s or 'went to the note' in s for s in _bk_said))
# ...and a note typed into while the question waits (its autosave runs) still takes the file it was
# offered for: its twin worked out after the question had another key, and the file was dropped.
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
app.notes = [NO.normalize_note({'id': 1, 'title': 'Trip', 'body': 'plan'})]
app.save_notes()


def _bk_type_then_skip(*a, **k):
    labels = [label for label, _v in k.get('buttons') or []]
    app.find_note(1)['body'] = 'plan, and words typed while it asked'
    return 'skip' if 'Skip them' in labels else 'cancel'


_ic_import([{'title': 'Trip', 'body': 'plan',
             'attachments': [{'name': 'p.txt', 'stored_as': 'qa3_ic_skip.txt'}]}],
           ['qa3_ic_skip.txt'], _bk_type_then_skip)
_bk_files = [a.get('stored_as') for a in (app.find_note(1) or {}).get('attachments') or []]
check(f"...and a note typed into while the question waits still takes the file offered for it ({_bk_files})",
      _bk_files == ['qa3_ic_skip.txt'])
for _ic_name in _ic_names:
    if os.path.exists(_ic_path(_ic_name)):
        os.remove(_ic_path(_ic_name))
app.notes = [NO.normalize_note({'id': 1, 'uid': 'bk-known', 'title': 'Synced', 'body': 'second words'}),
             NO.normalize_note({'id': 2, 'title': 'Look alike', 'body': 'same words'})]
app.save_notes()
# A backup of look-alikes alone that brings a template: Skip them goes on with
# the template -- with only Cancel and Import anyway, the default Cancel dropped
# it.
_bk_asked = []
_ic_import([{'title': 'Look alike', 'body': 'same words'}], [], _bk_answer,
           templates=[{'name': 'Weekly review', 'title': 'Review', 'body': 'wins'}])
check(f"a backup of look-alikes that brings a template offers Skip them, and the template comes ({_bk_asked})",
      any('Skip them' in labels for labels in _bk_asked)
      and any(t.get('name') == 'Weekly review' for t in app.templates)
      and sum(1 for n in app.notes if n.get('title') == 'Look alike') == 1)
app.templates = [t for t in app.templates if t.get('name') != 'Weekly review']
NO.save_templates(app.templates)
app.notes = []; app.save_notes()

# ---- A BACKUP WITH A DAMAGED FILE IN IT ----
# Bytes that are not UTF-8 (a file another program saved in a Windows code
# page) and nesting deeper than the parser follows raised past the worker's
# handlers. Its catch-all then ended the whole import with "Import failed
# unexpectedly" -- even when the damaged file was only the templates, the
# Trash or the settings riding beside a sound notebook.
_dz_damage = {'not UTF-8': b'[{"id": 1, "title": "caf\xe9"}]',
              'nested too deep': b'[' * 100000 + b']' * 100000}
_dz_sound = json.dumps([{'title': 'Sound note', 'body': 'kept'}]).encode()


def _dz_import(members, answer=None):
    """Import a backup holding *members* (name -> bytes), saying yes to
    every question, or what *answer* (the dialog's own arguments) gives;
    return what the import said, as (title, text) pairs."""
    zpath = os.path.join(tempfile.gettempdir(), 'qa3_damaged_member.zip')
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, 'w') as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    said = []
    real = app._themed_dialog
    app._themed_dialog = lambda *a, **k: (said.append((a[0], a[1])),
                                          answer(*a, **k) if answer else True)[1]
    fd.askopenfilename = lambda **k: zpath
    try:
        app.import_data()
        t0 = time.time()
        while app._import_state is not None and time.time() - t0 < 120:
            app.update()
    finally:
        app._themed_dialog = real
        os.remove(zpath)
    return said


# A notebook that parses but is not a list (null, a number): it raised on the
# main thread after the import's state was cleared, and its cleanup -- the
# unpacked folder, the files it copied -- never ran.
for _nl_value in (b'null', b'7', b'{"title": "x"}'):
    app.notes = []; app.save_notes()
    _nl_said = _dz_import({'notes_data.json': _nl_value})
    check(f'a backup whose notebook is {_nl_value!r} says it is not a backup '
          f'({[m.split(chr(10))[0] for _t, m in _nl_said]})',
          app.notes == [] and app._import_state is None
          and any("doesn't look like a Note Organizer backup" in m for _t, m in _nl_said))

for _dz_how, _dz_bytes in _dz_damage.items():
    for _dz_extra in ('templates.json', 'trash.json', 'settings.json'):
        app.notes = []; app.save_notes()
        _dz_said = _dz_import({'notes_data.json': _dz_sound,
                               _dz_extra: _dz_bytes})
        check(f'a backup whose {_dz_extra} is {_dz_how} still brings its '
              f'notes ({[t for t, _m in _dz_said]})',
              [n.get('title') for n in app.notes] == ['Sound note']
              and not any('failed' in t.lower() for t, _m in _dz_said))
    app.notes = []; app.save_notes()
    _dz_said = _dz_import({'notes_data.json': _dz_bytes})
    check(f'a backup whose notebook is {_dz_how} says it cannot read the '
          f'notes ({[m.split(chr(10))[0] for _t, m in _dz_said]})',
          app.notes == []
          and any(m.startswith("Couldn't read the notes in that backup")
                  for _t, m in _dz_said))
app.notes = []; app.save_notes()

# A delete when trash.json cannot be written (a full disk, a file another
# program holds) deletes nothing and says so. The note used to leave the
# notes file while the Trash kept it only in memory: in neither file once
# the app closed, under a status line promising "recoverable".
_tf_keep = NO.normalize_note({'id': 1, 'title': 'Keep me', 'body': 'x'})
_tf_doomed = NO.normalize_note({'id': 2, 'title': 'Accountant: Maria', 'body': 'tax'})
app.notes = [_tf_keep, _tf_doomed]; app.save_notes()
app.trash = []; NO.save_trash(app.trash)
_tf_warned = []
_tf_real = (app.ask_yes_no, app.show_warning)
app.ask_yes_no = lambda *a, **k: True
app.show_warning = lambda *a, **k: _tf_warned.append(' '.join(map(str, a)))
os.makedirs(NO.TRASH_FILE + '.tmp')
try:
    app.selected_note_id = None
    app._delete_note(_tf_doomed, None)
    app.update()
    _tf_disk = [n.get('title') for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))]
    check('a delete the Trash cannot hold keeps the note, on screen and on disk '
          f'({_tf_disk})',
          any(n.get('id') == 2 for n in app.notes) and 'Accountant: Maria' in _tf_disk
          and not any(e.get('id') == 2 for e in app.trash))
    check('...and says nothing was deleted',
          any('Nothing was deleted' in w for w in _tf_warned))
finally:
    os.rmdir(NO.TRASH_FILE + '.tmp')
    app.ask_yes_no, app.show_warning = _tf_real
app.notes = []; app.save_notes()
app.trash = []; NO.save_trash(app.trash)

# Closing after a save that failed (a full disk, a file another program
# holds) tries once more and, failing again, asks before it throws away
# what only the screen holds. It used to close at once.
_cs_note = NO.normalize_note({'id': 1, 'title': 'Draft', 'body': 'old words'})
app.notes = [_cs_note]; app.save_notes()
app.open_note_in_tab(_cs_note); app.update()
_cs_asked, _cs_closed = [], []
_cs_real = (app.ask_yes_no, app.show_error, app.destroy)
app.ask_yes_no = lambda *a, **k: (_cs_asked.append(a[0] if a else ''), False)[1]
app.show_error = lambda *a, **k: None
app.destroy = lambda: _cs_closed.append(True)
os.makedirs(NO.DATA_FILE + '.tmp')
try:
    app.body_text.insert('end', ' new words')
    app.on_app_close(); app.update()
    check('a close after a failed save asks, and No keeps the window open',
          _cs_asked == ['Close without saving?'] and not _cs_closed)
    os.rmdir(NO.DATA_FILE + '.tmp')
    _cs_asked.clear()
    app.on_app_close(); app.update()
    _cs_disk = json.load(open(NO.DATA_FILE, encoding='utf-8'))
    check('...and once the disk takes it, the close saves without asking '
          f'({[n.get("body") for n in _cs_disk]})',
          not _cs_asked and _cs_closed
          and any('new words' in (n.get('body') or '') for n in _cs_disk))
finally:
    if os.path.isdir(NO.DATA_FILE + '.tmp'):
        os.rmdir(NO.DATA_FILE + '.tmp')
    app.ask_yes_no, app.show_error = _cs_real[0], _cs_real[1]
    del app.destroy
    app._notes_unsaved = False
app.notes = []; app.save_notes()

# The failed save's message sends the person to Settings → Backup → Export,
# and that backup was packed from the file on disk: "Export complete",
# without the very changes it was made to rescue. It packs what the app
# holds now.
_xf_note = NO.normalize_note({'id': 1, 'title': 'Chapter', 'body': 'Chapter one draft.'})
app.notes = [_xf_note]; app.save_notes()
app.open_note_in_tab(_xf_note); app.update()
_xf_zip = os.path.join(tempfile.gettempdir(), 'qa3_export_after_failed_save.zip')
if os.path.exists(_xf_zip):
    os.remove(_xf_zip)
_xf_said = []
_xf_real = (app.show_error, app.show_info)
app.show_error = lambda *a, **k: _xf_said.append(a[0] if a else '')
app.show_info = lambda *a, **k: _xf_said.append(a[0] if a else '')
os.makedirs(NO.DATA_FILE + '.tmp')
try:
    app.body_text.insert('end-1c', ' Three hours of work typed today.')
    app._flush_autosave(leaving=False); app.update()
    _xf_failed = app._notes_unsaved
    fd.asksaveasfilename = lambda **k: _xf_zip
    app.export_data()
    t0 = time.time()
    while app._export_state is not None and time.time() - t0 < 120:
        app.update()
    with zipfile.ZipFile(_xf_zip) as _zf:
        _xf_packed = json.loads(_zf.read('notes_data.json').decode('utf-8'))
    check(f'after a failed save, the backup the app advises holds the changes the '
          f'file lacks ({[n.get("body") for n in _xf_packed]}; said {_xf_said})',
          _xf_failed and 'Export complete' in _xf_said
          and any('Three hours of work' in (n.get('body') or '') for n in _xf_packed))
    # A start that could not read the notes file holds none: the export said
    # "Export complete" over an empty notebook. It refuses.
    _xf_said.clear()
    _xf_asked = []
    fd.asksaveasfilename = lambda **k: (_xf_asked.append(1), _xf_zip)[1]
    _xf_real_warn = app.show_warning
    _xf_why = []
    app.show_warning = lambda *a, **k: (_xf_said.append(a[0] if a else ''),
                                        _xf_why.append(str(a[1]) if len(a) > 1 else ''))
    app._corrupt_notes_report = ''
    _xf_had = app.notes
    app.notes = []
    try:
        app.export_data(); app.update()
    finally:
        app.notes = _xf_had
        app._corrupt_notes_report = None
        app.show_warning = _xf_real_warn
    check(f'a start that could not read the notes file refuses to export an empty '
          f'backup, and says why ({_xf_said}; {[w[:60] for w in _xf_why]})',
          'Nothing to back up yet' in _xf_said and not _xf_asked
          and app._export_state is None
          and any('could not be opened when Note Organizer started' in w
                  and 'a backup made now would hold none either' in w for w in _xf_why))
    # ...but notes written since are another matter: on a run that saves
    # nothing the backup is their only way out, and it says what it holds.
    _xf_said.clear()
    fd.asksaveasfilename = lambda **k: _xf_zip
    app._corrupt_notes_report = ''
    try:
        app.export_data()
        t0 = time.time()
        while app._export_state is not None and time.time() - t0 < 120:
            app.update()
    finally:
        app._corrupt_notes_report = None
    with zipfile.ZipFile(_xf_zip) as _zf:
        _xf_packed = json.loads(_zf.read('notes_data.json').decode('utf-8'))
    check(f'...while notes written since it are backed up, said to be all it holds '
          f'({_xf_said}, {len(_xf_packed)})',
          _xf_said == ['Backup of this session saved']
          and [n.get('id') for n in _xf_packed] == [n.get('id') for n in app.notes])
    # ...its advice true of how the file was lost: reopening brings back a file
    # held, never one damaged, whether its copy aside was made or not.
    _xs_words, _xs_info = {}, app.show_info
    _xs_refused_was = getattr(app, '_notes_file_refused', False)
    for _xs_case, _xs_report, _xs_refused, _xs_held in (
            ('held', '', True, True), ('copied', 'notes_data_corrupt_qa3.json', False, False),
            ('not copied', '', False, True), ('older notebook', None, False, True)):
        _xs_got = []
        app.show_info = lambda *a, **k: _xs_got.append(' '.join(map(str, a)))
        app._corrupt_notes_report, app._notes_file_refused = _xs_report, _xs_refused
        if _xs_held:
            NO._core_paths.hold_writes(NO.DATA_FILE)
        try:
            app.export_data()
            t0 = time.time()
            while app._export_state is not None and time.time() - t0 < 120:
                app.update()
        finally:
            NO._core_paths.WRITES_HELD.discard(os.path.normcase(os.path.abspath(NO.DATA_FILE)))
            app._corrupt_notes_report, app._notes_file_refused = None, _xs_refused_was
            app.show_info = _xs_info
        _xs_got = ' '.join(_xs_got)
        _xs_words[_xs_case] = ('open it again' in _xs_got, 'copy kept aside' in _xs_got,
                               'will not bring those notes back' in _xs_got
                               and 'Import brings them in' in _xs_got)
    check(f"...and its advice is true of how the notes file was lost: reopen for one held, "
          f"never for one damaged ({_xs_words})",
          _xs_words == {'held': (True, False, False), 'copied': (False, True, False),
                        'not copied': (False, False, True), 'older notebook': (True, False, False)})
finally:
    os.rmdir(NO.DATA_FILE + '.tmp')
    app.show_error, app.show_info = _xf_real
    app._notes_unsaved = False
    if os.path.exists(_xf_zip):
        os.remove(_xf_zip)
app.notes = []; app.save_notes()

# A run whose notes file is held (neither read nor copied at the start, or
# not brought in from an older notebook) saves nothing. Every way out it gave
# was closed: a dialog at every pause with advice that cannot work there, an
# import that said "Import complete" with its notes in no file, a dialog
# inside a Windows sign-out.
_hr_said, _hr_status = [], []
_hr_real = (app.show_error, app.show_warning, app.set_status)
app.show_error = lambda *a, **k: _hr_said.append(a[0] if a else '')
app.show_warning = lambda *a, **k: _hr_said.append(a[0] if a else '')
app.set_status = lambda text, *a, **k: _hr_status.append(text)
_hr_picked = []
_hr_real_pick = fd.askopenfilename
fd.askopenfilename = lambda **k: (_hr_picked.append(1), '')[1]
NO._core_paths.hold_writes(NO.DATA_FILE)
try:
    app.new_note(); app.update()
    _hr_after = []
    for _hr_words in ('first words', ' and more'):
        app.body_text.insert('end-1c', _hr_words)
        app._flush_autosave(leaving=False); app.update()
        _hr_after.append(_hr_status[-1] if _hr_status else '')
    _hr_saves = list(_hr_said)
    _hr_said.clear()
    app.import_data(); app.update()
    _hr_import = list(_hr_said)
    _hr_said.clear()
    app._held_save_said = False          # as if not yet said: the sign-out's own
    app.body_text.insert('end-1c', ' at the end')
    app.on_session_end(); app.update()
    _hr_session = list(_hr_said)
finally:
    NO._core_paths.WRITES_HELD.clear()
    app.show_error, app.show_warning, app.set_status = _hr_real
    fd.askopenfilename = _hr_real_pick
    app._held_save_said = False
check(f'a held run says once that nothing is saved, then only on the status line '
      f'({_hr_saves}, {_hr_status[-1:]})',
      _hr_saves == ['Nothing is saved in this session']
      and any('nothing is saved in this session' in s for s in _hr_status))
check(f'...the status line saying so from the first save, never "Auto-saved" '
      f'({[s[:24] for s in _hr_after]})',
      len(_hr_after) == 2
      and all('nothing is saved in this session' in s for s in _hr_after))
check(f'...refuses an import before a file is picked ({_hr_import}, {_hr_picked})',
      _hr_import == ['Import after reopening'] and not _hr_picked)
check(f'...and a Windows sign-out shows no dialog ({_hr_session})', _hr_session == [])
app.new_note(); app.update()
app.notes = []; app.save_notes()

# A restore on a held run took the entry out of the Trash in memory, its notes
# save refused: the next Delete or Empty trash wrote that Trash over the file,
# and the note was in neither file. Refused before anything moves;
# a notes write that fails on an ordinary run puts the lists back as well; and
# no attached file is deleted on a held run, one its unread notes may use.
_rt_file = os.path.join(NO.ATTACHMENTS_DIR, '20261029120000000000_recipe.png')
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
with open(_rt_file, 'wb') as _f:
    _f.write(b'recipe')
_rt_entries = [NO.normalize_note({'id': 41, 'title': 'Recipe from mum', 'body': 'flour'}),
               NO.normalize_note({'id': 42, 'title': 'Old junk', 'body': 'x',
                                  'attachments': [{'name': 'recipe.png',
                                                   'stored_as': os.path.basename(_rt_file)}]})]
for _rt_e in _rt_entries:
    _rt_e['deleted_at'] = '2026-10-29 09:00:00'
app.trash = list(_rt_entries); NO.save_trash(app.trash)
_rt_said, _rt_toasts, _rt_status = [], [], []
_rt_real = (app.show_error, app.show_warning, app._show_toast, app.set_status)
app.show_error = lambda *a, **k: _rt_said.append(a[0] if a else '')
app.show_warning = lambda *a, **k: _rt_said.append(a[0] if a else '')
app._show_toast = lambda text, *a, **k: _rt_toasts.append(text)
app.set_status = lambda text, *a, **k: _rt_status.append(text)
NO._core_paths.hold_writes(NO.DATA_FILE)
try:
    _rt_one = app._restore_trash_entries([app.trash[0]])
    _rt_undo_said = len(_rt_said)
    app._undo_trash([(41, '2026-10-29 09:00:00')]); app.update()
    _rt_mem = [e.get('title') for e in app.trash]
    # The next write of the Trash, as Delete permanently on another entry makes:
    NO._delete_attachment_files([app.trash[1]],
                                spare=NO.attachment_names_in(app.notes + [app.trash[0]]))
    app.trash = [app.trash[0]]; NO.save_trash(app.trash)
    _rt_file_after = [e.get('title') for e in NO.load_trash()]
    _rt_kept_file = os.path.exists(_rt_file)
finally:
    NO._core_paths.WRITES_HELD.clear()
_rt_said2 = list(_rt_said)
_rt_said.clear()
app.trash = list(_rt_entries[:1]); NO.save_trash(app.trash)
os.makedirs(NO.DATA_FILE + '.tmp')
try:
    _rt_failed = app._restore_trash_entries([app.trash[0]])
    _rt_after_fail = ([e.get('title') for e in app.trash],
                      [n.get('title') for n in app.notes])
finally:
    os.rmdir(NO.DATA_FILE + '.tmp')
    app.show_error, app.show_warning, app._show_toast, app.set_status = _rt_real
    app._notes_unsaved = False
    if os.path.exists(_rt_file):
        os.remove(_rt_file)
check(f'a restore on a held run is refused and says why, the Undo as well '
      f'({_rt_one}, {_rt_said2}, {_rt_toasts})',
      _rt_one is None and _rt_said2 == ['Restore after reopening'] * 2
      and _rt_undo_said == 1 and _rt_toasts == [])
check(f'...the note still in the Trash after a later Trash write ({_rt_mem}, {_rt_file_after})',
      _rt_mem == ['Recipe from mum', 'Old junk'] and _rt_file_after == ['Recipe from mum'])
check(f'...and no attached file is deleted on a held run ({_rt_kept_file})', _rt_kept_file)
check(f'a restore whose notes write fails leaves the note in the Trash, and says so '
      f'({_rt_failed}, {_rt_after_fail}, {_rt_status[-1:]})',
      _rt_failed is None and _rt_after_fail == (['Recipe from mum'], [])
      and any('Not restored' in s for s in _rt_status))
app.trash = []; NO.save_trash(app.trash)
app.notes = []; app.save_notes()

# One attached file another program holds with no sharing failed the whole
# backup: it is left out of it, and named.
_la_file = os.path.join(NO.ATTACHMENTS_DIR, '20261028120000000000_scan.png')
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
with open(_la_file, 'wb') as _f:
    _f.write(b'held')
_la_zip = os.path.join(tempfile.gettempdir(), 'qa3_export_held_attachment.zip')
_la_said = []
_la_real = (app.show_info, fd.asksaveasfilename)
_la_open = open


def _la_held(path, *a, **k):
    # Opened by the entry file's own code only: another program's hold.
    if os.path.basename(str(path)) == os.path.basename(_la_file):
        raise PermissionError(13, 'held by another program')
    return _la_open(path, *a, **k)


app.show_info = lambda *a, **k: _la_said.append(' '.join(map(str, a)))
NO.open = _la_held
fd.asksaveasfilename = lambda **k: _la_zip
try:
    app.notes = [NO.normalize_note({'id': 1, 'title': 'Kept', 'body': 'words'})]
    app.save_notes()
    app.export_data()
    t0 = time.time()
    while app._export_state is not None and time.time() - t0 < 120:
        app.update()
    with zipfile.ZipFile(_la_zip) as _zf:
        _la_names = _zf.namelist()
finally:
    app.show_info, fd.asksaveasfilename = _la_real
    del NO.open
    os.remove(_la_file)
    if os.path.exists(_la_zip):
        os.remove(_la_zip)
check(f'a backup leaves out an attached file another program holds, and names it '
      f'({_la_said[:1]}, {_la_names})',
      len(_la_said) == 1 and 'not all of it' in _la_said[0] and 'scan.png' in _la_said[0]
      and 'notes_data.json' in _la_names
      and not any('scan.png' in n for n in _la_names))
app.notes = []; app.save_notes()

# A templates file the start could not read leaves the app holding only the
# session's: one template saved made "Export complete" of a backup without
# the file's own. Read at the export, or named as left out.
_ht_zip = os.path.join(tempfile.gettempdir(), 'qa3_export_held_templates.zip')
_ht_said, _ht_got = [], []
_ht_real = (app.show_info, fd.asksaveasfilename, app.templates)
app.show_info = lambda *a, **k: _ht_said.append(' '.join(map(str, a)))
fd.asksaveasfilename = lambda **k: _ht_zip
try:
    app.notes = [NO.normalize_note({'id': 1, 'title': 'Kept', 'body': 'words'})]
    app.save_notes()
    # The third: a name the session made again, unable to see the file's --
    # the file's won, and the newest was in no backup. Both go, the
    # session's first, as an import keeps the first of a name.
    for _ht_file, _ht_mine in (
            ('[{"name": "Weekly", "body": "a"}, {"name": "Trip", "body": "b"}]', 'Made today'),
            ('{broken', 'Made today'),
            ('[{"name": "Weekly", "body": "a"}, {"name": "Trip", "body": "b"}]', 'Trip')):
        with open(NO.TEMPLATES_FILE, 'w', encoding='utf-8') as _f:
            _f.write(_ht_file)
        NO._core_paths.hold_writes(NO.TEMPLATES_FILE)
        app.templates = [{'name': _ht_mine, 'body': 'c'}]
        app.export_data()
        t0 = time.time()
        while app._export_state is not None and time.time() - t0 < 120:
            app.update()
        with zipfile.ZipFile(_ht_zip) as _zf:
            _ht_got.append([(t.get('name'), t.get('body')) for t in
                            json.loads(_zf.read('templates.json').decode('utf-8'))])
        NO._core_paths.WRITES_HELD.clear()
finally:
    NO._core_paths.WRITES_HELD.clear()
    app.show_info, fd.asksaveasfilename, app.templates = _ht_real
    os.remove(NO.TEMPLATES_FILE)
    if os.path.exists(_ht_zip):
        os.remove(_ht_zip)
check(f'a templates file unread at the start goes into the backup with the '
      f'session\'s, or is named left out ({_ht_got}; {[s[:40] for s in _ht_said]})',
      _ht_got == [[('Made today', 'c'), ('Weekly', 'a'), ('Trip', 'b')],
                  [('Made today', 'c')],
                  [('Trip', 'c'), ('Weekly', 'a'), ('Trip', 'b')]]
      and len(_ht_said) == 3 and _ht_said[0].startswith('Export complete ')
      and 'not all of it' in _ht_said[1] and 'templates.json' in _ht_said[1])
app.notes = []; app.save_notes()

# Signing out of Windows, restarting or shutting down ends the process
# without the close: Tk's WM_SAVE_YOURSELF comes instead, and the last
# typing was left unsaved. on_session_end saves it, asking nothing.
app.new_note(); app.update()
_se_note = NO.normalize_note({'id': 4242, 'title': 'Before sign-out', 'body': 'typed'})
app.notes = [_se_note]; app.save_notes()
app.open_note_in_tab(_se_note); app.update()
_se_asked = []
_se_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (_se_asked.append(a[0] if a else ''), True)[1]
try:
    app.body_text.insert('end', ' just before')
    app.on_session_end(); app.update()
    _se_disk = [n.get('body') for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))]
    check(f'a Windows sign-out saves the last typing, asking nothing ({_se_disk})',
          _se_disk == ['typed just before'] and not _se_asked and app.winfo_exists())
finally:
    app.ask_yes_no = _se_real_ask
app.notes = []; app.save_notes()

# The blank editor a delete leaves -- no note, no tab -- still takes typing,
# and a way out within the autosave's half second (Ctrl+N, another note, the
# close, a sign-out) cancelled that autosave and saved nothing.
_be_real = (app.ask_yes_no, app._themed_dialog)
app.ask_yes_no = lambda *a, **k: True
app._themed_dialog = lambda *a, **k: True


def _be_bodies():
    return sorted(n.get('body') for n in json.load(open(NO.DATA_FILE, encoding='utf-8')))


try:
    _be_saved = []
    for _be_way, _be_words in (('Ctrl+N', 'buy milk'), ('sign-out', 'call the bank')):
        app.new_note(); app.update()
        _be_doomed = NO.normalize_note({'id': 4250, 'title': 'Gone', 'body': 'old'})
        app.notes = [_be_doomed]; app.save_notes()
        app.open_note_in_tab(_be_doomed); app.update()
        app.delete_current_note(); app.update()
        _be_state = (app.selected_note_id, len(app.open_tabs))
        app.body_text.insert('1.0', _be_words)
        if _be_way == 'Ctrl+N':
            app.open_blank_tab(); app.update()
        else:
            app.on_session_end(); app.update()
        _be_saved.append((_be_way, _be_state, _be_bodies()))
finally:
    app.ask_yes_no, app._themed_dialog = _be_real
check(f'typing in the blank editor a delete leaves is saved by any way out '
      f'within the autosave\'s wait ({_be_saved})',
      [s[2] for s in _be_saved] == [['buy milk'], ['call the bank']]
      and all(s[1] == (None, 0) for s in _be_saved))
app.new_note(); app.update()
app.notes = []; app.save_notes()
# ...an item typed in its checklist's Add box too: the blank editor's question
# left that box out, and Ctrl+N cleared it.
app._themed_dialog = lambda *a, **k: True
try:
    _be_doomed = NO.normalize_note({'id': 4251, 'title': 'Gone', 'body': 'old'})
    app.notes = [_be_doomed]; app.save_notes()
    app.open_note_in_tab(_be_doomed); app.update()
    app.delete_current_note(); app.update()
    _be_state = (app.selected_note_id, len(app.open_tabs))
    app.checklist_add_var.set('pack the bags')
    app.open_blank_tab(); app.update()
    _be_items = [i.get('text') for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))
                 for i in (n.get('checklist') or [])]
finally:
    app._themed_dialog = _be_real[1]
check(f'...and an item typed in its checklist\'s Add box is saved by Ctrl+N '
      f'({_be_state}, {_be_items})',
      _be_state == (None, 0) and _be_items == ['pack the bags'])
app.new_note(); app.update()
app.notes = []; app.save_notes()

# A checklist of 1,000 items took a 1,001st by Add, by the box taken on
# leaving, and by a delete's Undo after an Add into its room: drawn and
# saved, then cut without a word at the next start. Each door
# refuses it and says so; the Add leaves the words in the box.
_cf_said = []
_cf_real = app.show_info
app.show_info = lambda *a, **k: _cf_said.append(a[0] if a else '')
try:
    _cf_note = NO.normalize_note({'id': 4252, 'title': 'Big list', 'body': 'b', 'checklist': [
        {'text': 'item %d' % i, 'done': False} for i in range(1000)]})
    _cf_other = NO.normalize_note({'id': 4253, 'title': 'Other', 'body': 'x'})
    app.notes = [_cf_note, _cf_other]; app.save_notes()
    app.open_note_in_tab(_cf_note); app.update()
    app.checklist_add_var.set('ADDED 1001')
    app._add_checklist_item(); app.update()
    _cf_add = (len(app._get_checklist()), app.checklist_add_var.get(), len(_cf_said))
    app.open_note_in_tab(_cf_other); app.update()          # the box, on leaving
    _cf_file = [len(n.get('checklist') or [])
                for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))]
    app.open_note_in_tab(_cf_note); app.update()
    _cf_items = app._get_checklist()
    _cf_gone = _cf_items.pop(3)                          # deleted, its Undo offered
    app.checklist_add_var.set('into the room')
    app._add_checklist_item(); app.update()
    app._undo_checklist_delete(_cf_items, 3, _cf_gone); app.update()
    _cf_undo = (len(app._get_checklist()), _cf_gone in app._get_checklist())
finally:
    app.show_info = _cf_real
    app.checklist_add_var.set('')
check(f'a checklist of 1,000 items refuses a 1,001st at every door, and says so '
      f'({_cf_add}, {_cf_file}, {_cf_undo}, {_cf_said})',
      _cf_add == (1000, 'ADDED 1001', 1) and _cf_file == [1000, 0]
      and _cf_undo == (1000, False) and _cf_said == ['Checklist full'] * 3)
app.new_note(); app.update()
app.notes = []; app.save_notes()

# The Add box taken by a save that stays on the note (Export, a day moved)
# rebuilt every row, 2.2 s at 1,000: one row is added, as Add does.
_pr_note = NO.normalize_note({'id': 4256, 'title': 'Rows', 'body': 'b', 'checklist': [
    {'text': 'row %d' % i, 'done': False} for i in range(30)]})
app.notes = [_pr_note]; app.save_notes()
app.open_note_in_tab(_pr_note); app.update()
if not app._checklist_open:
    app.toggle_checklist_section(); app.update()
_pr_first = app._checklist_drawn['rows'][0][1] if app._checklist_drawn['rows'] else None
app.checklist_add_var.set('row 30')
app._flush_autosave(leaving=False); app.update()
_pr_rows = app._checklist_drawn['rows']
check(f'the Add box taken by a save that stays adds one row, the others kept '
      f'({len(_pr_rows)})',
      _pr_first is not None and len(_pr_rows) == 31 and _pr_rows[0][1] is _pr_first
      and [i.get('text') for i in app._get_checklist()][-1] == 'row 30')
app.new_note(); app.update()
app.notes = []; app.save_notes()

# Use template dropped an item typed in the Add box: in a new note nothing
# asked (the question's test left the box out), and over a saved note Yes
# lost what the autosave had not yet written. A new note's box is
# asked about; a saved note is left, saved first, and not asked about.
_ut_asked = []
_ut_real = app.ask_yes_no
app.ask_yes_no = lambda t, *a, **k: (_ut_asked.append(t), False)[1]     # "No"
_ut_tpl = {'name': 'Packing', 'title': 'Trip', 'body': 'b',
           'checklist': [{'text': 'socks', 'done': False}]}
try:
    app.new_note(); app.update()
    app.checklist_add_var.set('passport')
    app._apply_template(dict(_ut_tpl)); app.update()
    _ut_new = (list(_ut_asked), app.checklist_add_var.get())
    _ut_asked.clear()
    app.checklist_add_var.set('')
    _ut_note = NO.normalize_note({'id': 4254, 'title': 'Kept', 'body': 'old words'})
    app.notes = [_ut_note]; app.save_notes()
    app.open_note_in_tab(_ut_note); app.update()
    app.body_text.insert('end-1c', ' and new ones')
    app.checklist_add_var.set('towel')
    app._apply_template(dict(_ut_tpl)); app.update()
    _ut_kept = next((n for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))
                     if n.get('id') == 4254), {})
    _ut_saved = (list(_ut_asked), _ut_kept.get('body'),
                 [i.get('text') for i in _ut_kept.get('checklist') or []],
                 app.title_entry.get())
finally:
    app.ask_yes_no = _ut_real
    app.checklist_add_var.set('')
check(f'Use template asks before replacing a new note whose only words are in its '
      f'Add box ({_ut_new})', _ut_new == (['Replace current note?'], 'passport'))
check(f'...and leaves a saved note saved first, its Add box too, without asking '
      f'({_ut_saved})',
      _ut_saved == ([], 'old words and new ones', ['towel'], 'Trip'))
app.new_note(); app.update()
app.notes = []; app.save_notes()

# Comments wiped kept no rescue copy: the save's measure read the title and
# body only, though the copy holds the comments.
_cw_old = ' '.join('Remember the vet said %d grams a day' % i for i in range(24))
_cw_note = NO.normalize_note({'id': 4255, 'title': 'Dog', 'body': 'Walk twice a day.',
                              'comments': _cw_old})
app.notes = [_cw_note]; app.save_notes()
app.open_note_in_tab(_cw_note); app.update()
app.comments_text.delete('1.0', 'end')
app.comments_text.insert('1.0', 'ok')
app._flush_autosave(leaving=True); app.update()             # leaving saves
_cw_prev = (next((n for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))
                  if n.get('id') == 4255), {}).get('_prev') or {})
check(f'comments wiped keep a rescue copy of them ({len(_cw_prev.get("comments", ""))})',
      _cw_prev.get('comments') == _cw_old)
app.notes = []; app.save_notes()

# ...but a comment of two letters cleared after a big delete replaced that
# delete's copy with the note as it stood: the deleted body was in no file.
# The waiting copy keeps its words and takes the comments.
_cb_body = ' '.join('Pack item %d for the mountain trip' % i for i in range(20))
_cb_note = NO.normalize_note({'id': 4257, 'title': 'Trip', 'body': _cb_body, 'comments': 'ok'})
app.notes = [_cb_note]; app.save_notes()
app.open_note_in_tab(_cb_note); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'Trip.')
app._flush_autosave(leaving=False); app.update()
app.comments_text.delete('1.0', 'end')
app._flush_autosave(leaving=True); app.update()
_cb_prev = (next((n for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))
                  if n.get('id') == 4257), {}).get('_prev') or {})
check(f'comments cleared after a big delete keep that delete\'s copy, with the comments '
      f'({(_cb_prev.get("body") or "")[:14]!r}, {_cb_prev.get("comments")!r})',
      _cb_prev.get('body') == _cb_body and _cb_prev.get('comments') == 'ok')
app.new_note(); app.update()
app.notes = []; app.save_notes()

# ...and the comments half of the same loss: a long comment deleted, kept in
# the copy, then two letters typed, saved and cleared wrote over it -- the
# long comment in no file. The copy keeps whichever comments lose
# more; a long comment cleared over a short one takes its place.
_cc_long = ' '.join('Ask the vet about %d grams of the new food' % i for i in range(9))


def _cc_run(first, then):
    note = NO.normalize_note({'id': 4260, 'title': 'Dog', 'body': 'Walk twice a day.',
                              'comments': first})
    app.notes = [note]; app.save_notes()
    app.open_note_in_tab(note); app.update()
    app.comments_text.delete('1.0', 'end')
    app._flush_autosave(leaving=False); app.update()
    app.comments_text.insert('1.0', then)
    app._flush_autosave(leaving=False); app.update()
    app.comments_text.delete('1.0', 'end')
    app._flush_autosave(leaving=True); app.update()
    kept = (next((n for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))
                  if n.get('id') == 4260), {}).get('_prev') or {}).get('comments')
    app.new_note(); app.update()
    app.notes = []; app.save_notes()
    return kept


_cc_short_after_long = _cc_run(_cc_long, 'zz')
_cc_long_after_short = _cc_run('ok', _cc_long)
check(f'two letters of comments cleared after a long comment was deleted leave the long one '
      f'in the copy ({(_cc_short_after_long or "")[:12]!r})', _cc_short_after_long == _cc_long)
check(f'...and a long comment cleared over a short one takes its place '
      f'({(_cc_long_after_short or "")[:12]!r})', _cc_long_after_short == _cc_long)

# A full checklist's Add box taken on leaving said "Delete an item to make
# room", and the words went with the box: they wait for the note,
# back in its box when it opens again, and the window's close asks first.
_cw_said, _cw_asked, _cw_closed = [], [], []
_cw_real = (app.show_info, app.ask_yes_no, app.destroy)
app.show_info = lambda *a, **k: _cw_said.append(a[1] if len(a) > 1 else '')
app.ask_yes_no = lambda t, *a, **k: (_cw_asked.append(t), False)[1]     # "No"
app.destroy = lambda: _cw_closed.append(1)   # a close that asks nothing must not end the run
try:
    _cw_full = NO.normalize_note({'id': 4258, 'title': 'Big list', 'body': 'b', 'checklist': [
        {'text': 'item %d' % i, 'done': False} for i in range(1000)]})
    _cw_other = NO.normalize_note({'id': 4259, 'title': 'Other', 'body': 'x'})
    app.notes = [_cw_full, _cw_other]; app.save_notes()
    app.open_note_in_tab(_cw_full); app.update()
    app.checklist_add_var.set('buy more boxes')
    app.open_note_in_tab(_cw_other); app.update()
    _cw_left = app.checklist_add_var.get()
    app.open_note_in_tab(_cw_full); app.update()
    _cw_back = app.checklist_add_var.get()
    # ...said once for those words, not at every way out of the note: back
    # in its box at each opening, they raised "Checklist full" each time.
    # Other words are said again.
    for _cw_i in range(3):
        app.open_note_in_tab(_cw_other); app.update()
        app.open_note_in_tab(_cw_full); app.update()
    _cw_said_n = len(_cw_said)
    app.checklist_add_var.set('buy bigger boxes')
    app.open_note_in_tab(_cw_other); app.update()
    _cw_said_new = len(_cw_said)
    app.on_app_close(); app.update()
    _cw_open = not _cw_closed
finally:
    app.show_info, app.ask_yes_no, app.destroy = _cw_real
    app._add_box_waiting.clear()
    app.checklist_add_var.set('')
check(f'words a full checklist could not take wait in its Add box for the note, said '
      f'once, and the close asks before losing them ({_cw_left!r}, {_cw_back!r}, '
      f'{_cw_asked}, said {_cw_said_n} then {_cw_said_new}: {_cw_said[:1]})',
      _cw_left == '' and _cw_back == 'buy more boxes' and _cw_open
      and _cw_asked == ['Close without these items?'] and _cw_said_n == 1
      and _cw_said_new == 2
      and 'waits in this note\'s Add box' in (_cw_said[0] if _cw_said else ''))
app.new_note(); app.update()
app.notes = []; app.save_notes()

# ...but not about words of a note in the Trash: the close asked to lose
# words of a note the person had deleted.
_ct_asked, _ct_closed = [], []
_ct_real = (app.show_info, app.ask_yes_no, app.destroy)
app.show_info = lambda *a, **k: None
# Yes to the delete, No to anything the close asks.
app.ask_yes_no = lambda t, *a, **k: (_ct_asked.append(t), t == 'Delete note')[1]
app.destroy = lambda: _ct_closed.append(1)
try:
    _ct_full = NO.normalize_note({'id': 4261, 'title': 'Big list', 'body': 'b', 'checklist': [
        {'text': 'item %d' % i, 'done': False} for i in range(1000)]})
    _ct_other = NO.normalize_note({'id': 4262, 'title': 'Other', 'body': 'x'})
    app.notes = [_ct_full, _ct_other]; app.save_notes()
    app.open_note_in_tab(_ct_full); app.update()
    app.checklist_add_var.set('buy more boxes')
    app.open_note_in_tab(_ct_other); app.update()
    _ct_waits = dict(app._add_box_waiting)
    # Deleted from its right-click menu, another note open.
    app._context_delete_note(app.find_note(4261)); app.update()
    _ct_trashed = (not any(n.get('uid') == _ct_full['uid'] for n in app.notes)
                   and any(e.get('uid') == _ct_full['uid'] for e in app.trash))
    del _ct_asked[:]
    app.on_app_close(); app.update()
finally:
    app.show_info, app.ask_yes_no, app.destroy = _ct_real
    app._add_box_waiting.clear()
    app.checklist_add_var.set('')
check(f'...and the close does not ask about the words of a note in the Trash '
      f'(waiting {list(_ct_waits.values())}, in the Trash {_ct_trashed}, asked {_ct_asked}, '
      f'closed {bool(_ct_closed)})',
      list(_ct_waits.values()) == ['buy more boxes'] and _ct_trashed
      and _ct_asked == [] and _ct_closed == [1])
app.new_note(); app.update()
app.notes = []; app.save_notes()


def _cs_lists(full_id):
    """A note of 1,000 items and another to leave it for, both saved."""
    full = NO.normalize_note({'id': full_id, 'title': 'Big list', 'body': 'b', 'checklist': [
        {'text': 'item %d' % i, 'done': False} for i in range(1000)]})
    other = NO.normalize_note({'id': full_id + 1, 'title': 'Other', 'body': 'x'})
    app.notes = [full, other]; app.save_notes()
    return full, other


# ...and "once" is once for those words: added -- by Add, or by a way out of
# the note once there was room -- they are no longer the words that were
# said, and the same words typed into the list full again waited in silence.
_ca_said, _ca_seen = [], {}
_ca_real = app.show_info
app.show_info = lambda *a, **k: _ca_said.append(a[1] if len(a) > 1 else '')
try:
    for _ca_id, _ca_route in ((4263, 'Add'), (4265, 'a way out')):
        _ca_full, _ca_other = _cs_lists(_ca_id)
        app.open_note_in_tab(_ca_full); app.update()
        app.checklist_add_var.set('buy more boxes')
        app.open_note_in_tab(_ca_other); app.update()      # said: they wait
        app.open_note_in_tab(_ca_full); app.update()       # back in the box
        app._get_checklist().pop(0); app._render_checklist_items(); app.update()
        if _ca_route == 'Add':
            app._add_checklist_item(); app.update()
        else:
            app.open_note_in_tab(_ca_other); app.update()
            app.open_note_in_tab(_ca_full); app.update()
        _ca_items = len(app._get_checklist())
        _ca_before = len(_ca_said)
        app.checklist_add_var.set('buy more boxes')        # typed again, full again
        app.open_note_in_tab(_ca_other); app.update()
        _ca_seen[_ca_route] = (_ca_items, len(_ca_said) - _ca_before)
finally:
    app.show_info = _ca_real
    app._add_box_waiting.clear()
    app._waiting_said.clear()
    app.checklist_add_var.set('')
check(f'words once added are no longer the words said: typed again into the list full '
      f'again, "Checklist full" says them again (items, then said: {_ca_seen})',
      _ca_seen == {'Add': (1000, 1), 'a way out': (1000, 1)})
app.new_note(); app.update()
app.notes = []; app.save_notes()

# ...and they are remembered as said only once they are: words a Windows
# sign-out took, the sign-out then cancelled, were never said at all. A close
# answered No has named them in its question, and the next way out keeps
# silent.
_cs_said, _cs_asked, _cs_seen = [], [], {}
_cs_real = (app.show_info, app.ask_yes_no, app.destroy)
app.show_info = lambda *a, **k: _cs_said.append(a[1] if len(a) > 1 else '')
app.ask_yes_no = lambda t, *a, **k: (_cs_asked.append(t), False)[1]     # "No"
app.destroy = lambda: None
try:
    _cs_full, _cs_other = _cs_lists(4267)
    app.open_note_in_tab(_cs_full); app.update()
    app.checklist_add_var.set('passport photos')
    app.on_session_end(); app.update()
    _cs_seen['at the sign-out'] = len(_cs_said)
    app.open_note_in_tab(_cs_other); app.update()          # the sign-out was cancelled
    _cs_seen['the next way out'] = len(_cs_said)
    app.open_note_in_tab(_cs_full); app.update()
    app.checklist_add_var.set('visa forms')
    app.on_app_close(); app.update()
    _cs_seen['at the close'] = (len(_cs_said), list(_cs_asked))
    app.open_note_in_tab(_cs_other); app.update()
    _cs_seen['after the close'] = len(_cs_said)
finally:
    app.show_info, app.ask_yes_no, app.destroy = _cs_real
    app._add_box_waiting.clear()
    app._waiting_said.clear()
    app.checklist_add_var.set('')
check(f'"Checklist full" is remembered as said only when it is, or the close has asked '
      f'about the words ({_cs_seen})',
      _cs_seen == {'at the sign-out': 0, 'the next way out': 1,
                   'at the close': (1, ['Close without these items?']),
                   'after the close': 1})
app.new_note(); app.update()
app.notes = []; app.save_notes()

# A repeat turned off on the phone kept a day's own text only in the rescue
# copy; here the next big delete made a copy of words alone, and the day's
# text was in no file. A note read keeps those days in itself.
_pd_note = {'id': 4257, 'title': 'Gym', 'body': 'Warm up.\n' + 'Then the plan for the week. ' * 4,
            '_prev': {'title': 'Gym', 'body': 'Warm up.', 'date': '2026-11-02',
                      'recurrence': {'freq': 'weekly', 'interval': 1},
                      'overrides': {'2026-11-09': {'body': 'Leg day - knee hurt'}}}}
with open(NO.DATA_FILE, 'w', encoding='utf-8') as _f:
    json.dump([_pd_note], _f)
app.notes = app.load_notes(); app.update()
app.open_note_in_tab(app.notes[0]); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'Warm up.')
app._flush_autosave(leaving=True); app.update()
_pd_kept = next((n for n in json.load(open(NO.DATA_FILE, encoding='utf-8'))
                 if n.get('id') == 4257), {})
check(f'a day\'s own text a phone kept only in the rescue copy stays in the note after a '
      f'big delete here ({_pd_kept.get("overrides")})',
      (_pd_kept.get('overrides') or {}).get('2026-11-09', {}).get('body') == 'Leg day - knee hurt')
app.new_note(); app.update()
app.notes = []; app.save_notes()

# ...and saves all the close saves (one list, _save_on_the_way_out). Its own
# copy had drifted: a date typed short was left unsettled, so unsaved, and a
# write that had failed was never tried again.
app.new_note(); app.update()
_se2 = NO.normalize_note({'id': 4243, 'title': 'Dentist', 'body': 'call'})
app.notes = [_se2]; app.save_notes()
app.open_note_in_tab(_se2); app.update()
_se2_asked = []
_se2_real = (app.ask_yes_no, app._themed_dialog, app.show_error)
app.ask_yes_no = lambda *a, **k: (_se2_asked.append(a[0] if a else ''), True)[1]
app._themed_dialog = lambda *a, **k: (_se2_asked.append(a[0] if a else ''), True)[1]
app.show_error = lambda *a, **k: None


def _se2_disk():
    return [(n.get('date'), n.get('body')) for n in
            json.load(open(NO.DATA_FILE, encoding='utf-8')) if n.get('id') == 4243]


try:
    app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '17.10')
    app.body_text.insert('end', ' them')
    app.on_session_end(); app.update()
    _se2_want = NO.format_date(NO.read_date('17.10', settled=True))
    check(f'a Windows sign-out settles a date typed short and saves it, as the '
          f'close does ({_se2_disk()})',
          _se2_disk() == [(_se2_want, 'call them')] and not _se2_asked)
    os.makedirs(NO.DATA_FILE + '.tmp')
    try:
        app.body_text.insert('end', ' today')
        app._flush_autosave(leaving=False); app.update()
        _se2_failed = app._notes_unsaved
    finally:
        os.rmdir(NO.DATA_FILE + '.tmp')
    app.on_session_end(); app.update()
    check(f'...and writes once more what a failed save left only on screen '
          f'({_se2_disk()})',
          _se2_failed and not app._notes_unsaved
          and _se2_disk() == [(_se2_want, 'call them today')])
    app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '45.13.2026')
    app.body_text.insert('end', '!')
    _se2_asked.clear()
    app.on_session_end(); app.update()
    check(f'...asking nothing, even about a date it cannot store ({_se2_asked})',
          not _se2_asked and app.winfo_exists())
finally:
    # The unreadable date is cleared while the questions are still answered.
    app.date_entry.delete(0, 'end')
    app.new_note(); app.update()
    app.ask_yes_no, app._themed_dialog, app.show_error = _se2_real
    app._notes_unsaved = False
app.notes = []; app.save_notes()

# ...and keeps a template half written in its editor: the close asks it, the
# session asks nothing, and the work went with the session.
app.templates = [NO.normalize_template({'name': 'Week plan', 'body': 'Mon'})]
NO.save_templates(app.templates)
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()
_st_asked = []
_st_real = (app.ask_yes_no, app.ask_yes_no_cancel, app.show_warning)
app.ask_yes_no = app.ask_yes_no_cancel = app.show_warning = (
    lambda *a, **k: (_st_asked.append(a[0] if a else ''), None)[1])
try:
    app._edit_template(None, lambda: None); app.update()
    _st_boxes = []

    def _st_walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Entry):
                _st_boxes.append(c)
            _st_walk(c)
    _st_walk(app._mini_popup)
    _st_boxes[0].delete(0, 'end')
    _st_boxes[0].insert(0, 'Week plan')
    app.on_session_end(); app.update()
    _st_names = [t.get('name') for t in NO.load_templates()]
    check(f'a Windows sign-out keeps a template half written in its editor, beside '
          f'the one that has its name, asking nothing ({_st_names}, asked {_st_asked})',
          _st_names == ['Week plan', 'Week plan (2)'] and not _st_asked)
    # A sign-out can be cancelled, and the editor stays. It went on editing
    # the template it had opened, so a second sign-out added a "(3)", and its
    # own Save and close asked about work already written.
    _st_boxes[1].insert('end', 'Monday')
    app.on_session_end(); app.update()
    _st_again = [(t.get('name'), t.get('title')) for t in NO.load_templates()]
    _st_clean = app._mini_popup._confirm_dismiss()
    check(f'...and a second sign-out after one cancelled writes it again in its own '
          f'place, leaving the editor nothing unsaved ({_st_again}, {_st_clean}, '
          f'asked {_st_asked})',
          _st_again == [('Week plan', ''), ('Week plan (2)', 'Monday')]
          and _st_clean is True and not _st_asked)
finally:
    app.ask_yes_no, app.ask_yes_no_cancel, app.show_warning = _st_real
    app._dismiss_mini_popup()
    app.hide_settings_page(); app.update()
app.templates = []; NO.save_templates(app.templates)

# ...but at 1,000 templates it wrote a 1,001st, which the next start cut,
# unsaid: refused at the sign-out, and the next start says so.
app.templates = [NO.normalize_template({'name': 'T%d' % i, 'body': 'x'})
                 for i in range(1000)]
NO.save_templates(app.templates)
NO.save_setting('template_not_kept', None)
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()
_tf_real = (app.ask_yes_no, app.ask_yes_no_cancel, app.show_warning)
app.ask_yes_no = app.ask_yes_no_cancel = app.show_warning = lambda *a, **k: None
try:
    app._edit_template(None, lambda: None); app.update()
    _tf_boxes = []

    def _tf_walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Entry):
                _tf_boxes.append(c)
            _tf_walk(c)
    _tf_walk(app._mini_popup)
    _tf_boxes[0].delete(0, 'end')
    _tf_boxes[0].insert(0, 'Packing')
    app.on_session_end(); app.update()
    with open(NO.TEMPLATES_FILE, encoding='utf-8') as _f:
        _tf_written = len(json.load(_f))
    _tf_said = _next_start_says()
finally:
    app.ask_yes_no, app.ask_yes_no_cancel, app.show_warning = _tf_real
    app._dismiss_mini_popup()
    app.hide_settings_page(); app.update()
check(f'a sign-out at 1,000 templates writes no 1,001st, and the next start says it '
      f'was not kept ({_tf_written}, {_tf_said[:70]!r})',
      _tf_written == 1000 and '“Packing”' in _tf_said and 'was not kept' in _tf_said
      and NO.get_setting('template_not_kept') is None)
app.templates = []; NO.save_templates(app.templates)

# ...and one the templates file refuses at the sign-out went unsaid, listed on
# screen alone: the list as the file has it, and the next start says why.
app.templates = [NO.normalize_template({'name': 'Week plan', 'body': 'Mon'})]
NO.save_templates(app.templates)
NO.save_setting('template_not_kept', None)
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()
_tu_page = sys.modules['noteorganizer.ui.settings_page']
_tu_save_was = _tu_page.save_templates
app.ask_yes_no = app.ask_yes_no_cancel = app.show_warning = lambda *a, **k: None
try:
    app._edit_template(None, lambda: None); app.update()
    _tu_boxes = []

    def _tu_walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Entry):
                _tu_boxes.append(c)
            _tu_walk(c)
    _tu_walk(app._mini_popup)
    _tu_boxes[0].delete(0, 'end')
    _tu_boxes[0].insert(0, 'Packing')
    _tu_page.save_templates = lambda _t: (False, OSError(28, 'No space left on device'))
    app.on_session_end(); app.update()
    _tu_listed = [t.get('name') for t in app.templates]
    _tu_page.save_templates = _tu_save_was
    _tu_said = _next_start_says()
    # ...and a later sign-out whose write lands takes that word back: kept, the
    # next start said a template the file holds was not kept.
    _tu_page.save_templates = lambda _t: (False, OSError(28, 'No space left on device'))
    app._ending_session = False
    app.on_session_end(); app.update()
    _tu_page.save_templates = _tu_save_was
    _tu_word = NO.get_setting('template_not_kept')
    app._ending_session = False
    app.on_session_end(); app.update()
    _tu_after = (NO.get_setting('template_not_kept'), NO.get_setting('template_not_kept_why'),
                 [t.get('name') for t in NO.load_templates()])
finally:
    _tu_page.save_templates = _tu_save_was
    app.ask_yes_no, app.ask_yes_no_cancel, app.show_warning = _tf_real
    app._ending_session = False
    app._dismiss_mini_popup()
    app.hide_settings_page(); app.update()
check(f"a template the file refuses at a sign-out is not listed, and the next start says "
      f"why it was not kept ({_tu_listed}, {_tu_said[:110]!r})",
      _tu_listed == ['Week plan'] and '“Packing”' in _tu_said
      and 'was not kept: the templates file could not be written' in _tu_said)
check(f"...and a later sign-out whose write lands takes back that word and its reason "
      f"({_tu_word!r} -> {_tu_after})",
      _tu_word == 'Packing' and _tu_after[0] is None and _tu_after[1] is None
      and 'Packing' in _tu_after[2])
app.templates = []; NO.save_templates(app.templates)

# ...and with the sign-out cancelled, room made and the editor's own Save
# pressed, that word stayed: the next start said a template on disk was not
# kept.
app.templates = [NO.normalize_template({'name': 'T%d' % i, 'body': 'x'})
                 for i in range(1000)]
NO.save_templates(app.templates)
NO.save_setting('template_not_kept', None)
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()
app.ask_yes_no = app.ask_yes_no_cancel = app.show_warning = lambda *a, **k: None
try:
    app._edit_template(None, lambda: None); app.update()
    _tk_boxes = []

    def _tk_walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Entry):
                _tk_boxes.append(c)
            _tk_walk(c)
    _tk_walk(app._mini_popup)
    _tk_boxes[0].delete(0, 'end')
    _tk_boxes[0].insert(0, 'Packing')
    app.on_session_end(); app.update()
    _tk_word = NO.get_setting('template_not_kept')
    app._ending_session = False            # the sign-out was cancelled
    app.templates.pop()                    # room made
    app._mini_popup._save_from_keyboard(); app.update()
    _tk_said = _next_start_says()
finally:
    app.ask_yes_no, app.ask_yes_no_cancel, app.show_warning = _tf_real
    app._ending_session = False
    app._dismiss_mini_popup()
    app.hide_settings_page(); app.update()
check(f"a template saved after a cancelled sign-out refused it takes back the word that it "
      f"was not kept ({_tk_word!r}, {_tk_said[:60]!r})",
      _tk_word == 'Packing' and any(t.get('name') == 'Packing' for t in app.templates)
      and 'was not kept' not in _tk_said)
# ...but a Save the disk refuses leaves the word, still true: it was taken back.
app.templates = [NO.normalize_template({'name': 'T%d' % i, 'body': 'x'})
                 for i in range(1000)]
NO.save_templates(app.templates)
NO.save_setting('template_not_kept', None)
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()
app.ask_yes_no = app.ask_yes_no_cancel = app.show_warning = lambda *a, **k: None
_tr_page = sys.modules['noteorganizer.ui.settings_page']
_tr_save_was = _tr_page.save_templates
try:
    app._edit_template(None, lambda: None); app.update()
    _tk_boxes = []
    _tk_walk(app._mini_popup)
    _tk_boxes[0].delete(0, 'end')
    _tk_boxes[0].insert(0, 'Packing')
    app.on_session_end(); app.update()
    app._ending_session = False
    app.templates.pop()
    _tr_page.save_templates = lambda _t: (False, OSError(28, 'No space left on device'))
    app._mini_popup._save_from_keyboard(); app.update()
    _tr_word = NO.get_setting('template_not_kept')
    # It closed as if kept, the template gone at the next start: the editor
    # stays now with its words, the list as the file has it, and it is said.
    _tr_open = app._mini_popup is not None and app._mini_popup.winfo_exists()
    _tr_listed = any(t.get('name') == 'Packing' for t in app.templates)
    _tr_status = str(app.status_lbl.cget('text'))
finally:
    _tr_page.save_templates = _tr_save_was
    app.ask_yes_no, app.ask_yes_no_cancel, app.show_warning = _tf_real
    app._ending_session = False
    app._dismiss_mini_popup()
    app.hide_settings_page(); app.update()
check(f"...and a Save the disk refuses leaves that word, still true ({_tr_word!r})",
      _tr_word == 'Packing')
check(f"...keeps the editor open, the list as the file has it, and says it was not saved "
      f"(open {_tr_open}, listed {_tr_listed}, {_tr_status!r})",
      _tr_open and not _tr_listed
      and _tr_status.startswith('Not saved: the templates file could not be written'))
app.templates = []; NO.save_templates(app.templates)
NO.save_setting('template_not_kept', None)
# Said with "began to": true too of a sign-out the person cancelled.
NO.save_setting('template_not_kept', 'Packing list')
_tk_next = _next_start_says()
check(f'a template not kept is said as written when Windows began to sign out ({_tk_next[:120]!r})',
      'being written when Windows began to sign out or shut down, was not kept' in _tk_next)
app.templates = []; NO.save_templates(app.templates)

# A backup's Trash brings its window when this notebook never chose one:
# the default 30 days then emptied, at the next start, a Trash its owner
# kept for a year. A window chosen here stays.
_tw_backup = {'notes_data.json': json.dumps([{'title': 'Kept', 'body': 'x'}]).encode(),
              'trash.json': json.dumps([{'id': 7, 'uid': 'tw-7', 'title': 'Old',
                                         'deleted_at': '2026-03-01 09:00:00'}]).encode(),
              'settings.json': json.dumps({'trash_retention_days': 365,
                                           'app_version': '0.97.405'}).encode()}
_tw_settings = NO.load_settings()
_tw_settings.pop('trash_retention_days', None)
NO.save_settings(_tw_settings)
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)
_dz_import(_tw_backup)
check(f'a restored Trash keeps the window it came with, where none was chosen '
      f'({NO.trash_retention_days()} days)', NO.trash_retention_days() == 365)
NO.choose_trash_window(30)
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)
_dz_import(_tw_backup)
check(f'...and a window chosen here stays ({NO.trash_retention_days()} days)',
      NO.trash_retention_days() == 30)
_tw_settings = NO.load_settings()
_tw_settings.pop('trash_retention_days', None)
NO.save_settings(_tw_settings)
# ...and never a shorter one: this notebook's own Trash was deleted under
# the default's promise, and a backup from a 7-day notebook emptied it at
# the next start, files and all.
app.notes = []; app.save_notes()
app.trash = [dict(NO.normalize_note({'id': 3, 'title': 'Mine, 10 days ago'}),
                  deleted_at=time.strftime('%Y-%m-%d %H:%M:%S',
                                           time.localtime(time.time() - 10 * 86400)))]
NO.save_trash(app.trash)
_dz_import(dict(_tw_backup, **{'settings.json': json.dumps(
    {'trash_retention_days': 7, 'app_version': '0.97.405'}).encode()}))
check(f'a backup from a notebook that keeps its Trash for less does not shorten '
      f'the window here ({NO.trash_retention_days()} days, '
      f'saved: {"trash_retention_days" in NO.load_settings()})',
      NO.trash_retention_days() == NO.TRASH_RETENTION_DAYS
      and 'trash_retention_days' not in NO.load_settings())
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)
# ...and brings none of its Trash without that window: over settings held
# (their defaults stand in) or the window's write refused, the entries came in
# and the next start's 30 days removed them, files and all. Said, not done.
_tw_said = {}
# 'unknown': a backup from a notebook whose Trash length was lost (its settings
# carry the mark, no length) brought old entries in under this computer's 30 days.
_tw_unknown = dict(_tw_backup, **{'settings.json': json.dumps(
    {'desktop_trash_window_unknown': True, 'app_version': '0.97.405'}).encode()})
# 'trash held': an entry every window keeps, or the window alone left it out unwatched;
# filed under a category only it uses, which must not come in without it.
_tw_recent = dict(_tw_backup, **{'trash.json': json.dumps([{
    'id': 7, 'uid': 'tw-7', 'title': 'Old', 'deleted_at': _tr_days_ago(2),
    'category': 'QaHeldTrashCat'}]).encode()})
NO.CATEGORY_COLORS.pop('QaHeldTrashCat', None); NO.persist_categories()
_tw_cat_in = None
for _tw_case in ('held', 'refused', 'trash held', 'unknown'):
    app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)
    _tw_choose_was = NO.choose_trash_window
    if _tw_case == 'held':
        NO._core_paths.hold_writes(NO.SETTINGS_FILE)
    elif _tw_case == 'refused':
        NO.choose_trash_window = lambda _d: (False, OSError(28, 'No space left on device'))
    elif _tw_case == 'trash held':
        NO._core_paths.hold_writes(NO.TRASH_FILE)
    # Asked and told here, not through whatever an earlier check left in their
    # place: "Import complete" went to one of those, unheard.
    _tw_ask_was, _tw_info_was = app.__dict__.get('ask_yes_no'), app.__dict__.get('show_info')
    _tw_infos = []
    app.ask_yes_no = lambda *a, **k: True
    app.show_info = lambda title, msg='', *a, **k: _tw_infos.append((title, msg))
    try:
        _tw_msgs = _dz_import({'unknown': _tw_unknown, 'trash held': _tw_recent}.get(
            _tw_case, _tw_backup)) + _tw_infos
        # In memory alone, a held Trash's took showed under its "couldn't be read".
        _tw_shown = any(e.get('title') == 'Old' for e in app.trash)
        if _tw_case == 'trash held':
            _tw_cat_in = 'QaHeldTrashCat' in NO.CATEGORY_COLORS
    finally:
        for _tw_path in (NO.SETTINGS_FILE, NO.TRASH_FILE):
            NO._core_paths.WRITES_HELD.discard(os.path.normcase(os.path.abspath(_tw_path)))
        NO.choose_trash_window = _tw_choose_was
        for _tw_name, _tw_was in (('ask_yes_no', _tw_ask_was), ('show_info', _tw_info_was)):
            if _tw_was is None:
                app.__dict__.pop(_tw_name, None)
            else:
                setattr(app, _tw_name, _tw_was)
    _tw_said[_tw_case] = (
        _tw_shown,
        any(("trashed notes could not be written to disk" in m) if _tw_case == 'trash held'
            else ("of the backup's trashed notes" in m and "not brought in" in m)
            for _t, m in _tw_msgs))
    _tw_heard = (_tw_heard if _tw_case != 'held' else []) + [
        _tw_case, [(t, m[-120:]) for t, m in _tw_msgs]]
check(f"a backup's Trash is not brought in past the window this computer's next start "
      f"keeps, nor into a held Trash, and that is said ({_tw_said}; last heard {_tw_heard})",
      _tw_said == {'held': (False, True), 'refused': (False, True), 'trash held': (False, True),
                   'unknown': (False, True)})
# Kept out, but adopted before the Trash's write put them back, its entries'
# categories stood in the list with no note under them.
check(f"...nor, into a held Trash, a category only its entries use ({_tw_cat_in})",
      _tw_cat_in is False)
NO.CATEGORY_COLORS.pop('QaHeldTrashCat', None); NO.persist_categories()
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)

# A backup's templates into a templates file held this run stay in it: in memory
# alone they took the place of the held file's words, gone at the next start.
# And a note filed under a category its backup's settings lack keeps it: it
# came in under General, unsaid, where the start believes the note.
_tt_backup = dict(_tw_backup, **{
    'notes_data.json': json.dumps([{'title': 'Seeds', 'body': 'x', 'category': 'Garden'}]).encode(),
    'templates.json': json.dumps([{'name': 'From the backup', 'body': 'b'}]).encode()})
app.notes = []; app.save_notes(); app.templates = []; NO.save_templates(app.templates)
NO.CATEGORY_COLORS.pop('Garden', None); NO.persist_categories()
_tt_ask_was, _tt_info_was = app.__dict__.get('ask_yes_no'), app.__dict__.get('show_info')
_tt_infos = []
app.ask_yes_no = lambda *a, **k: True
app.show_info = lambda title, msg='', *a, **k: _tt_infos.append((title, msg))
NO._core_paths.hold_writes(NO.TEMPLATES_FILE)
try:
    _tt_msgs = _dz_import(_tt_backup) + _tt_infos
finally:
    NO._core_paths.WRITES_HELD.discard(os.path.normcase(os.path.abspath(NO.TEMPLATES_FILE)))
    for _tt_name, _tt_was in (('ask_yes_no', _tt_ask_was), ('show_info', _tt_info_was)):
        if _tt_was is None:
            app.__dict__.pop(_tt_name, None)
        else:
            setattr(app, _tt_name, _tt_was)
_tt_seeds = next((n for n in app.notes if n.get('title') == 'Seeds'), {})
check(f"a backup's templates into a held templates file stay in the backup, said; and its "
      f"note keeps a category its settings lack ({[t.get('name') for t in app.templates]}, "
      f"{_tt_seeds.get('category')!r})",
      app.templates == []
      and any('templates could not be written to disk' in m for _t, m in _tt_msgs)
      and _tt_seeds.get('category') == 'Garden' and 'Garden' in NO.CATEGORY_COLORS)
NO.CATEGORY_COLORS.pop('Garden', None); NO.persist_categories()
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)
# A backup's trashed note keeps a category only the Trash uses (General, unsaid);
# of two twins in its Trash the older left out took the newer, uncounted; and a
# name its notes use that a ceiling refuses went to General unsaid.
_tc_long = 'L' * (NO.MAX_CATEGORY_NAME + 1)
# Two more refused names, one only a note uses and one only the Trash: the
# settings' refusal of the first hid whether the notes' own was counted.
_tc_note_long = 'M' * (NO.MAX_CATEGORY_NAME + 1)
_tc_trash_long = 'T' * (NO.MAX_CATEGORY_NAME + 1)
_tc_backup = dict(_tw_backup, **{
    'notes_data.json': json.dumps([{'title': 'Long', 'body': 'x', 'category': _tc_long},
                                   {'title': 'Longer', 'body': 'z',
                                    'category': _tc_note_long}]).encode(),
    'trash.json': json.dumps([
        {'id': 13, 'uid': 'tc-13', 'title': 'Long shed', 'body': 'w',
         'category': _tc_trash_long, 'deleted_at': _tr_days_ago(6)},
        {'id': 8, 'uid': 'tc-8', 'title': 'Twin', 'body': 'same', 'deleted_at': _tr_days_ago(200)},
        {'id': 9, 'uid': 'tc-9', 'title': 'Twin', 'body': 'same', 'deleted_at': _tr_days_ago(2)},
        {'id': 10, 'uid': 'tc-10', 'title': 'Shed', 'body': 'y', 'category': 'OnlyInTrash',
         'deleted_at': _tr_days_ago(3)},
        # Twins under a category it adopts: signed under General before it, both came in.
        {'id': 11, 'uid': 'tc-11', 'title': 'Pair', 'body': 'p', 'category': 'QaPairCat',
         'deleted_at': _tr_days_ago(4)},
        {'id': 12, 'uid': 'tc-12', 'title': 'Pair', 'body': 'p', 'category': 'QaPairCat',
         'deleted_at': _tr_days_ago(5)}]).encode(),
    # The long name refused in its settings and on its note: counted once.
    'settings.json': json.dumps({'app_version': '0.97.405',
                                 'categories': {_tc_long: '#3a7d44'}}).encode()})
NO.CATEGORY_COLORS.pop('OnlyInTrash', None); NO.CATEGORY_COLORS.pop('QaPairCat', None)
NO.persist_categories()
_tc_settings = NO.load_settings()
_tc_window_was = _tc_settings.pop('trash_retention_days', None)   # this computer's 30 days
NO.save_settings(_tc_settings)
_tc_ask_was, _tc_info_was = app.__dict__.get('ask_yes_no'), app.__dict__.get('show_info')
_tc_infos = []
app.ask_yes_no = lambda *a, **k: True
app.show_info = lambda title, msg='', *a, **k: _tc_infos.append((title, msg))
try:
    _tc_msgs = ' '.join(m for _t, m in _dz_import(_tc_backup) + _tc_infos)
finally:
    for _tc_name, _tc_was in (('ask_yes_no', _tc_ask_was), ('show_info', _tc_info_was)):
        if _tc_was is None:
            app.__dict__.pop(_tc_name, None)
        else:
            setattr(app, _tc_name, _tc_was)
_tc_trash = {e.get('title'): e for e in app.trash}
_tc_saved = NO.load_settings().get('categories') or {}
# The restored parts as Import complete says them, each in the form its number
# takes: as many trashed notes as came in, "note" for one.
import re as _tc_re
_tc_restored = _tc_re.search(r"Also restored 2 categories and (\d+) trashed (notes?)\.", _tc_msgs)
check(f"a backup's trashed note keeps a category only the Trash uses, the newer of two twins "
      f"comes in, and a name a ceiling refuses is said ({sorted(_tc_trash)}, "
      f"{_tc_trash.get('Shed', {}).get('category')!r}; {_tc_msgs[-260:]!r})",
      _tc_trash.get('Shed', {}).get('category') == 'OnlyInTrash' and 'OnlyInTrash' in _tc_saved
      and 'Twin' in _tc_trash and "1 of the backup's trashed notes was not brought in" in _tc_msgs
      # The settings' and a note's long name counted once, a note's own and the
      # Trash's own once each.
      and "3 of the backup's categories could not be added" in _tc_msgs
      # ...and the two names only its Trash uses counted in the words, as case 1079 reads them.
      and bool(_tc_restored) and int(_tc_restored.group(1)) == len(app.trash)
      and (_tc_restored.group(2) == 'note') == (len(app.trash) == 1)
      and [e.get('category') for e in app.trash if e.get('title') == 'Pair'] == ['QaPairCat'])
NO.CATEGORY_COLORS.pop('OnlyInTrash', None); NO.CATEGORY_COLORS.pop('QaPairCat', None)
NO.persist_categories()
if _tc_window_was is not None:
    NO.choose_trash_window(_tc_window_was)
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)

# The map written again after the Trash, landed, takes back the first write's refusal: it
# writes the whole map. "The categories could not be written" stood over a file holding them.
_mw_backup = dict(_tw_backup, **{
    'notes_data.json': json.dumps([{'title': 'Peas', 'body': 'x', 'category': 'QaFirstCat'}]).encode(),
    'trash.json': json.dumps([{'id': 13, 'uid': 'mw-13', 'title': 'Hoe', 'body': 'h',
                               'category': 'QaSecondCat', 'deleted_at': _tr_days_ago(2)}]).encode(),
    'settings.json': json.dumps({'app_version': '0.97.405'}).encode()})
_mw_calls, _mw_persist_was = [], NO.persist_categories
NO.persist_categories = lambda: (_mw_calls.append(1), len(_mw_calls) > 1 and _mw_persist_was())[1]
_mw_ask_was, _mw_info_was = app.__dict__.get('ask_yes_no'), app.__dict__.get('show_info')
_mw_infos = []
app.ask_yes_no = lambda *a, **k: True
app.show_info = lambda title, msg='', *a, **k: _mw_infos.append((title, msg))
try:
    _mw_msgs = ' '.join(m for _t, m in _dz_import(_mw_backup) + _mw_infos)
finally:
    NO.persist_categories = _mw_persist_was
    for _mw_name, _mw_was in (('ask_yes_no', _mw_ask_was), ('show_info', _mw_info_was)):
        if _mw_was is None:
            app.__dict__.pop(_mw_name, None)
        else:
            setattr(app, _mw_name, _mw_was)
_mw_saved = NO.load_settings().get('categories') or {}
check(f"a backup's categories written by the map's second write are not said unwritten "
      f"({len(_mw_calls)} writes; {_mw_msgs[-160:]!r})",
      len(_mw_calls) == 2 and 'categories could not be written' not in _mw_msgs
      and 'QaFirstCat' in _mw_saved and 'QaSecondCat' in _mw_saved)
# ...and its one trashed note is said as one: the check above it brings several,
# so "1 trashed notes" passed every check.
check(f"Import complete says the one trashed note it restored in the singular "
      f"({_mw_msgs[-160:]!r})",
      'Also restored 2 categories and 1 trashed note.' in _mw_msgs)
for _mw_cat in ('QaFirstCat', 'QaSecondCat'):
    NO.CATEGORY_COLORS.pop(_mw_cat, None)
NO.persist_categories()
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)

# A category renamed or deleted over settings held this run moved every note, then the
# map's write was refused: the old name came back empty at the next start, a deleted one too.
NO.CATEGORY_COLORS['QaHeldCat'] = '#3a7d44'; NO.persist_categories()
app.notes = [NO.normalize_note({'id': 9301, 'title': 'Held cat', 'body': 'x', 'category': 'QaHeldCat'})]
app.save_notes()
_hc_warned = []
_hc_patched = ('show_warning', '_show_inline_rename', '_ask_category_deletion', 'ask_yes_no',
               'show_error', '_move_notes_to_trash')
_hc_was = {_hc_name: app.__dict__.get(_hc_name) for _hc_name in _hc_patched}
app.show_warning = lambda title, msg='', *a, **k: _hc_warned.append(
    (title, 'held' if "couldn't be read" in msg else 'unsaved' if "couldn't be saved" in msg else msg))
app._show_inline_rename = lambda _anchor, _default, on_name, **_limit: on_name('QaHeldCat2')
# Asked nothing when refused; answered here should a broken guard ask (it would wait for a click).
app._ask_category_deletion = lambda *a, **k: 'move'
app.ask_yes_no = lambda *a, **k: True
app.show_error = lambda *a, **k: None
_hc_frame = tk.Frame(app)
_hc_frame.pack()


def _hc_walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _hc_walk(child)


_sp_module = sys.modules['noteorganizer.ui.settings_page']
_sp_persist_was = _sp_module.persist_categories
_hc_seen = {}
app._build_category_row(_hc_frame, 'QaHeldCat', lambda: None)
app.update()
_hc_pencil = next(w for w in _hc_walk(_hc_frame) if getattr(w, '_icon_kind', None) == 'pencil')
try:
    # Over held settings or a held notes file, then with the list's own write refused: the
    # rename first, then the delete, each said, nothing moved (renamed or deleted, the row
    # beneath a later rename would no longer exist).
    for _hc_case in ('settings', 'notes', 'refused'):
        _hc_warned.clear()
        if _hc_case == 'refused':
            _sp_module.persist_categories = lambda: False
        else:
            NO._core_paths.hold_writes(NO.SETTINGS_FILE if _hc_case == 'settings' else NO.DATA_FILE)
        try:
            _hc_pencil.event_generate('<Button-1>')
            app.update()
            app._delete_category('QaHeldCat', lambda: None)
        finally:
            _sp_module.persist_categories = _sp_persist_was
            for _hc_path in (NO.SETTINGS_FILE, NO.DATA_FILE):
                NO._core_paths.WRITES_HELD.discard(os.path.normcase(os.path.abspath(_hc_path)))
        _hc_seen[_hc_case] = (list(_hc_warned), [n.get('category') for n in app.notes],
                              list(NO.CATEGORY_COLORS).count('QaHeldCat'),
                              'QaHeldCat2' in NO.CATEGORY_COLORS)
    # ...and a delete whose notes the Trash refuses puts the list it wrote first back.
    app._ask_category_deletion = lambda *a, **k: 'delete_notes'
    app._move_notes_to_trash = lambda *a, **k: None
    app._delete_category('QaHeldCat', lambda: None)
    _hc_trash_refused = ('QaHeldCat' in NO.CATEGORY_COLORS,
                         'QaHeldCat' in (NO.load_settings().get('categories') or {}),
                         [n.get('category') for n in app.notes])
finally:
    for _hc_name in _hc_patched:
        if _hc_was[_hc_name] is None:
            app.__dict__.pop(_hc_name, None)
        else:
            setattr(app, _hc_name, _hc_was[_hc_name])
    _hc_frame.destroy()
def _hc_still(why):
    return ([("Can't rename it now", why), ("Can't delete it now", why)], ['QaHeldCat'], 1, False)


check(f"over settings held this run a category is neither deleted nor renamed, and that is said; "
      f"over held notes, or the list's write refused, too ({_hc_seen})",
      _hc_seen == {'settings': _hc_still('held'), 'notes': _hc_still('held'),
                   'refused': _hc_still('unsaved')})
check(f"a category delete whose notes the Trash refuses keeps the category, in the list and "
      f"on disk ({_hc_trash_refused})",
      _hc_trash_refused == (True, True, ['QaHeldCat']))
NO.CATEGORY_COLORS.pop('QaHeldCat', None); NO.persist_categories()
app.notes = []; app.save_notes()

# A backup's trashed notes under a name this computer's map lacks are signed after it is
# adopted: signed first, under General, one under another name was taken for its twin, and
# one already here under that name came in again.
NO.CATEGORY_COLORS.pop('QaSigned', None); NO.persist_categories()
app.trash = [{'id': 21, 'uid': 'sg-here', 'title': 'Here', 'body': 'h', 'category': 'QaSigned',
              'deleted_at': _tr_days_ago(1)}]
NO.save_trash(app.trash)
_sg_backup = dict(_tw_backup, **{
    'notes_data.json': json.dumps([{'title': 'Any', 'body': 'a'}]).encode(),
    'trash.json': json.dumps([
        {'id': 22, 'uid': 'sg-g', 'title': 'Pea', 'body': 'p', 'deleted_at': _tr_days_ago(2)},
        {'id': 23, 'uid': 'sg-s', 'title': 'Pea', 'body': 'p', 'category': 'QaSigned',
         'deleted_at': _tr_days_ago(2)},
        {'id': 24, 'uid': 'sg-h', 'title': 'Here', 'body': 'h', 'category': 'QaSigned',
         'deleted_at': _tr_days_ago(1)},
        # Its General twin is another note: this Trash signed before the adoption took it for one.
        {'id': 26, 'uid': 'sg-hg', 'title': 'Here', 'body': 'h', 'deleted_at': _tr_days_ago(1)},
        # Left in the backup by the length: its category is not adopted, an empty one said restored.
        {'id': 25, 'uid': 'sg-o', 'title': 'Long gone', 'body': 'g', 'category': 'QaOldCat',
         'deleted_at': _tr_days_ago(400)}]).encode(),
    'settings.json': json.dumps({'app_version': '0.97.405'}).encode()})
_sg_ask_was, _sg_info_was = app.__dict__.get('ask_yes_no'), app.__dict__.get('show_info')
app.ask_yes_no = lambda *a, **k: True
app.show_info = lambda *a, **k: None
try:
    _dz_import(_sg_backup)
finally:
    for _sg_name, _sg_was in (('ask_yes_no', _sg_ask_was), ('show_info', _sg_info_was)):
        if _sg_was is None:
            app.__dict__.pop(_sg_name, None)
        else:
            setattr(app, _sg_name, _sg_was)
_sg_trash = sorted((e.get('title'), e.get('category')) for e in app.trash)
check(f"a backup's trashed notes are signed under the names they are kept by: a twin under "
      f"another name comes in, one already here does not come again, and one left out adopts "
      f"nothing ({_sg_trash}, {'QaOldCat' in NO.CATEGORY_COLORS})",
      _sg_trash == [('Here', 'General'), ('Here', 'QaSigned'), ('Pea', 'General'), ('Pea', 'QaSigned')]
      and 'QaOldCat' not in NO.CATEGORY_COLORS)
NO.CATEGORY_COLORS.pop('QaSigned', None); NO.CATEGORY_COLORS.pop('QaOldCat', None)
NO.persist_categories()
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)

# A backup's trashed note whose file a note here uses comes in on a copy of that file, signed
# under the copy's name: every import of that backup brought it in again, with another copy.
_rf_name = '20261114120000000000_r.png'
with open(os.path.join(NO.ATTACHMENTS_DIR, _rf_name), 'wb') as _fh:
    _fh.write(b'qa3 recipe picture')
app.notes = [NO.normalize_note({'id': 31, 'uid': 'rf-n', 'title': 'Recipe', 'body': 'r',
                                'attachments': [{'stored_as': _rf_name, 'filename': 'r.png'}]})]
app.save_notes()
_rf_backup = dict(_tw_backup, **{
    'notes_data.json': json.dumps([{'title': 'Other', 'body': 'o'}]).encode(),
    'trash.json': json.dumps([{'id': 32, 'uid': 'rf-t', 'title': 'Recipe', 'body': 'r',
                               'deleted_at': _tr_days_ago(2),
                               'attachments': [{'stored_as': _rf_name, 'filename': 'r.png'}]}]).encode(),
    'attachments/' + _rf_name: b'qa3 recipe picture',
    'settings.json': json.dumps({'app_version': '0.97.405'}).encode()})
_rf_ask_was, _rf_info_was = app.__dict__.get('ask_yes_no'), app.__dict__.get('show_info')
app.ask_yes_no = lambda *a, **k: True
app.show_info = lambda *a, **k: None
try:
    _dz_import(_rf_backup)
    _rf_first = sum(1 for e in app.trash if e.get('title') == 'Recipe')
    _dz_import(_rf_backup)
finally:
    for _rf_name_was, _rf_was in (('ask_yes_no', _rf_ask_was), ('show_info', _rf_info_was)):
        if _rf_was is None:
            app.__dict__.pop(_rf_name_was, None)
        else:
            setattr(app, _rf_name_was, _rf_was)
_rf_again = sum(1 for e in app.trash if e.get('title') == 'Recipe')
check(f"a backup's trashed note on a copy of a file a note here uses is not brought in again by "
      f"a second import ({_rf_first}, {_rf_again})",
      _rf_first == 1 and _rf_again == 1)
# ...and the question whether a backup of look-alikes brings anything more knows it the same way:
# "the rest of this import still happens" was said of nothing.
_rf_entry = json.loads(_rf_backup['trash.json'].decode())[0]
check(f"a backup whose only trashed note is here on a copy of its file brings nothing more "
      f"({app._backup_brings_more({'imported_trash': [_rf_entry]}, [])})",
      app._backup_brings_more({'imported_trash': [_rf_entry]}, []) is False)
# ...and an older writer's label ("photo.jpg" over a .png) here, raw, beside the backup's shaped
# one, never matched: the same note on a copy came in at every import.
for _lb_n in (0, 1):
    with open(os.path.join(NO.ATTACHMENTS_DIR, f'2026111414000000000{_lb_n}_photo.png'), 'wb') as _fh:
        _fh.write(b'qa3 photo')
_lb_here = {'id': 51, 'uid': 'lb-1', 'title': 'Pic', 'body': 'p', 'deleted_at': _tr_days_ago(1),
            'attachments': [{'filename': 'photo.jpg', 'stored_as': '20261114140000000000_photo.png'}]}
_lb_there = NO.normalize_note(dict(_lb_here, attachments=[
    {'filename': 'photo.jpg', 'stored_as': '20261114140000000001_photo.png'}]))
_lb_known = any(NO._same_files(_lb_there, h)
                for h in NO._loosely_signed([_lb_here]).get(NO._loose_signature(_lb_there), ()))
check(f"a trashed note here under an older writer's raw label is known beside the backup's "
      f"shaped one ({_lb_known})", _lb_known)
# ...nor one whose trashed note would come in, over a Trash held this run: the merge brings none.
_rf_new = dict(_rf_entry, uid='rf-new', title='Not here', attachments=[])
_rf_free = app._backup_brings_more({'imported_trash': [_rf_new]}, [])
NO._core_paths.hold_writes(NO.TRASH_FILE)
try:
    _rf_held = app._backup_brings_more({'imported_trash': [_rf_new]}, [])
finally:
    NO._core_paths.WRITES_HELD.discard(os.path.normcase(os.path.abspath(NO.TRASH_FILE)))
check(f"over a held Trash a backup's trashed notes are not said to bring more ({_rf_free}, {_rf_held})",
      _rf_free is True and _rf_held is False)
# ...nor over held settings (none comes in, the length not known), nor a template over a held
# templates file (put back, said unwritten): Skip promised "the rest" of nothing.
_rf_more = {}
for _rf_path, _rf_state in ((NO.SETTINGS_FILE, {'imported_trash': [_rf_new]}),
                            (NO.TEMPLATES_FILE, {'imported_templates': [{'name': 'Qa weekly'}]})):
    _rf_open = app._backup_brings_more(_rf_state, [])
    NO._core_paths.hold_writes(_rf_path)
    try:
        _rf_more[os.path.basename(_rf_path)] = (_rf_open, app._backup_brings_more(_rf_state, []))
    finally:
        NO._core_paths.WRITES_HELD.discard(os.path.normcase(os.path.abspath(_rf_path)))
check(f"over held settings or a held templates file a backup is not said to bring more ({_rf_more})",
      _rf_more == {'settings.json': (True, False), 'templates.json': (True, False)})
# ...and each part asked as the merge takes it, as the phone's question asks: a template with no
# name comes in "Untitled template", none past the cap; a trashed note older than this computer
# keeps stays in the backup; a name only the backup's Trash uses is adopted before it is signed
# (here beside a General twin); a day's mark only on a real day, in a colour kept.
_rf_ask = {
    'unnamed template': {'imported_templates': [{'name': '', 'title': 'x'}]},
    'trashed long ago': {'imported_trash': [dict(_rf_new, deleted_at=_tr_days_ago(400))]},
    'no real day': {'imported_day_colors': {'not a day': '#ff0000', '2026-11-14': 'not a colour'}},
}
_rf_said = {k: app._backup_brings_more(v, []) for k, v in _rf_ask.items()}
_rf_templates_was, _rf_trash_was = app.templates, app.trash
app.templates = [{'name': f'Qa T{_i}'} for _i in range(NO.MAX_TEMPLATES)]
app.trash = [dict(_rf_new, category='General')]
try:
    _rf_said['a template past the cap'] = app._backup_brings_more(
        {'imported_templates': [{'name': 'Qa new'}]}, [])
    _rf_said['a name only its Trash uses'] = app._backup_brings_more(
        {'imported_trash': [dict(_rf_new, category='QaTrashOnly')]}, [])
finally:
    app.templates, app.trash = _rf_templates_was, _rf_trash_was
check(f"the question whether a backup brings more asks each part as the merge takes it ({_rf_said})",
      _rf_said == {'unnamed template': True, 'trashed long ago': False, 'no real day': False,
                   'a template past the cap': False, 'a name only its Trash uses': True})
# ...by the length the merge keeps them by: a backup's longer window, taken where none was chosen
# here, keeps a note deleted 45 days ago, which this computer's own 30 would not.
_rf_settings = NO.load_settings()
_rf_chosen = _rf_settings.pop('trash_retention_days', None)
NO.save_settings(_rf_settings)
_rf_45 = {'imported_trash': [dict(_rf_new, deleted_at=_tr_days_ago(45))]}
try:
    _rf_window = (app._backup_brings_more(dict(_rf_45, imported_trash_window=90), []),
                  app._backup_brings_more(_rf_45, []))
finally:
    if _rf_chosen is not None:
        _rf_settings['trash_retention_days'] = _rf_chosen
        NO.save_settings(_rf_settings)
check(f"a backup's longer Trash window, taken where none was chosen here, is the length its trashed "
      f"notes are asked by ({_rf_window})", _rf_window == (True, False))
# A backup's trashed notes whose Trash write is refused for a moment are put back, as its templates
# are: listed for the session, they were gone at the next start.
_pb_real, _pb_real_info = NO.save_trash, app.show_info
_pb_said = []
# Its file used by a note here, the entry was given a copy: put back, nothing named the copy.
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
with open(os.path.join(NO.ATTACHMENTS_DIR, 'qa3_pb_shared.txt'), 'w') as _fh:
    _fh.write('shared')
app.notes = [NO.normalize_note({'id': 1, 'title': 'Holder', 'body': 'h', 'attachments': [
    {'filename': 'shared.txt', 'stored_as': 'qa3_pb_shared.txt'}]})]
app.save_notes()
_pb_files = sorted(os.listdir(NO.ATTACHMENTS_DIR))
NO.save_trash = lambda *a, **k: (False, 'refused')
app.show_info = lambda *a, **k: (_pb_said.append(' '.join(str(x) for x in a)), True)[1]
try:
    _dz_import({'notes_data.json': b'[]', 'trash.json': json.dumps(
        [dict(_rf_new, uid='pb-1', title='Put back', deleted_at=_tr_days_ago(1), attachments=[
            {'filename': 'shared.txt', 'stored_as': 'qa3_pb_shared.txt'}])]).encode()})
finally:
    NO.save_trash, app.show_info = _pb_real, _pb_real_info
_pb_listed = [e.get('title') for e in app.trash if e.get('title') == 'Put back']
_pb_left = sorted(os.listdir(NO.ATTACHMENTS_DIR))
check(f"a backup's trashed notes the Trash would not take are put back, said, and leave no copy "
      f"of a file behind ({_pb_listed}, {_pb_said[-1:]}, {set(_pb_left) - set(_pb_files)})",
      not _pb_listed and any('trashed notes could not be written' in s for s in _pb_said)
      and _pb_left == _pb_files)
app.notes = []; app.save_notes()
os.remove(os.path.join(NO.ATTACHMENTS_DIR, 'qa3_pb_shared.txt'))
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)

# A backup's note whose file is held by this Trash came in on a copy of it; matched by its
# identity at the next import, its files were compared by stored name, so it was asked about
# as "edited elsewhere" at every import, and each Update added one more copy.
_nf_name = '20261114130000000000_n.pdf'
with open(os.path.join(NO.ATTACHMENTS_DIR, _nf_name), 'wb') as _fh:
    _fh.write(b'qa3 note file')
app.trash = [{'id': 41, 'uid': 'nf-t', 'title': 'Gone', 'body': 'g', 'deleted_at': _tr_days_ago(1),
              'attachments': [{'stored_as': _nf_name, 'filename': 'n.pdf'}]}]
NO.save_trash(app.trash)
_nf_backup = dict(_tw_backup, **{
    'notes_data.json': json.dumps([{'id': 42, 'uid': 'nf-n', 'title': 'Kept', 'body': 'k',
                                    'attachments': [{'stored_as': _nf_name, 'filename': 'n.pdf'}]}]).encode(),
    'trash.json': json.dumps([]).encode(),
    'attachments/' + _nf_name: b'qa3 note file',
    'settings.json': json.dumps({'app_version': '0.97.405'}).encode()})
_nf_ask_was, _nf_info_was = app.__dict__.get('ask_yes_no'), app.__dict__.get('show_info')
app.ask_yes_no = lambda *a, **k: True
app.show_info = lambda *a, **k: None
try:
    _dz_import(_nf_backup)
    # Its last button for every question: "Update it" when it is asked as edited elsewhere,
    # the road where each Update added one more copy.
    _nf_said = _dz_import(_nf_backup, answer=lambda *a, **k: (k.get('buttons') or [(None, True)])[-1][1])
finally:
    for _nf_name_was, _nf_was in (('ask_yes_no', _nf_ask_was), ('show_info', _nf_info_was)):
        if _nf_was is None:
            app.__dict__.pop(_nf_name_was, None)
        else:
            setattr(app, _nf_name_was, _nf_was)
_nf_note = next((n for n in app.notes if n.get('uid') == 'nf-n'), {})
_nf_files = [a.get('filename') for a in _nf_note.get('attachments') or []]
check(f"a backup's note that came in on a copy of a file is not asked about again, nor given "
      f"another copy ({_nf_files}; {[t for t, _m in _nf_said]})",
      _nf_files == ['n.pdf'] and not any('edited elsewhere' in (t + m) for t, m in _nf_said))
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)

# A Trash entry is kept as the file held it, and four readers still read its
# fields raw: a title of 7 kept Recently deleted from opening, comments or
# files of the wrong type broke a row's hover and left its window behind, and
# a files field of 7 stopped a backup's merge after its files were copied.
app.trash = [
    {'id': 11, 'deleted_at': '2026-10-20 10:00:00', 'title': 5},
    {'id': 12, 'deleted_at': '2026-10-20 10:00:00', 'title': ['a'], 'comments': 9},
    {'id': 13, 'deleted_at': '2026-10-20 10:00:00', 'title': 'Seven', 'attachments': 7},
    {'id': 14, 'deleted_at': '2026-10-20 10:00:00', 'title': 'List',
     'attachments': [1, 2]}]
NO.save_trash(app.trash)
_dz_import({'notes_data.json': json.dumps([{'title': 'From backup', 'body': 'x'}]).encode()})
check('a backup merges beside Trash entries whose files field is not a list',
      any(n.get('title') == 'From backup' for n in app.notes))
_rt_errors = []
_rt_real_report = app.report_callback_exception
app.report_callback_exception = lambda *a: _rt_errors.append(str(a[1]))
try:
    # Caught, so a broken panel is this check's FAIL, not the suite's end.
    try:
        app.show_settings_page()
        app.toggle_settings_panel('trash')
        app.update()
    except Exception as _rt_exc:
        _rt_errors.append(repr(_rt_exc))
    _rt_rows = _trash_rows()
    check(f'Recently deleted opens with every damaged entry drawn '
          f'({len(_rt_rows)} rows; errors {_rt_errors})',
          len(_rt_rows) == 4 and not _rt_errors)
    _rt_top = set(app.winfo_children())
    for _rt_row in _rt_rows:
        for _rt_w in _rt_row.winfo_children():
            if isinstance(_rt_w, tk.Frame):
                _rt_w.event_generate('<Enter>', x=2, y=2); app.update()
                _rt_w.event_generate('<Leave>'); app.update()
    _rt_left = [w for w in app.winfo_children()
                if isinstance(w, tk.Toplevel) and w not in _rt_top and w.winfo_exists()]
    check(f'...and hovering each row raises nothing and leaves no preview behind '
          f'(errors {_rt_errors}; left behind {len(_rt_left)})',
          not _rt_errors and not _rt_left)
finally:
    app.report_callback_exception = _rt_real_report
    app.hide_settings_page(); app.update()
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)

# ---- KEYBOARD in Recently deleted: a row's ring, its order, and where the
# keyboard goes after a row's Restore or Delete ----
# The tick box has no words, so Windows drew no dotted ring round it; Delete
# came before Restore in Tab's order and Select all after the list it sits
# above; and Space on a row's Restore left the keyboard on the window.
def _kt_settle(n=6):
    for _ in range(n):
        app.update()
        time.sleep(0.02)


from _qa_support import take_focus as _qa_take_focus  # noqa: E402


def _kt_take(w, cap_s=2.0):
    return _qa_take_focus(app, w, cap_s)


def _kt_rows():
    found = []

    def walk(w):
        for c in w.winfo_children():
            if getattr(c, '_trash_buttons', None):
                found.append(c)
            else:
                walk(c)
    walk(app.settings_page)
    return found


def _kt_tick(row):
    return next((c for c in row.winfo_children()
                 if isinstance(c, tk.Checkbutton)), None)


def _kt_ringed():
    return [i for i, r in enumerate(_kt_rows())
            if str(r.cget('highlightbackground')).lower()
            == str(r.cget('highlightcolor')).lower()
            == app._focus_ring().lower()]


app.trash = [{'id': 600 + i, 'uid': f'kt-{i}', 'title': f'KeyTrash{i}', 'body': 'x',
              'category': 'General', 'deleted_at': f'2026-10-{20 - i:02d} 10:00:00'}
             for i in range(6)]
NO.save_trash(app.trash)
app.show_settings_page(); app.toggle_settings_panel('trash')
_kt_settle(10)
_kt_r = _kt_rows()
check(f'fixture: six Trash rows drawn, each with its tick box ({len(_kt_r)})',
      len(_kt_r) == 6 and all(_kt_tick(r) is not None for r in _kt_r))
if len(_kt_r) == 6 and _kt_take(_kt_tick(_kt_r[1])):
    _kt_settle(2)
    _kt_one = _kt_ringed()
    _kt_take(_kt_tick(_kt_rows()[3]))
    _kt_settle(2)
    check(f'the Trash row whose tick box holds the keyboard wears the ring, and '
          f'only that row ({_kt_one}, then {_kt_ringed()})',
          _kt_one == [1] and _kt_ringed() == [3])
_kt_r = _kt_rows()
if _kt_r:
    _kt_b = _kt_r[0]._trash_buttons
    check('Tab reads a Trash row left to right: its tick box, Restore, Delete',
          _kt_tick(_kt_r[0]).tk_focusNext() is _kt_b['restore']
          and _kt_b['restore'].tk_focusNext() is _kt_b['delete'])
    _kt_sel = find_btn(app.settings_page, 'Select all')
    check('Select all, drawn above the list, comes before it in Tab\'s order',
          _kt_sel is not None and _kt_sel.tk_focusNext() is _kt_tick(_kt_r[0]))

_kt_asked = []
_kt_real_focus_set = tk.Misc.focus_set


def _kt_record(self):
    _kt_asked.append(self)
    return _kt_real_focus_set(self)


tk.Misc.focus_set = _kt_record
try:
    _kt_r = _kt_rows()
    _kt_gone = _kt_r[2]._trash_buttons if len(_kt_r) > 2 else None
    _kt_title = 'KeyTrash2'
    if _kt_gone is not None and _kt_take(_kt_gone['restore']):
        del _kt_asked[:]
        _kt_gone['restore'].event_generate('<space>')
        _kt_settle()
    _kt_r = _kt_rows()
    check(f'Space on a row\'s Restore puts that note back, and the row drawn in '
          f'its place takes the keyboard on its own Restore ({_kt_asked})',
          not any(e.get('title') == _kt_title for e in app.trash)
          and len(_kt_r) == 5 and _kt_r[2]._trash_buttons['restore'] in _kt_asked)
    if _kt_r and _kt_take(_kt_r[-1]._trash_buttons['delete']):
        del _kt_asked[:]
        _kt_r[-1]._trash_buttons['delete'].event_generate('<space>')
        _kt_settle()
    _kt_r = _kt_rows()
    check(f'Space on the last row\'s Delete deletes it, and the new last row '
          f'takes the keyboard on its Delete ({_kt_asked})',
          len(_kt_r) == 4 and _kt_r[-1]._trash_buttons['delete'] in _kt_asked)
    # A click is not the keyboard: the mouse's Restore moves nothing.
    if _kt_r and _kt_take(_kt_tick(_kt_r[0])):
        del _kt_asked[:]
        _kt_r[1]._trash_buttons['restore'].invoke()
        _kt_settle()
    check(f'a Restore pressed by the mouse sends the keyboard nowhere '
          f'({_kt_asked})', len(_kt_rows()) == 3 and not any(
              getattr(w.master, '_trash_buttons', None) for w in _kt_asked))
finally:
    tk.Misc.focus_set = _kt_real_focus_set
app.hide_settings_page()
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)
_kt_settle()

# ---- KEYBOARD: the delete toast's Undo ----
# A label bound to the mouse alone, gone after eight seconds: from the
# keyboard a delete could not be taken back where it was made.
app.notebook.select(app.TAB_NOTES)
_kz_note = _undo_seed('KeyUndoMe')
app.refresh_note_list(); _kt_settle()
app._delete_note(_kz_note, None); _kt_settle(2)
check('fixture: the delete went to the Trash, and the toast offers Undo',
      'KeyUndoMe' in _trash_titles() and app._toast_action is not None)
if _kt_take(app.canvas):
    app.canvas.event_generate('<Control-z>')
    _kt_settle()
check('Ctrl+Z on the note list, while the toast offers Undo, takes the offer',
      'KeyUndoMe' in _titles() and 'KeyUndoMe' not in _trash_titles()
      and app._toast_action is None)
_kz_back = next((n for n in app.notes if n.get('title') == 'KeyUndoMe'), None)
if _kz_back is not None:
    app._delete_note(_kz_back, None)
    _kt_settle(2)
# A delete leaves the keyboard in the new note's title, which has no undo of
# its own: Ctrl+Z there did nothing at all.
if _kt_take(app.title_entry):
    app.title_entry.event_generate('<Control-z>')
    _kt_settle()
check('...and in the title, which has no undo of its own, it takes the offer too',
      'KeyUndoMe' in _titles() and 'KeyUndoMe' not in _trash_titles())
_kz_back = next((n for n in app.notes if n.get('title') == 'KeyUndoMe'), None)
if _kz_back is not None:
    app._delete_note(_kz_back, None)
    _kt_settle(2)
# ...but not in a title typed in since: the next note's typo "undone" brought
# the deleted note back over it.
app.title_entry.insert(0, 'Shopping lisr')
if _kt_take(app.title_entry):
    app.title_entry.event_generate('<Control-z>')
    _kt_settle()
check('...but in a title typed in since the delete, Ctrl+Z leaves the deleted note where it is',
      'KeyUndoMe' in _trash_titles() and app._toast_action is not None)
app.title_entry.delete(0, 'end')
# ...and in the blank note's text and comments, which take Ctrl+Z themselves:
# with nothing to take back the press ended there, and did nothing.
_kz_boxes = []
for _kz_box in (app.body_text, app.comments_text):
    if _kt_take(_kz_box):
        _kz_box.event_generate('<Control-z>')
        _kt_settle()
    _kz_boxes.append('KeyUndoMe' in _titles() and 'KeyUndoMe' not in _trash_titles())
    _kz_back = next((n for n in app.notes if n.get('title') == 'KeyUndoMe'), None)
    if _kz_back is not None:
        app._delete_note(_kz_back, None)
        _kt_settle(2)
check(f'...and in the note\'s text and comments with nothing to take back, it takes the offer '
      f'({_kz_boxes})', _kz_boxes == [True, True])
app.body_text.insert('end', 'typed here')
app.body_text.edit_separator()
if _kt_take(app.body_text):
    app.body_text.event_generate('<Control-z>')
    _kt_settle()
check('...but in a text box with typing of its own Ctrl+Z is the box\'s, and the offer stays',
      'KeyUndoMe' in _trash_titles() and app._toast_action is not None)
app.body_text.delete('1.0', 'end')
# ...and in the note's text holding only a redo step -- a typo taken back a
# moment before -- it takes the offer: read as this press's, the press did
# nothing at all.
app.body_text.edit_reset()
app.body_text.insert('end', 'oops'); app.body_text.edit_separator()
app.body_text.edit_undo()
if _kt_take(app.body_text):
    app.body_text.event_generate('<Control-z>')
    _kt_settle()
check(f"...and in the note's text holding only a redo step, it takes the offer "
      f"({app._can_edit_redo(app.body_text)})",
      'KeyUndoMe' in _titles() and 'KeyUndoMe' not in _trash_titles())
_kz_back = next((n for n in app.notes if n.get('title') == 'KeyUndoMe'), None)
if _kz_back is not None:
    app._delete_note(_kz_back, None)
    _kt_settle(2)
app.body_text.delete('1.0', 'end')
# A text box with an undo of its own and no Ctrl+Z binding (Tk's own <<Undo>>
# takes it back): the offer stays, or one press undid twice. One step only:
# with two, the box could still undo after the press, and the check passed
# whatever the order (a table cell's last typing).
_kz_own = tk.Text(app, undo=True, height=1, width=10)
_kz_own.place(x=0, y=0)
_kz_own.insert('end', 'one'); _kz_own.edit_separator()
if _kt_take(_kz_own):
    _kz_own.event_generate('<Control-z>')
    _kt_settle()
check(f'...and in any box with an undo of its own, the box\'s too, its last step as well '
      f'({_kz_own.get("1.0", "end-1c")!r})',
      _kz_own.get("1.0", "end-1c") == '' and 'KeyUndoMe' in _trash_titles() and app._toast_action is not None)
# ...but such a box holding only a redo step -- its last typing taken back a
# moment before -- takes the offer: read off the redo step left, the press
# did nothing at all (a table cell).
_kz_own.edit_reset()
_kz_own.insert('end', 'x'); _kz_own.edit_separator()
_kz_own.edit_undo()
if _kt_take(_kz_own):
    _kz_own.event_generate('<Control-z>')
    _kt_settle()
check("...and such a box holding only a redo step takes the offer",
      'KeyUndoMe' in _titles() and 'KeyUndoMe' not in _trash_titles())
_kz_back = next((n for n in app.notes if n.get('title') == 'KeyUndoMe'), None)
if _kz_back is not None:
    app._delete_note(_kz_back, None)
    _kt_settle(2)
# ...but Ctrl+Shift+Z there, the guide's Redo, never takes it: bound for Caps
# Lock, <Control-Z> took it too.
_kz_own.edit_reset()
_kz_own.insert('end', 'y'); _kz_own.edit_separator()
_kz_own.edit_undo()
if _kt_take(_kz_own):
    _kz_own.event_generate('<Control-Shift-Z>')
    _kt_settle()
# ...and on the list, which no text box's own Redo answers first.
if _kt_take(app.canvas):
    app.canvas.event_generate('<Control-Shift-Z>')
    _kt_settle()
check("...but Ctrl+Shift+Z, the Redo key, leaves the offer where it is",
      'KeyUndoMe' in _trash_titles() and app._toast_action is not None)
_kz_own.destroy()
check('the toast\'s Undo is a Tab stop',
      str(app.toast_action_lbl.cget('takefocus')) == '1')
_kz_waited = False
if app._toast_hide_job is not None and _kt_take(app.toast_action_lbl):
    # Its timer's own callback, run now: with the keyboard on Undo it waits.
    _kz_job = app._toast_hide_job
    _kz_script = app.tk.splitlist(app.tk.call('after', 'info', _kz_job))[0]
    app.tk.eval(_kz_script)
    app.tk.call('after', 'cancel', _kz_job)     # it ran; Tcl's copy must not
    _kt_settle(2)
    _kz_waited = bool(app.toast_frame.winfo_ismapped()) and app._toast_action is not None
    app.toast_action_lbl.event_generate('<space>')
    _kt_settle()
check(f'while the keyboard is on Undo the toast waits for it ({_kz_waited}), '
      f'and Space takes the offer',
      _kz_waited and 'KeyUndoMe' in _titles() and 'KeyUndoMe' not in _trash_titles())
app._hide_toast()
# What Tk's own Undo took is that press's only: a Caps Lock Ctrl+Z in the
# comments with no offer up left its word for the next press there, which then
# did nothing while the banner offered Undo.
app.comments_text.insert('end', 'TODO'); app.comments_text.edit_separator()
app.comments_text.event_generate('<<Undo>>')
_kt_settle()
_kz_back = next((n for n in app.notes if n.get('title') == 'KeyUndoMe'), None)
if _kz_back is not None:
    app._delete_note(_kz_back, None)
    _kt_settle(2)
if _kt_take(app.comments_text):
    app.comments_text.event_generate('<Control-z>')
    _kt_settle()
check("...and a Caps Lock Ctrl+Z with no offer up leaves no word for the next press",
      _kz_back is not None and 'KeyUndoMe' in _titles() and 'KeyUndoMe' not in _trash_titles())
app._hide_toast()
# A plain banner in its place hid the Undo the
# keyboard was on, and nothing moved the keyboard -- left on a word no
# longer on screen, where Tab started again from the window's top.
app.notebook.select(app.TAB_NOTES)
app.refresh_note_list()
_kt_settle()
tk.Misc.focus_set = _kt_record
try:
    app._show_toast('Note moved to Trash', action=lambda: None)
    _kt_settle(2)
    _kz_on = _kt_take(app.toast_action_lbl)
    del _kt_asked[:]
    app._show_toast('Exported to notes.txt')
    _kt_settle(2)
    check(f'a plain banner over the Undo the keyboard is on hides the Undo and '
          f'takes the keyboard to the note list ({_kz_on}, asked {_kt_asked})',
          _kz_on and not app.toast_action_lbl.winfo_ismapped()
          and _kt_asked[-1:] == [app.canvas])
    app._show_toast('Note moved to Trash', action=lambda: None)
    _kt_settle(2)
    _kz_on = _kt_take(app.toast_action_lbl)
    del _kt_asked[:]
    app._hide_toast()
    _kt_settle(2)
    check(f'...and the banner going from under the keyboard does the same '
          f'({_kz_on}, asked {_kt_asked})',
          _kz_on and _kt_asked[-1:] == [app.canvas])
finally:
    tk.Misc.focus_set = _kt_real_focus_set
app._hide_toast()
app.notes = []; app.save_notes(); app.trash = []; NO.save_trash(app.trash)
app.refresh_note_list()
_kt_settle()
# With the list put away by the sidebar's arrow, the list was still
# the landing -- a hidden window, for which Tk only notes a request -- so the
# keyboard stayed on the hidden Undo. Asked where it IS, not where it was sent.
app.toggle_sidebar()
_kt_settle()
_kz_land = {}
for _kz_how in ('a plain banner', 'Ctrl+Z', 'the banner going', 'Space'):
    app._show_toast('Note moved to Trash', action=lambda: None)
    _kt_settle(2)
    _kz_on = _kt_take(app.toast_action_lbl)
    if _kz_how == 'a plain banner':
        app._show_toast('Exported to notes.txt')
    elif _kz_how == 'Ctrl+Z':
        app.toast_action_lbl.event_generate('<Control-z>')
    elif _kz_how == 'Space':
        app.toast_action_lbl.event_generate('<space>')
    else:
        app._hide_toast()
    _kt_settle(4)
    try:
        _kz_held = app.nametowidget(str(app.tk.call('focus', '-lastfor', app)))
        _kz_land[_kz_how] = (_kz_on, _kz_held is app.sidebar_toggle
                             and bool(_kz_held.winfo_viewable()))
    except (KeyError, tk.TclError):
        _kz_land[_kz_how] = (_kz_on, False)
    app._hide_toast()
if app._sidebar_hidden:
    app.toggle_sidebar()
_kt_settle()
check(f'with the note list put away, the keyboard leaves a hidden Undo for the '
      f'list\'s arrow, by every road ({_kz_land})',
      len(_kz_land) == 4 and all(v == (True, True) for v in _kz_land.values()))


print()
print(f"=== QA3 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
