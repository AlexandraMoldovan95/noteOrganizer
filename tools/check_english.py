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
is no legitimate Romanian to show -- which makes the rule simple to state
and simple to check. (The Android companion keeps a copy of this gate; its
interface has been English too since 2026-10-15, so it holds the app's own
strings to the same rule.)

One exception, agreed on purpose: the Romanian month names the date field
understands ("17 octombrie 2026"), in noteorganizer/core/recurrence.py and
in the tests that type them. They are read, never shown; none carries a
diacritic, none is on the word list below, and none has an ending the
shape rule knows. Do not "fix" them away -- and do not let anything else
in on their account.

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

# Words that are Romanian and not also English. Short ones like "a", "la"
# or "un" are left out: they appear in English prose and as identifiers, and
# a gate that cries wolf gets switched off.
WORDS = [
    "acest", "aceasta", "acum", "adauga", "arata", "cand", "cauta",
    "daca", "deci", "dupa", "este", "fara", "fiindca", "fisier",
    "fisierul", "fisiere", "inainte", "inapoi", "notita", "notite",
    "pentru", "poate", "ramane", "sterge", "sters", "stearsa", "sunt",
    "toate", "trebuie", "verifica", "vreau",
    # Nouns as well (2026-09-15): a seeded notebook of Romanian recipes
    # passed a list of function words.
    "reteta", "cumparat", "lapte", "paine", "faina", "framantat",
    "caiet", "caietul", "aliment", "fructe", "nume", "cant", "zile",
    # Every word the 2026-09-29 sweep found, plus the connectives around
    # them; a word that is also English ("face", "nota", "plan") stays out.
    # ISSUES_LOG: "The same net, woven again".
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
    # A third pass the same day: seven more lines the list had missed.
    "coada", "facut", "deja", "necunoscut", "ramasa", "dinainte",
    "laterala", "panou", "bara", "continut", "acelasi", "baza",
    "scurt", "originala", "versiune",
    # The fourth pass (2026-10-03) read the whole repository, not a sample.
    # Still invisible: two-letter words and words English shares ("da",
    # "nu", "doi", "sub") -- for those, reading before committing.
    "acasa", "acte", "adaugata", "albastru", "alta", "antrenament",
    "ascuns", "bifa", "cablu", "capat", "categorie", "celula", "citit",
    "coloana", "colorat", "colorata", "corectat", "cumparaturi",
    "cuvant", "cuvinte", "decat", "descriere", "discutat", "disparuta",
    "doilea", "dubla", "evidentiat", "franta", "geamana", "golit",
    "identica", "identitate", "incaltari", "inceput", "inventat", "jos",
    "lateste", "legenda", "mele", "memorat", "mers", "modificare",
    "multa", "munca", "nerandat", "nivel", "nou", "noua", "ordine", "oua",
    "pana", "patru", "plecata", "pozitie", "pret", "prin", "proaspat",
    "produs", "proiect", "proiecte", "prosop", "repetat", "repetitiva",
    "retete", "retetele", "rupt", "schimbat", "scoala", "serie",
    "simulat", "spatii", "straina", "sursa", "tabel", "tarziu",
    "telefon", "temporara", "titlu", "trei", "treilea", "umplut", "unic",
    "unu", "valoare", "varianta", "veche", "vecina", "vezi", "vizibil",
    "vopsit", "ziua",
]
ROMANIAN = re.compile(r"\b(%s)\b" % "|".join(WORDS), re.I)

# Endings Romanian gives its words and English almost never does (the
# article in "planul", "-ilor", "-eaza", "-iune", the teens), so the rule
# knows words nobody listed. A capital then lower case keeps it off base64.
SHAPES = re.compile(r"\b[A-Za-z][a-z]{2,}(?:(?<![fao])ul|ului|ilor|elor|"
                    r"eaza|easca|iune|iunea|iuni|sprezece)\b")
ENGLISH_SHAPED = {"annul", "consul", "mogul", "kabul", "istanbul", "bachelor"}

# Glue hides a word from \b ("NotaTabelQ", "vechi1", the "trei" in
# "unu\ntrei"), so a copy of each line is pried apart at those seams first;
# a name that only LOOKS glued (DejaVu, not "deja") is kept whole.
SEAMS = re.compile(r"\\[ntr](?=[A-Za-z])|(?<=[a-z])(?=[A-Z])"
                   r"|(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])")
WHOLE_NAMES = ("DejaVu",)


def pried(line):
    for name in WHOLE_NAMES:
        line = line.replace(name, name.lower())
    return SEAMS.sub(" ", line)


def romanian_in(line):
    """The first Romanian word in a line, by list or by shape, or None."""
    line = pried(line)
    word = ROMANIAN.search(line)
    if word:
        return word.group(0)
    for shape in SHAPES.finditer(line):
        if shape.group(0).lower() not in ENGLISH_SHAPED:
            return shape.group(0)
    return None


# Lines the rule must find, and lines it must leave alone, read before the
# repository: a change to the list or the shapes that blinds the rule fails
# here, where a clean repository would have passed it in silence.
# One of each ending no listed word carries, so each shape is read alone;
# and each English exception, so none is kept that nothing needs.
MUST_FIND = ["titlu nou", "NotaTabelVeche", "done\\ntrei",
             "planul", "creionului", "copiilor", "notelor",
             "deseneaza", "citeasca", "sectiune", "optiunea", "optiuni", "doisprezece"]
MUST_PASS = ["annul the consul's order", "a flight to Kabul", "set the font to DejaVu Sans",
             "a mogul in Istanbul", "a bachelor party"]


def examples_misread():
    """(what went wrong, line) for each example the rule reads wrongly."""
    return ([("missed", line) for line in MUST_FIND if not romanian_in(line)]
            + [("flagged", line) for line in MUST_PASS if romanian_in(line)])


# Checked only against FILENAMES: too short or too code-like to search for
# in code (`cos` is the icon's cosine), but in a filename nothing else.
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
                         text=True, encoding="utf-8", errors="replace", timeout=120)
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
        word = romanian_in(line)
        mark = DIACRITICS.search(line)
        if word or mark:
            found.append((number, word or mark.group(0), line.strip()))
    return found


def main():
    import guest  # the memory ceiling, before git starts (tools/guest.py)
    guest.settle(heavy=False)
    misread = examples_misread()
    for what, line in misread:
        print("The rule %s its own example: %r" % (what, line))
    if misread:
        return 1
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
        if name not in ALLOWED and (IN_FILENAME.search(pried(stem))
                                    or romanian_in(stem)):
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
