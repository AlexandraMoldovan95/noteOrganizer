"""A note's identity: the `uid` that survives leaving the app.

`id` is a note's place in one file — two devices both hand a new note
`max + 1`, so both invent 87 and nothing downstream can tell the two
apart. `uid` is invented independently and cannot collide, which is what
lets an import say "this is the note you already have" instead of
guessing from the text — a guess that is wrong precisely when the note
was edited, which is the only time anyone re-sends one.

Pure logic: no GUI, no filesystem. Still runs from a scratch copy, never
the project root — see CLAUDE.md, "QA testing safety". Nothing here
writes, but the rule has no per-file exceptions for a reason.
"""
import sys

from noteorganizer.core.duplicates import _dup_key
from noteorganizer.core.model import (
    NOTE_DEFAULTS,
    apply_shared_update,
    find_by_uid,
    split_by_identity,
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
      normalize_note({"id": 1, "uid": "de-pe-telefon"})["uid"] == "de-pe-telefon")

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

_note = normalize_note({"id": 5, "title": "Cumparaturi", "body": "lapte"})
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
    "uid": "inventat", "title": "x",
    "attachments": [{"filename": "p.png", "stored_as": "../../escape"}],
}]))[0]
check('a code cannot smuggle in an attachment alongside a uid',
      "attachments" not in _forged)
check('...while the uid it did carry comes through',
      _forged.get("uid") == "inventat")

# ---- finding the note an incoming copy IS ----

_a = normalize_note({"id": 1, "title": "A"})
_b = normalize_note({"id": 2, "title": "B"})
_notes = [_a, _b]

check('find_by_uid finds the note with that identity',
      find_by_uid(_notes, _b["uid"]) is _b)

check('find_by_uid returns None for an identity nobody has',
      find_by_uid(_notes, "nimeni") is None)

for _empty, _what in [("", "an empty string"), ("   ", "whitespace"),
                      (None, "None"), (7, "a number")]:
    check('find_by_uid returns None for %s rather than matching anything'
          % _what, find_by_uid(_notes, _empty) is None)

check('find_by_uid ignores whitespace around the identity asked for',
      find_by_uid(_notes, "  %s  " % _a["uid"]) is _a)

check('find_by_uid survives a list holding something that is not a note',
      find_by_uid([_a, "nu e o notita", None], _a["uid"]) is _a)

# The guard above earns its keep only against a note that HAS an empty
# identity -- which normalize_note never produces, but a raw dict from a
# half-written file or another program can. Without such a note in the
# list, an empty search returns None anyway and the check proves nothing:
# a mutant that removed the guard survived this suite until this case
# was added.
_hollow = {"id": 3, "title": "fara identitate", "uid": ""}
for _empty, _what in [("", "an empty string"), ("   ", "whitespace")]:
    check('%s does not match a note whose identity is blank' % _what,
          find_by_uid([_a, _hollow], _empty) is None)

# The pairing that matters: identity says yes exactly where resemblance
# says no. An edited note is a different text and the same note.
_edited = dict(_a, title="A, corectat", body="text nou")
check('an EDITED copy still has the same identity',
      find_by_uid(_notes, _edited["uid"]) is _a)
check('...while its content no longer matches',
      _dup_key(normalize_note(_edited)) != _dup_key(_a))

# ---- updating a note from an incoming copy ----

_mine = normalize_note({
    "id": 9, "title": "Vechi", "body": "corp vechi", "category": "Work",
    "comments": "nota mea", "created": "2020-01-01 00:00:00",
    "attachments": [{"filename": "p.png", "stored_as": "a1.png"}],
})
_mine_uid, _mine_id = _mine["uid"], _mine["id"]
_incoming = {"uid": _mine_uid, "title": "Nou", "body": "corp nou",
             "category": "Personal"}
apply_shared_update(_mine, _incoming)

check('an update takes the incoming title',
      _mine["title"] == "Nou")
check('an update takes the incoming body',
      _mine["body"] == "corp nou")
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
      _mine["_prev"]["title"] == "Vechi")
check('...and the body it replaced',
      _mine["_prev"]["body"] == "corp vechi")
check('...and the comments, which Restore previous also puts back',
      _mine["_prev"]["comments"] == "nota mea")

check('the rescue copy survives the gate, so the button is not a lie',
      normalize_note(dict(_mine)).get("_prev", {}).get("body") == "corp vechi")

# An incoming copy is untrusted like any other: it goes through the gate
# before a single field is taken out of it.
_hostile = {"uid": _mine["uid"], "title": ["nu e text"], "body": None,
            "checklist": "nici asta", "category": "Categorie inexistenta"}
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
_have2 = normalize_note({"id": 2, "title": "Am si asta"})
_mine_all = [_have1, _have2]

_batch = [
    {"uid": _have2["uid"], "title": "Am si asta, editata"},
    {"uid": "necunoscut", "title": "Noua"},
    {"title": "Fara identitate deloc"},
]
_known, _fresh = split_by_identity(_mine_all, _batch)

check('split_by_identity pairs an incoming note with the one it IS',
      len(_known) == 1 and _known[0][0] is _have2)
check('...and hands back the incoming copy beside it',
      _known[0][1]["title"] == "Am si asta, editata")
check('split_by_identity treats an unknown identity as new',
      any(n.get("uid") == "necunoscut" for n in _fresh))
check('split_by_identity treats a note with NO identity as new',
      any(n.get("title") == "Fara identitate deloc" for n in _fresh))
check('split_by_identity accounts for every note in the batch',
      len(_known) + len(_fresh) == len(_batch))
check('split_by_identity skips an entry that is not a note at all',
      split_by_identity(_mine_all, ["nu e", None, 5]) == ([], []))
check('split_by_identity on an empty batch finds nothing',
      split_by_identity(_mine_all, []) == ([], []))
check('split_by_identity against an empty notebook calls everything new',
      len(split_by_identity([], _batch)[1]) == 3)

print()
print("FAILURES: %s" % (fails if fails else "none"))
sys.exit(1 if fails else 0)
