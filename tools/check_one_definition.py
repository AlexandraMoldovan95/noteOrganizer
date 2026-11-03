"""Fail when a shared judgement about a note is written out twice.

WHY THIS GATE EXISTS
--------------------
Every omission an adversarial review has caught in this project came from
the same shape: a question the app asks in several places, answered by a
hand-rolled field list at each one. Fix the site the bug was reported on
and the siblings keep the old answer, silently, until a user loses data.

Three real ones, all found by review AFTER the "fix" had shipped:

* "is the editor empty?" lived in SIX places with six field lists. The
  first fix taught one of them that an emptied saved note is a real edit;
  the autosave and flush gates ran in front of it and still threw the
  emptying away, so the reported scenario was unchanged.
* "are these the same note?" lived in THREE. The duplicate scan learned
  about checklists; the stale-copy purge did not — and it authorises an
  irreversible delete of a leftover notebook folder on every launch.
* "has the body changed?" compared ``.strip()``-ed bodies while the save
  had just learned to store the body exactly as typed, so whitespace
  edits were written and then reported as no-change.

A grep would have caught all three in seconds. This gate is that grep,
run automatically, so the class cannot come back quietly.

HOW IT DECIDES
--------------
Each rule names a QUESTION, the function that owns the single answer, and
a pattern that recognises someone answering it by hand. A match outside
the owning function fails the gate. Where a second answer is genuinely
different (the explicit Save counts the date; a pristine-editor test
counts it too), the function is listed as a deliberate exception WITH the
reason — so the exceptions are readable, finite, and reviewed, instead of
being whatever happened to be written.

This gate is deliberately narrow. It does not try to find every possible
duplicate judgement; it holds the questions that have cost this project
something, each RULE below, and gains one the next time another does:

1-2. Does the editor hold anything worth keeping? -- asked of an editor
   state, and again of bare local variables (the first of the three above).
3. Are these two notes the same note?
4. Has the body changed?
5. Does this widget have its place in the layout? -- answered at fourteen
   show/hide sites with winfo_ismapped(), which says no for a widget whose
   page is merely hidden (0.82.233).
6. Could this file or code be read as JSON? -- fourteen readers caught one
   of the three ways a text turns out unreadable (0.83.338); its owner is
   a constant, paths.JSON_UNREADABLE.
7. Is this a figure from 0 to 9?
8. What has the person typed in the date field?

An allowance that matches nothing fails the gate too: an exception nobody
can see is not a reviewed exception, it is a comment.
"""

import ast
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    os.path.join(ROOT, "note_organizer.py"),
]
for sub in ("core", "ui"):
    folder = os.path.join(ROOT, "noteorganizer", sub)
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.endswith(".py"):
                FILES.append(os.path.join(folder, name))


class Rule:
    def __init__(self, question, owner, pattern, allowed, window=6):
        self.question = question
        self.owner = owner
        self.pattern = pattern
        self.allowed = dict(allowed)
        self.window = window


