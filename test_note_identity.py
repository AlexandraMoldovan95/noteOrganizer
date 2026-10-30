"""A note's identity: the `uid` that survives leaving the app.

`id` is a note's place in one file — two devices both hand a new note
`max + 1`, so both invent 87 and nothing downstream can tell the two
apart. `uid` is invented independently and cannot collide, which is what
lets an import say "this is the note you already have" instead of
guessing from the text — a guess that is wrong precisely when the note
was edited, which is the only time anyone re-sends one.

No GUI. Mostly pure logic, except the last section, which goes through
the real load path to answer a question no amount of reasoning about the
code could settle: whether an identity handed out at startup ever reaches
the disk. That section writes — inside a temp directory of its own, which
it configures the app's paths at and restores afterwards. Run it from a
scratch copy, never the project root — see CLAUDE.md, "QA testing
safety".
"""
import os
import sys
# Settled as a guest of this computer before the app's code (qa/_qa_support,
# beside this file in a scratch copy, in qa/ where CI runs it).
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa"))
from _qa_support import as_a_guest  # noqa: E402
as_a_guest()

from noteorganizer.core.duplicates import _dup_key  # noqa: E402
from noteorganizer.core.model import (
    NOTE_DEFAULTS,
    apply_shared_update,
    copy_replaced_by_restore,
    find_by_uid,
    rescue_copy_due,
    rescue_copy_spent,
    split_by_identity,
    text_lost,
    words_lost,
    new_note_uid,
    normalize_note,
)
from noteorganizer.core.sharing import (
    SHAREABLE_FIELDS,
    decode_share_code,
    encode_share_code,
)

fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


# ---- minting ----

check('a note arriving without a uid is given one',
      bool(normalize_note({"id": 1, "title": "x"})["uid"]))

check('two notes minted back to back get different uids',
      normalize_note({"id": 1})["uid"] != normalize_note({"id": 2})["uid"])

check('a thousand mints produce a thousand distinct uids',
      len({new_note_uid() for _ in range(1000)}) == 1000)

check('uid is in the note shape, so nothing downstream meets a gap',
      "uid" in NOTE_DEFAULTS)

check('a uid is plain text, like everything else in the file',
      isinstance(normalize_note({"id": 1})["uid"], str))

# ---- keeping one that already exists ----
#
# This is the property the whole feature rests on: pass the same note
# through the gate twice -- as every load, save and import does -- and it
# must come out as the SAME note. A uid regenerated on the way through
# would be no identity at all.

_once = normalize_note({"id": 1, "title": "x"})
_twice = normalize_note(dict(_once))
check('a note keeps its uid when it passes through the gate again',
      _once["uid"] == _twice["uid"])

_third = normalize_note(normalize_note(normalize_note(dict(_once))))
check('...and through it any number of times',
      _third["uid"] == _once["uid"])

check('a uid minted elsewhere is trusted, not replaced',
      normalize_note({"id": 1, "uid": "from-the-phone"})["uid"] == "from-the-phone")

check('surrounding whitespace is trimmed off a uid',
      normalize_note({"id": 1, "uid": "  abc  "})["uid"] == "abc")

# ---- refusing a uid that is not one ----

for _bad, _what in [("", "an empty string"), ("   ", "only whitespace"),
                    (None, "None"), (17, "a number"), ([], "a list"),
                    ({}, "a dict"), (False, "False")]:
    _out = normalize_note({"id": 1, "uid": _bad})["uid"]
    check('a uid that is %s is replaced with a real one' % _what,
          isinstance(_out, str) and len(_out) > 8)

# ---- the id is untouched ----
#
# The whole point of adding a field beside `id` rather than changing it:
# the 115 places that read an id keep working, unexamined.

check('id is still an int after the change',
      isinstance(normalize_note({"id": 7})["id"], int))

check('id still coerces a stringy id, as it always did',
      normalize_note({"id": "7"})["id"] == 7)

check('id still falls back to 0 when it is nonsense',
      normalize_note({"id": ["nope"]})["id"] == 0)

check('a note with no uid still gets its id unchanged',
      normalize_note({"id": 42, "title": "x"})["id"] == 42)

# ---- travelling in a share code ----

