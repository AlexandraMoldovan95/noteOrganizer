"""Every theme's text measured against WCAG, and kept from getting worse.

WHAT IT CHECKS
--------------
For each of the eight themes in noteorganizer/core/themes.py, the
contrast ratio WCAG 2.1 defines -- from relative luminance, not by eye --
between each text colour and each surface the app draws it on. All of the
app's text is 8 to 11 pt, which WCAG counts as normal-sized (large means
18 pt, or 14 pt bold), so every pair of words owes 4.5:1, the AA level; a
drawn glyph owes 3:1, WCAG's non-text contrast. That includes the words
on a filled button, which the app picks by this same measure
(themes.letters_on), and the surfaces it mixes rather than reads off a
palette (DERIVED).

Pairs still below AA are listed in BELOW_AA with the reason. Anything else
below it fails; so does a listed pair that has started to pass, so the
list can only shrink.

One more thing the theme switch depends on: it remaps colours by value,
so a colour value must mean one role across all the themes. And the table
in docs/ARCHITECTURE.md must be the one this prints, so it cannot go stale.

Last, every theme's accent has its window icon: the app looks the icon
up by the accent's hex (assets/icon_<hex>.ico) and quietly falls back to
the default when there is none, so a changed accent lost its icon with
nothing to say so. `py tools/make_icon.py --all` draws them. And no icon is
left over for an accent no theme wears: the build bundles every one.

    py tools/check_contrast.py              # the verdict
    py tools/check_contrast.py --markdown   # the table in ARCHITECTURE.md
"""

import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# themes.py is pure data; loaded on its own so the gate needs no package.
_spec = importlib.util.spec_from_file_location(
    "themes", os.path.join(ROOT, "noteorganizer", "core", "themes.py"))
themes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(themes)

AA_NORMAL = 4.5
# What a drawn glyph owes its ground: WCAG 2.1's non-text contrast.
AA_NON_TEXT = 3.0

# (text colour, surface, where the app draws it[, what it owes]). Theme
# keys; the on_* names are the words on a fill, which the app works out
# from the fill (themes.letters_on), and the DERIVED names below are
# mixed surfaces. A pair owes AA_NORMAL unless it names AA_NON_TEXT.
PAIRS = [
    ("text", "bg", "text on the window"),
    ("text", "card", "text on a card or panel"),
    ("text", "sidebar", "text in the sidebar"),
    ("subtext", "bg", "secondary text on the window"),
    ("subtext", "card", "secondary text on a card (a note's preview)"),
    ("subtext", "sidebar", "secondary text in the sidebar (Sort, Show)"),
    ("accent_text", "bg", "accent text on the window (the repeat summary)"),
    ("accent_text", "card", "accent text on a card or panel"),
    ("accent_text", "sidebar", "accent text in the sidebar"),
    ("accent_text", "nav_tint", "the selected Settings section's name"),
    ("danger_text", "bg", "warning text on the window"),
    ("danger_text", "card", "warning text on a card or panel"),
    ("danger_text", "sidebar", "warning text in the sidebar"),
    ("danger_text", "danger_hover", "a warning button's words, pointed at"),
    ("danger_text", "bin_hover_card", "a bin on a card, pointed at (a glyph, "
                                      "owes 3:1)", AA_NON_TEXT),
    ("danger_text", "bin_hover_sidebar", "a bin in a list row, pointed at "
                                         "(a glyph, owes 3:1)", AA_NON_TEXT),
    ("success_text", "bg", "confirmation text on the window"),
    ("success_text", "card", "confirmation text on a card or panel"),
    ("success_text", "sidebar", "confirmation text in the sidebar"),
    ("on_accent", "accent", "words on an accent button (and the find bar's "
                            "current match)"),
    ("on_accent", "accent_hover", "words on an accent button, pointed at"),
    ("on_danger", "danger", "words on a destructive button"),
    ("on_success", "success", "words on a confirming button"),
    ("on_success", "success_pressed", "words on a confirming button, held down"),
    ("text", "find_all", "text of the other find matches"),
    ("text", "find_miss", "text in the find box when nothing is found"),
]

# Surfaces the app mixes from a palette rather than reading off it, each
# the way the app mixes it (the Settings nav and its two hover tints are
# mixed in ui/settings_page.py; the find surfaces in themes.py).
DERIVED = {
    "find_all": themes.find_all_surface,
    "nav_tint": lambda p: themes.blend(p["sidebar"], p["accent"], 0.16),
    "danger_hover": lambda p: themes.blend(p["card"], p["danger"], 0.14),
    "bin_hover_card": lambda p: themes.blend(p["card"], p["danger"], 0.16),
    "bin_hover_sidebar": lambda p: themes.blend(p["sidebar"], p["danger"], 0.16),
}

# Pairs still below AA, each with its reason. Empty since the accent
# colours were chosen (see ARCHITECTURE.md, Contrast, measured), and kept
# as the mechanism: a pair may only join it with a reason written here.
BELOW_AA = {}


def listed_below_aa():
    """{(theme, fg, bg): reason} for every pair BELOW_AA lists. Its shape
    is {theme: [(fg, bg, reason), ...]}."""
    return {(theme, fg, bg): reason
            for theme, pairs in BELOW_AA.items() for fg, bg, reason in pairs}