RULES = [
    Rule(
        question="does the editor hold anything worth keeping?",
        owner="_editor_state_has_content",
        # TWO or more note content fields read off an editor-state dict
        # and chained with or/and. Two, not three -- and the reason is the
        # whole point of this gate. Its first version demanded three
        # names, and the live share-as-code guard enumerated exactly two,
        # so the gate reported CLEAN over an instance of the very class it
        # exists to pin. A net tuned to what it already found is blind to
        # precisely the UNDER-inclusive guards that lose data, which is
        # worse than no net, because the next reader trusts it.
        pattern=re.compile(
            r"(?s)(?=.*[\"']title[\"'])"
            r"(?=.*[\"'](?:body|comments|checklist|attachments)[\"'])"
            r"(?=.*\bst\b)(?=.*\bor\b)"),
        allowed={
            "_editor_state_has_content": "the single answer",
            "editor_state_matches_saved":
                "the pristine-editor test additionally counts the date, so "
                "a calendar-prefilled editor still reads as changed",
            "save_current_as_template":
                "narrower on purpose: a template carries title, body, "
                "comments and checklist and NOTHING else, so an "
                "attachment or a repeat rule alone really would make an "
                "empty template",
        },
    ),
    Rule(
        question="does the editor hold anything worth keeping? "
                 "(bare-locals spelling)",
        owner="_editor_state_has_content",
        # The same question written with local variables instead of an
        # editor-state dict. The gate's first rule requires the
        # st["field"] spelling and so was blind to this one entirely --
        # which meant the save's own guard, a deliberate second
        # answer, had an allowlist entry that had never matched
        # anything. An exception nobody can see is not a reviewed
        # exception; it is a comment.
        pattern=re.compile(r"(?s)not\s+title\b.{0,200}?\bnot\s+body\b"),
        allowed={
            "_editor_fields_to_save":
                "explicit Save additionally counts the date and the repeat "
                "rule: pressing Save is what makes a bare dated reminder "
                "deliberate, and the automatic routes agree with "
                "_editor_state_has_content, which leaves both out",
        },
        window=8,
    ),
    Rule(
        question="are these two notes the same note?",
        owner="content_signature",
        # A tuple of note identity fields built by hand.
        pattern=re.compile(
            r"(?s)(?=.*[\"']title[\"'])(?=.*[\"']body[\"'])"
            r"(?=.*[\"']comments[\"'])(?=.*[\"']category[\"'])"),
        allowed={
            "content_signature": "the single answer",
            "_dup_key":
                "the USER-facing duplicate key is deliberately fuzzier: "
                "case/whitespace-insensitive, ' (copy)' ignored, and "
                "attachments excluded because cleanup merges them",
            "_text": "content_signature's own nested coercion helper",
            # Constructors, not judgements: these BUILD a note or a
            # template dict out of editor state. Naming the fields is
            # what they are for.
            "_write_fields_to_note": "builds the note being saved",
            "_keep_text_aside":
                "builds the note a big delete's words become beside an "
                "Update's copy (wave 2); it compares nothing",
            "_day_as_shown":
                "builds the copy of one day a file is made of (wave 2); its "
                "one comparison asks whether the day's text is the series' own, "
                "as _settle_off_schedule_day's does",
            "do_save": "builds the template being saved",
            "collect": "builds the template the settings editor is editing",
            "notes_set_aside":
                "builds the notes a series' copy's days set aside become "
                "(round 15 of the final audit); it compares nothing",
            "editor_state_matches_saved":
                "the OCCURRENCE branch compares only OVERRIDABLE_FIELDS, "
                "because an override carries exactly those -- comparing "
                "series-owned fields there made a just-saved occurrence "
                "read as dirty forever (field report, 0.71.111)",
        },
    ),
    Rule(
        question="has the body changed?",
        owner="editor_state_matches_saved",
        # A stripped body on either side of a comparison: the exact shape
        # that discarded whitespace-only edits.
        pattern=re.compile(
            r"[\"']body[\"']\]\s*\.strip\(\)\s*[!=]=|"
            r"[!=]=\s*\w+\[[\"']body[\"']\]\s*\.strip\(\)"),
        allowed={},
        window=1,
    ),
    Rule(
        question="does this widget have its place in the layout?",
        owner="_is_placed",
        # winfo_ismapped() called anywhere. It answers whether the widget
        # is on the SCREEN -- no for a widget until Tk first draws it after
        # packing, and no for as long as the page holding it is hidden --
        # so a show/hide decision reading it skipped a widget that was
        # only asleep (Restore previous stayed on a note with nothing to
        # restore, opened from the Calendar). A leading dot, so the
        # comments that name it do not count.
        pattern=re.compile(r"\.winfo_ismapped\(\)"),
        allowed={
            "_show_tooltip":
                "asks the screen question on purpose: a tooltip is only "
                "worth showing for a widget that is on the screen",
            "_clear_settings_field_focus":
                "runs on a click, and a click only lands on a page Tk has "
                "already drawn, so the screen answer is settled",
            "_is_calendar_visible":
                "asked by a key press and by the grid's own resize, both of "
                "which arrive after the page is drawn; a caller that runs "
                "before Tk goes idle asks _calendar_is_showing instead",
            "_grid_keyboard_back":
                "asks whether a right-click menu is still posted: a menu has "
                "no place in any layout, only on the screen or not",
        },
        window=1,
    ),
    Rule(
        question="could this file or code be read as JSON?",
        owner="JSON_UNREADABLE",
        # An except clause naming JSONDecodeError itself. That is one of
        # three ways a JSON text turns out unreadable -- bytes that are not
        # UTF-8 raise UnicodeDecodeError, nesting deeper than the parser
        # follows raises RecursionError -- and every reader that named it
        # alone let the other two escape: the app would not start while its
        # notes, settings, Trash or templates file held one (0.83.338).
        # noteorganizer.core.paths.JSON_UNREADABLE names all three.
        pattern=re.compile(r"\bexcept\b[^:\n]*\bJSONDecodeError\b"),
        allowed={},
        window=1,
    ),
    Rule(
        question="is this a figure from 0 to 9?",
        owner='isdecimal(), what int() reads, or a test against "0123456789"',
        # str.isdigit() is True for superscript and circled figures too --
        # "²", "①", "₂" -- which int() refuses and the patterns, written
        # [0-9], never match. "17²" in the date field passed read_date's
        # test as a figure, failed its match, and every autosave of the
        # note raised. Three readers had been fixed one at a time before
        # (a day of the month, a year, the calculator); this stops the
        # next. Code only, before any "#": the comments that tell this
        # story name it.
        pattern=re.compile(r"(?m)^[^#\n]*\.isdigit\(\)"),
        allowed={
            "_day": "asked only after head.isascii(): no figure but 0-9 reaches it",
        },
        window=1,
    ),
    Rule(
        question="what has the person typed in the date field?",
        owner="_typed_date",
        # The field read by hand. Five readers each compared it with its
        # empty form ("YYYY-MM-DD") themselves, and the day the form became
        # DD.MM.YYYY each was one more place to forget -- a reader that
        # missed it would take the form for a date someone typed.
        pattern=re.compile(r"self\.date_entry\.get\(\)"),
        allowed={"_typed_date": "the single answer"},
        window=1,
    ),
]