_note = normalize_note({"id": 5, "title": "Shopping", "body": "milk"})
_back = decode_share_code(encode_share_code([_note]))[0]

check('uid is one of the fields a share code carries',
      "uid" in SHAREABLE_FIELDS)

check('a note keeps its uid through a share code',
      _back.get("uid") == _note["uid"])

check('a share code still carries no id',
      "id" not in _back)

check('a share code still carries no attachments',
      "attachments" not in _back)

check('the note that comes back out of a code still normalises cleanly',
      normalize_note(dict(_back))["uid"] == _note["uid"])

# ---- what a hand-made code may carry ----
#
# decode projects through the same field slice encode produces, so a
# forged code cannot smuggle in anything a real one would not have. uid
# joining that list must not widen the door.

_forged = decode_share_code(encode_share_code([{
    "uid": "made-up", "title": "x",
    "attachments": [{"filename": "p.png", "stored_as": "../../escape"}],
}]))[0]
check('a code cannot smuggle in an attachment alongside a uid',
      "attachments" not in _forged)
check('...while the uid it did carry comes through',
      _forged.get("uid") == "made-up")

# ---- finding the note an incoming copy IS ----

_a = normalize_note({"id": 1, "title": "A"})
_b = normalize_note({"id": 2, "title": "B"})
_notes = [_a, _b]

check('find_by_uid finds the note with that identity',
      find_by_uid(_notes, _b["uid"]) is _b)

check('find_by_uid returns None for an identity nobody has',
      find_by_uid(_notes, "nobody") is None)

for _empty, _what in [("", "an empty string"), ("   ", "whitespace"),
                      (None, "None"), (7, "a number")]:
    check('find_by_uid returns None for %s rather than matching anything'
          % _what, find_by_uid(_notes, _empty) is None)

check('find_by_uid ignores whitespace around the identity asked for',
      find_by_uid(_notes, "  %s  " % _a["uid"]) is _a)

check('find_by_uid survives a list holding something that is not a note',
      find_by_uid([_a, "not a note", None], _a["uid"]) is _a)

# The guard above earns its keep only against a note that HAS an empty
# identity -- which normalize_note never produces, but a raw dict from a
# half-written file or another program can. Without such a note in the
# list, an empty search returns None anyway and the check proves nothing:
# a mutant that removed the guard survived this suite until this case
# was added.
_hollow = {"id": 3, "title": "no identity", "uid": ""}
for _empty, _what in [("", "an empty string"), ("   ", "whitespace")]:
    check('%s does not match a note whose identity is blank' % _what,
          find_by_uid([_a, _hollow], _empty) is None)

# ---- an import's matching, at the size of a whole backup ----
# split_by_identity asked find_by_uid once per incoming note, each a walk
# through the notebook: a backup of thousands into a notebook of thousands
# froze the app for seconds. Counted, not timed: a busy machine makes any
# timing check lie.


class _Counted(list):
    walks = 0

    def __iter__(self):
        type(self).walks += 1
        return super().__iter__()


_book = _Counted(normalize_note({"id": k, "title": "n%d" % k}) for k in range(50))
_back = [dict(n) for n in _book] + [{"title": "new"}]
_Counted.walks = 0
_known, _fresh = split_by_identity(_book, _back)
check('an import walks the notebook once, not once per incoming note (%d walks for %d)'
      % (_Counted.walks, len(_back)),
      _Counted.walks == 1 and len(_known) == 50 and len(_fresh) == 1
      and all(mine is _book[k] for k, (mine, _theirs) in enumerate(_known)))
_twin = dict(_a)
_known, _fresh = split_by_identity(
    [_a, _twin, "not a note", _hollow],
    [{"uid": "  %s " % _a["uid"]}, {"uid": ""}, {"uid": "   "}, {"uid": 7}, "not a note"])
check('...and answers as find_by_uid does: the first of two notes sharing an identity, '
      'spaces ignored, and a blank or missing identity matching nothing',
      len(_known) == 1 and _known[0][0] is _a and len(_fresh) == 3)

# The pairing that matters: identity says yes exactly where resemblance
# says no. An edited note is a different text and the same note.
_edited = dict(_a, title="A, corrected", body="new text")
check('an EDITED copy still has the same identity',
      find_by_uid(_notes, _edited["uid"]) is _a)
