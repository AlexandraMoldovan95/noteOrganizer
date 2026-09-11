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
duplicate judgement; it pins the three that have actually cost this
project data, and gains a rule the next time one costs it another.
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
        # which meant save_current_note's guard, a deliberate second
        # answer, had an allowlist entry that had never matched
        # anything. An exception nobody can see is not a reviewed
        # exception; it is a comment.
        pattern=re.compile(r"(?s)not\s+title\b.{0,200}?\bnot\s+body\b"),
        allowed={
            "save_current_note":
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
            "save_current_note": "builds the note being saved",
            "do_save": "builds the template being saved",
            "collect": "builds the template the settings editor is editing",
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
                if func in rule.allowed or func in seen_funcs:
                    continue
                seen_funcs.add(func)
                problems.append((rel, i + 1, func, rule))

    if not problems:
        print("one-definition gate: clean (%d file(s), %d rule(s))"
              % (len(FILES), len(RULES)))
        return 0

    print("one-definition gate: %d hand-rolled answer(s)\n" % len(problems))
    for rel, lineno, func, rule in problems:
        print("  %s:%d  in %s()" % (rel, lineno, func))
        print("      question : %s" % rule.question)
        print("      owned by : %s()" % rule.owner)
        print("      Call the owner, or -- if this answer is genuinely")
        print("      different -- add it to that rule's `allowed` in")
        print("      tools/check_one_definition.py WITH the reason, so the")
        print("      exception is reviewed rather than assumed.")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