def enclosing_functions(tree):
    """line number -> innermost enclosing function name."""
    owner = {}

    def walk(node, name):
        for child in ast.iter_child_nodes(node):
            child_name = name
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                child_name = child.name
            lineno = getattr(child, "lineno", None)
            end = getattr(child, "end_lineno", lineno)
            if lineno:
                # Plain assignment, not setdefault: the walk descends
                # outer-to-inner, so the innermost function wins -- which
                # is the one that actually owns the line.
                for ln in range(lineno, (end or lineno) + 1):
                    owner[ln] = child_name
            walk(child, child_name)

    walk(tree, "<module>")
    return owner


def main():
    problems = []
    used = set()            # (rule's question, allowed name) that matched somewhere
    for path in FILES:
        src = io.open(path, encoding="utf-8").read()
        lines = src.split("\n")
        try:
            owner = enclosing_functions(ast.parse(src))
        except SyntaxError as exc:
            print("cannot parse %s: %s" % (path, exc))
            return 1
        rel = os.path.relpath(path, ROOT)
        for rule in RULES:
            seen_funcs = set()
            for i in range(len(lines)):
                window = "\n".join(lines[i:i + rule.window])
                if "#" in window and "one-definition-ok" in window:
                    continue
                if not rule.pattern.search(window):
                    continue
                func = owner.get(i + 1, "<module>")
                # A hand-rolled JUDGEMENT always lives inside a function.
                # Module- and class-level matches are field DECLARATIONS
                # (NOTE_DEFAULTS, OVERRIDABLE_FIELDS, SHAREABLE_FIELDS) --
                # naming the fields is their whole job, and they are the
                # single definition of what a note HAS, not of what it
                # MEANS.
                if func == "<module>":
                    continue
                if func in rule.allowed:
                    used.add((rule.question, func))
                    continue
                if func in seen_funcs:
                    continue
                seen_funcs.add(func)
                problems.append((rel, i + 1, func, rule))

    # An allowance that matches nothing is a comment, not a reviewed
    # exception: it once hid that its function had changed shape.
    unused = [(rule, name) for rule in RULES for name in rule.allowed
              if (rule.question, name) not in used]
    if unused:
        print("one-definition gate: %d allowance(s) that match nothing\n" % len(unused))
        for rule, name in unused:
            print("  %s -- in the rule %r" % (name, rule.question))
        print("\n      Remove each, or aim it at the function as it is now.")
        return 1

    if not problems:
        print("one-definition gate: clean (%d file(s), %d rule(s))"
              % (len(FILES), len(RULES)))
        return 0

    print("one-definition gate: %d hand-rolled answer(s)\n" % len(problems))
    for rel, lineno, func, rule in problems:
        print("  %s:%d  in %s()" % (rel, lineno, func))
        print("      question : %s" % rule.question)
        # A function's name gets its "()"; a constant, or an owner that is
        # a way of asking rather than one function, is printed as it is.
        plain = rule.owner.isupper() or " " in rule.owner
        print("      owned by : %s%s" % (rule.owner, "" if plain else "()"))
        print("      Use the owner, or -- if this answer is genuinely")
        print("      different -- add it to that rule's `allowed` in")
        print("      tools/check_one_definition.py WITH the reason, so the")
        print("      exception is reviewed rather than assumed.")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