check('...while its content no longer matches',
      _dup_key(normalize_note(_edited)) != _dup_key(_a))

# ---- updating a note from an incoming copy ----

_mine = normalize_note({
    "id": 9, "title": "Old", "body": "the old body", "category": "Work",
    "comments": "my own note", "created": "2020-01-01 00:00:00",
    "attachments": [{"filename": "p.png", "stored_as": "a1.png"}],
})
_mine_uid, _mine_id = _mine["uid"], _mine["id"]
_incoming = {"uid": _mine_uid, "title": "New", "body": "the new body",
             "category": "Personal"}
apply_shared_update(_mine, _incoming)

check('an update takes the incoming title',
      _mine["title"] == "New")
check('an update takes the incoming body',
      _mine["body"] == "the new body")
check('an update keeps the note IN PLACE: the id does not move',
      _mine["id"] == _mine_id)
check('an update keeps the identity',
      _mine["uid"] == _mine_uid)
check('an update is not a birth: created does not move',
      _mine["created"] == "2020-01-01 00:00:00")
check('an update refreshes updated',
      len(_mine["updated"]) == 19)
check('an update leaves the attachments alone — a code never carried them',
      _mine["attachments"] == [{"filename": "p.png", "stored_as": "a1.png"}])

check('an update leaves a rescue copy behind',
      isinstance(_mine.get("_prev"), dict))
check('...holding the title it replaced',
      _mine["_prev"]["title"] == "Old")
check('...and the body it replaced',
      _mine["_prev"]["body"] == "the old body")
check('...and the comments, which Restore previous also puts back',
      _mine["_prev"]["comments"] == "my own note")

check('the rescue copy survives the gate, so the button is not a lie',
      normalize_note(dict(_mine)).get("_prev", {}).get("body") == "the old body")

# An incoming copy is untrusted like any other: it goes through the gate
# before a single field is taken out of it.
_hostile = {"uid": _mine["uid"], "title": ["not text"], "body": None,
            "checklist": "not this either", "category": "No such category"}
apply_shared_update(_mine, _hostile)
check('an update coerces a wrong type instead of storing it',
      _mine["title"] == "" and _mine["body"] == "")
check('an update coerces a wrong-typed checklist to a list',
      _mine["checklist"] == [])
check('an update files an unknown category under General',
      _mine["category"] == "General")

# ---- sorting a batch: what we have, and what we don't ----
#
# Both bulk routes -- a code carrying several notes, and a restored
# backup -- ask this one function. Two hand-rolled copies of the same
# judgement is how this project's search rules drifted apart once.

_have1 = normalize_note({"id": 1, "title": "Am"})
_have2 = normalize_note({"id": 2, "title": "I have this one too"})
_mine_all = [_have1, _have2]

_batch = [
    {"uid": _have2["uid"], "title": "I have this one too, edited"},
    {"uid": "unknown-to-us", "title": "Brand new"},
    {"title": "No identity at all"},
]
_known, _fresh = split_by_identity(_mine_all, _batch)

check('split_by_identity pairs an incoming note with the one it IS',
      len(_known) == 1 and _known[0][0] is _have2)
check('...and hands back the incoming copy beside it',
      _known[0][1]["title"] == "I have this one too, edited")
check('split_by_identity treats an unknown identity as new',
      any(n.get("uid") == "unknown-to-us" for n in _fresh))
check('split_by_identity treats a note with NO identity as new',
      any(n.get("title") == "No identity at all" for n in _fresh))
check('split_by_identity accounts for every note in the batch',
      len(_known) + len(_fresh) == len(_batch))
check('split_by_identity skips an entry that is not a note at all',
      split_by_identity(_mine_all, ["not a note", None, 5]) == ([], []))
check('split_by_identity on an empty batch finds nothing',
      split_by_identity(_mine_all, []) == ([], []))
check('split_by_identity against an empty notebook calls everything new',
      len(split_by_identity([], _batch)[1]) == 3)