def owed():
    """{(fg, bg): the ratio that pair owes}."""
    return {(pair[0], pair[1]): (pair[3] if len(pair) > 3 else AA_NORMAL)
            for pair in PAIRS}


def luminance(colour):
    """Relative luminance, as WCAG 2.1 defines it."""
    value = colour.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    channels = [int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def ratio(one, other):
    light, dark = sorted((luminance(one), luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def colour_of(theme, key):
    palette = themes.THEMES[theme]
    if key in DERIVED:
        return DERIVED[key](palette)
    return key if key.startswith("#") else themes.palette_value(palette, key)


def measured():
    """{(theme, fg, bg): ratio} for every theme and pair."""
    out = {}
    for theme in themes.THEMES:
        for fg, bg in owed():
            out[(theme, fg, bg)] = ratio(colour_of(theme, fg),
                                         colour_of(theme, bg))
    return out


def one_value_one_role():
    """Colour values that name two different roles across the themes."""
    roles = {}
    for palette in themes.THEMES.values():
        for key, value in palette.items():
            roles.setdefault(value.lower(), set()).add(key)
    return {value: keys for value, keys in roles.items() if len(keys) > 1}


def accents_without_icons():
    """Accents with no window icon of their own in assets/."""
    missing = []
    for palette in themes.THEMES.values():
        stem = "icon_" + palette["accent"].lstrip("#").lower()
        for ext in (".ico", ".png"):
            if not os.path.exists(os.path.join(ROOT, "assets", stem + ext)):
                missing.append(stem + ext)
    return sorted(set(missing))


def icons_no_accent_wears():
    """Per-accent icons in assets/ that no theme's accent asks for any
    more: the build bundles every icon file, so they would ship unused."""
    worn = {"icon_" + p["accent"].lstrip("#").lower() for p in themes.THEMES.values()}
    left = []
    for name in os.listdir(os.path.join(ROOT, "assets")):
        stem, ext = os.path.splitext(name)
        hexpart = stem[len("icon_"):]
        if (stem.startswith("icon_") and len(hexpart) == 6 and ext in (".ico", ".png")
                and all(ch in "0123456789abcdef" for ch in hexpart.lower())
                and stem.lower() not in worn):
            left.append(name)
    return sorted(left)


def theme_order():
    return list(themes.DARK_THEMES) + list(themes.LIGHT_THEMES)


def markdown(ratios):
    order = theme_order()
    lines = ["| Text, and where | "
             + " | ".join(themes.THEME_LABELS[t] for t in order) + " |",
             "|---|" + "---:|" * len(order)]
    minimum = owed()
    for fg, bg, where, *_ in PAIRS:
        cells = []
        for theme in order:
            value = ratio_text = "%.1f" % ratios[(theme, fg, bg)]
            if ratios[(theme, fg, bg)] < minimum[(fg, bg)]:
                value = "**%s** ✗" % ratio_text
            cells.append(value)
        lines.append("| %s | %s |" % (where, " | ".join(cells)))
    return "\n".join(lines)


def table_in_docs():
    """The contrast table as docs/ARCHITECTURE.md has it, or None."""
    path = os.path.join(ROOT, "docs", "ARCHITECTURE.md")
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for start, line in enumerate(lines):
        if line.startswith("| Text, and where |"):
            end = start
            while end < len(lines) and lines[end].startswith("|"):
                end += 1
            return "\n".join(lines[start:end])
    return None


def main():
    ratios = measured()
    if "--markdown" in sys.argv:
        print(markdown(ratios))
        return 0
    problems = []
    if table_in_docs() != markdown(ratios):
        problems.append("the contrast table in docs/ARCHITECTURE.md is not "
                        "the measured one: paste in what --markdown prints")
    below = listed_below_aa()
    minimum = owed()
    for key, value in sorted(ratios.items()):
        listed = key in below
        need = minimum[key[1:]]
        if value < need and not listed:
            problems.append("%s: %s on %s is %.2f:1, below %.1f:1"
                            % (key[0], key[1], key[2], value, need))
        elif value >= need and listed:
            problems.append("%s: %s on %s now passes (%.2f:1) -- take it out "
                            "of BELOW_AA" % (key[0], key[1], key[2], value))
    for key in below:
        if key not in ratios:
            problems.append("BELOW_AA names a pair that is not measured: %s"
                            % (key,))
    for value, keys in sorted(one_value_one_role().items()):
        problems.append("%s is %s in different themes; the theme switch "
                        "remaps by value" % (value, " and ".join(sorted(keys))))
    for name in accents_without_icons():
        problems.append("assets/%s is missing: an accent without its window "
                        "icon (py tools/make_icon.py --all)" % name)
    for name in icons_no_accent_wears():
        problems.append("assets/%s is an icon no theme's accent wears: the "
                        "build would ship it unused" % name)
    if problems:
        for line in problems:
            print(line)
        print("\n%d problem(s)." % len(problems))
        return 1
    passing = sum(1 for key, value in ratios.items()
                  if value >= minimum[key[1:]])
    print("Contrast measured: %d of %d pairs at WCAG AA across %d themes; "
          "%d listed below it, each with its reason."
          % (passing, len(ratios), len(themes.THEMES), len(below)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
