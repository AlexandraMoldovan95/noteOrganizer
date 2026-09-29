"""Fail when Romanian reaches anything a reader of this repository sees.

WHY THIS GATE EXISTS
--------------------
The work here is discussed in Romanian and written down in English, and
the line between the two is easy to cross without noticing. It was
crossed: the qa stories named their checks in Romanian, four screenshots
carried Romanian filenames, and every CI run printed those names into a
log anybody can open.

Nothing about that was wrong while it lived on one machine. It stops
being a private note the moment it is pushed.

This app's interface is English throughout, so in THIS repository there
is no legitimate Romanian at all -- which makes the rule simple to state
and simple to check. (The Android companion is different: its interface
speaks Romanian to its users, so its copy of this gate exempts the app's
own strings. Same idea, different boundary.)

    py tools/check_english.py
    py tools/check_english.py --list     # every hit, not just the first few

Exit code 0 when clean, 1 when something slipped through.

WHAT IT READS
-------------
Every text file git tracks, minus binaries and the exceptions below. It
asks git rather than walking the disk, so an untracked scratch file
cannot fail the build and a tracked one cannot hide from it.
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Words that are Romanian and are not also English. Short ones like "a",
# "la" or "un" are left out on purpose: they appear inside English prose
# and in code as identifiers, and a gate that cries wolf gets switched
# off. These are enough -- they carry ordinary Romanian sentences.
WORDS = [
    "acest", "aceasta", "acum", "adauga", "arata", "cand", "cauta",
    "daca", "deci", "dupa", "este", "fara", "fiindca", "fisier",
    "fisierul", "fisiere", "inainte", "inapoi", "notita", "notite",
    "pentru", "poate", "ramane", "sterge", "sters", "stearsa", "sunt",
    "toate", "trebuie", "verifica", "vreau",
    # Added 2026-09-15, after the gate read a seeded notebook full of
    # Romanian nouns -- "Reteta de paine", "lapte", "oua" -- and called
    # the repository clean. The list had only function words, and nouns
    # carry just as much language. Widening it turned up twenty-six more
    # lines of test data nobody had looked at since writing them.
    "reteta", "cumparat", "lapte", "paine", "faina", "framantat",
    "caiet", "caietul", "aliment", "fructe", "nume", "cant", "zile",
    # Added 2026-09-29, after the gate called the repository clean while
    # six check names in story_note_travels printed Romanian into every
    # CI log -- the exact thing the docstring above says this was written
    # to stop -- plus two messages in doc_screenshots and some eighty
    # lines of seeded test data. None of them used a word on the list.
    #
    # That is the lesson, and it is why this block is long: a hand-picked
    # sample answers "none of MY words are here", which is not the same
    # question as "is this English". The words below were not guessed --
    # they are every word the 2026-09-29 sweep actually found, plus the
    # ordinary connectives that carry a Romanian sentence around them.
    # A word goes in only if it is not also English: "face", "nota",
    # "plan", "corp" and "lista" were all tried and rejected here,
    # because a gate that cries wolf gets switched off.
    "aici", "acolo", "altfel", "apasa", "apoi", "asta", "atentie",
    "atunci", "butonul", "butoane", "cateva", "ceva", "comentariu",
    "culoare", "culori", "deschide", "deschis", "doar", "eroare",
    "fereastra", "foarte", "garda", "gasit", "gasita", "gasite",
    "greseala", "gresit", "inchide", "inchis", "inca", "insa", "intai",
    "lunga", "mereu", "nesalvat", "netrimis", "nicio", "niciun",
    "nimeni", "nimic", "niste", "numai", "oprit", "orice", "pastrat",
    "porneste", "prea", "ramas", "ramane", "randul", "ruleaza",
    "salut", "salvat", "salvata", "salveaza", "scris", "scrie",
    "sedinta", "simplu", "sterge", "titlul", "titluri", "vechi",
    "vorbe", "acelasi", "aiurea", "editata", "inexistenta", "notitei",
    "sablon", "scurta", "versiunea",
    # A third pass, same day: translating the list above turned up seven
    # more lines whose words were not on it either -- "coada", "facut
    # deja", "Ramasa", "necunoscut". Three rounds of widening on one day
    # is the honest measure of how far a wordlist gets you, and it is
    # why anything new written here is read before it is committed
    # rather than trusted to this gate.
    "coada", "facut", "deja", "necunoscut", "ramasa", "dinainte",
    "laterala", "panou", "bara", "continut", "acelasi", "baza",
    "scurt", "originala", "versiune",
]
ROMANIAN = re.compile(r"\b(%s)\b" % "|".join(WORDS), re.I)

# Words checked only against FILENAMES. They are too short, or too close
# to something a program legitimately says, to search for inside code --
# `cos` is the cosine the icon is drawn with -- but in a filename there
# is nothing else they could be.
FILENAME_ONLY = ["lista", "setari", "categorii", "cos", "cosul", "tema",
                 "deschisa", "poza", "poze", "ecran", "ecrane"]
IN_FILENAME = re.compile(r"\b(%s)\b" % "|".join(WORDS + FILENAME_ONLY), re.I)

# Romanian diacritics. Any of them, anywhere, in a repository whose app
# speaks English.
DIACRITICS = re.compile(r"[ăâîșțĂÂÎȘȚ]")

# Extensions worth reading. Everything else is either binary or not prose.
TEXT = (".py", ".md", ".txt", ".yml", ".yaml", ".json", ".spec", ".cfg",
        ".toml", ".ini", ".bat", ".sh", ".html", ".css", ".js")

# Exceptions, each with the reason it is one. An exception nobody can
# read is not a reviewed exception -- the same rule the note-shape gate
# keeps.
ALLOWED = {
    "tools/check_english.py":
        "this gate: the wordlist it searches for is necessarily Romanian",
}


def tracked():
    """Every path git tracks here -- or a refusal.

    Asking git is what makes an untracked scratch file harmless and a
    tracked one impossible to hide. It also means that OUTSIDE a git
    checkout this gate has nothing to read, and a gate with nothing to
    read must not print a pass: "0 files, all clean" is the shape of
    every check that has quietly stopped working.
    """
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    names = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    if out.returncode != 0 or not names:
        print("Cannot list the tracked files (is %s a git checkout?)." % ROOT)
        print("This gate reads what git tracks; with nothing to read it")
        print("refuses rather than reporting everything clean.")
        sys.exit(2)
    return names


def tracked_files():
    for name in tracked():
        if os.path.splitext(name)[1].lower() in TEXT:
            yield name


def hits_in(relative):
    path = os.path.join(ROOT, relative)
    try:
        text = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        word = ROMANIAN.search(line)
        mark = DIACRITICS.search(line)
        if word or mark:
            found.append((number, (word or mark).group(0), line.strip()))
    return found


def main():
    show_all = "--list" in sys.argv
    leaks = []
    named = []

    for relative in tracked_files():
        if relative in ALLOWED:
            continue
        for number, word, line in hits_in(relative):
            leaks.append((relative, number, word, line))

    # Filenames are read too: a picture called 04-setari-cos.png says it
    # in the file listing, before anybody opens anything.
    for name in tracked():
        stem = os.path.basename(name).rsplit(".", 1)[0].replace("-", " ")
        if name not in ALLOWED and IN_FILENAME.search(stem):
            named.append(name)

    if not leaks and not named:
        print("English throughout: %d tracked text file(s) read, plus every "
              "tracked filename." % sum(1 for _ in tracked_files()))
        return 0

    if named:
        print("Romanian in FILENAMES (%d):" % len(named))
        for name in named:
            print("    %s" % name)
        print()

    if leaks:
        print("Romanian in CONTENT (%d line(s) in %d file(s)):"
              % (len(leaks), len({l[0] for l in leaks})))
        shown = leaks if show_all else leaks[:12]
        for relative, number, word, line in shown:
            print("    %s:%d  [%s]  %s" % (relative, number, word, line[:70]))
        if len(shown) < len(leaks):
            print("    ... and %d more (--list for all)"
                  % (len(leaks) - len(shown)))
        print()

    print("This repository is read by people who do not speak Romanian, and")
    print("its app speaks English. Translate it, or add the file to ALLOWED")
    print("in this gate WITH the reason it belongs there.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