# ---- the rescue copy, spent and swapped (2026-10-22, both apps) ----
#
# Undo after a big deletion brought the words back and the button stayed;
# pressed later, it put the old version over everything written since,
# with no way back. A save that holds what the copy kept spends it, and a
# restore keeps what it replaces -- unless that holds nothing new.
_long = "a long text that a slip of the hand deleted whole"
_kept = {"title": "t", "body": _long, "formatting": [], "paragraphs": [], "comments": ""}
check('a note holding again what its copy kept: the copy is spent',
      rescue_copy_spent({"title": "t", "body": _long, "_prev": dict(_kept)}))
check('...but not while the words differ',
      not rescue_copy_spent({"title": "t", "body": "", "_prev": dict(_kept)}))
check("...nor while an update's extra field differs",
      not rescue_copy_spent({"title": "t", "body": _long, "pinned": True,
                             "_prev": dict(_kept, pinned=False)}))
check('...and a note with no copy has none to spend',
      not rescue_copy_spent({"title": "t", "body": _long}))
_swap = copy_replaced_by_restore({"title": "t", "body": "written since"}, _kept)
check('a restore keeps the text it replaces, to be the copy in its turn',
      isinstance(_swap, dict) and _swap.get("body") == "written since" and _swap.get("title") == "t")
check('...the fields an update brings back with it',
      copy_replaced_by_restore({"title": "New", "body": "new", "category": "Home"},
                               dict(_kept, category="Work")).get("category") == "Home")
check('...but nothing over an emptied note, or words the restored text holds',
      copy_replaced_by_restore({"title": "t", "body": ""}, _kept) is None
      and copy_replaced_by_restore({"title": "t", "body": "a long text"}, _kept) is None)

# ---- when a save keeps a rescue copy: by what is gone (2026-10-24) ----
#
# Counted by how much SHORTER the text got, a short note replaced by a new
# line before the autosave (the owner's test case 692) and a paragraph
# replaced by one as long kept no copy, and their words were gone.
_short = "Buy milk\nCall mom\nPay the rent"
_para = "x" * 200 + "\n" + "an old paragraph of three hundred characters " * 6 + "\n" + "y" * 100
check('text_lost counts what neither end keeps',
      text_lost("abcdef", "abXYef") == 2 and text_lost("abc", "abc") == 0
      and text_lost("abc", "") == 3 and text_lost("", "new") == 0)
check('words_lost counts the words gone, each with its space, as often as they '
      'were there',
      words_lost("milk eggs milk", "eggs milk") == 5
      and words_lost("one two", "two  one") == 0
      and words_lost("a b", "a B") == 2 and words_lost("", "new") == 0)
check('a short note replaced by a new line keeps a copy (test case 692)',
      rescue_copy_due("", _short, "", "A new line"))
check('a paragraph replaced by another as long keeps a copy',
      rescue_copy_due("t", _para, "t", _para.replace("an old paragraph", "a new paragraph!")
                      .replace("of three hundred characters", "freshly typed in place of it.")))
check('an emptied note keeps a copy, however short',
      rescue_copy_due("", "milk", "", ""))
check('a big deletion keeps one, as it always did',
      rescue_copy_due("t", _long * 3, "t", _long))
check('a word changed keeps none',
      not rescue_copy_due("", _short, "", _short.replace("mom", "dad")))
check('...nor words added, at the end or in the middle',
      not rescue_copy_due("", _short, "", _short + "\nWater the plants")
      and not rescue_copy_due("", _short, "", _short.replace("Call", "Please call")))
check('...nor a tiny note retyped, or a title renamed',
      not rescue_copy_due("", "Milk", "", "Eggs")
      and not rescue_copy_due("Shopping", _short, "Groceries", _short))
check('...nor a first save of a new note',
      not rescue_copy_due("", "", "Title", "text"))

# ---- the identity has to survive the app closing ----
#
# Minting happens on every read, in memory. A session that only READS
# never saves, so unless the first read that mints also writes them down,
# the next launch invents a different set -- and a code made yesterday
# matches nothing today, which is the entire point of the field. Measured
# through the real load path rather than reasoned about: two loads of the
# same notebook, and the file itself.
import json
import os
import shutil
import tempfile

from noteorganizer.core import paths as _paths
from noteorganizer.core import storage as _storage


def _seed(directory, notes, indent=2):
    with open(os.path.join(directory, "notes_data.json"), "w",
              encoding="utf-8") as handle:
        json.dump(notes, handle, indent=indent)
    with open(os.path.join(directory, "settings.json"), "w",
              encoding="utf-8") as handle:
        # As it is on any notebook older than its first launch; otherwise
        # the one-time cleanup rewrites the file and hides the question.
        json.dump({"cleanup_done": True}, handle)


def _bytes_of(directory):
    with open(os.path.join(directory, "notes_data.json"),
              encoding="utf-8") as handle:
        return handle.read()


_prev_app_dir = _paths.APP_DIR
_work = tempfile.mkdtemp(prefix="identity-load-")
try:
    _paths.configure(_work)

    _seed(_work, [{"id": 1, "title": "First"}, {"id": 2, "title": "Second"}])
    _first, _ = _storage.load_notes(False)
    _second, _ = _storage.load_notes(False)

    check('a notebook read twice keeps the identities it was given',
          [n["uid"] for n in _first] == [n["uid"] for n in _second])
    _on_disk = json.loads(_bytes_of(_work))
    check('the identities are written down, not only held in memory',
          all(n.get("uid") for n in _on_disk))
    check('...and they are the ones the app is working with',
          [n["uid"] for n in _on_disk] == [n["uid"] for n in _first])
    check('nothing else about the notes is disturbed by that write',
          [n["title"] for n in _on_disk] == ["First", "Second"])

    # A notebook that needs nothing must not be rewritten. Seeded with an
    # indent the app never writes, so an untouched file is recognisable
    # without leaning on a timestamp.
    _settled = [{"id": 1, "title": "First", "uid": "aaa"},
                {"id": 2, "title": "Second", "uid": "bbb"}]
    _seed(_work, _settled, indent=4)
    _before = _bytes_of(_work)
    _storage.load_notes(False)
    check('a notebook that already has its identities is left alone',
          _bytes_of(_work) == _before)

    # The guard that matters most: a file this launch could not read is
    # never written over, however much it looks like it needs identities.
    # Its bytes are what the startup notice promises are still on disk.
    with open(os.path.join(_work, "notes_data.json"), "w",
              encoding="utf-8") as _handle:
        _handle.write("{ not json")
    _corrupt_before = _bytes_of(_work)
    _notes, _report = _storage.load_notes(False)
    check('an unreadable notebook is reported, not repaired',
          _report["notes_file_corrupt"])
    check('...and its bytes are left exactly where they were',
          _bytes_of(_work) == _corrupt_before)
    # ---- through the trash and back ----
    #
    # A restore already hands out a fresh id, because the trashed note's
    # own number may have been reused while it was gone. The identity has
    # the same problem by a different route: a copy of the note can arrive
    # from a share code while the original sits in the trash.
    _seed(_work, [{"id": 1, "title": "Left behind", "uid": "aaa"}])
    _live, _ = _storage.load_notes(False)
    _deleted = {"id": 9, "title": "Deleted", "uid": "bbb",
                "deleted_at": "2026-01-01 00:00:00"}

    _back, _ = _storage.restore_from_trash(list(_live), [_deleted], _deleted)
    check('a note that comes back from the trash is still the same note',
          _back[-1]["uid"] == "bbb")
    check('...and it does not bring "deleted_at" back with it',
          "deleted_at" not in _back[-1])

    _twin = {"id": 9, "title": "Deleted", "uid": "aaa",
             "deleted_at": "2026-01-01 00:00:00"}
    _back2, _ = _storage.restore_from_trash(list(_live), [_twin], _twin)
    check('a restore whose identity is already in use is given a new one',
          _back2[-1]["uid"] not in ("", "aaa"))
    check('...and the note already here keeps its own',
          _back2[0]["uid"] == "aaa")
    check('...so the notebook never holds two notes with one identity',
          len({n["uid"] for n in _back2}) == len(_back2))
finally:
    # None when nothing configured paths before this file did — which is
    # the normal case here, since this suite imports core directly rather
    # than starting the app. configure() cannot take it back.
    if _prev_app_dir is not None:
        _paths.configure(_prev_app_dir)
    shutil.rmtree(_work, ignore_errors=True)

print()
print("FAILURES: %s" % (fails if fails else "none"))
sys.exit(1 if fails else 0)
