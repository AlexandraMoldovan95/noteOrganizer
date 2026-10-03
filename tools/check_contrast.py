"""Every theme's text measured against WCAG, and kept from getting worse.

WHAT IT CHECKS
--------------
For each of the eight themes in noteorganizer/core/themes.py, the
contrast ratio WCAG 2.1 defines -- from relative luminance, not by eye --
between each text colour and each surface the app draws it on. All of the
app's text is 8 to 11 pt, which WCAG counts as normal-sized (large means
18 pt, or 14 pt bold), so every pair owes 4.5:1, the AA level.

Pairs still below AA are listed in BELOW_AA with the reason. Anything else
below it fails; so does a listed pair that has started to pass, so the
list can only shrink.

One more thing the theme switch depends on: it remaps colours by value,
so a colour value must mean one role across all the themes. And the table
in docs/ARCHITECTURE.md must be the one this prints, so it cannot go stale.

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
WHITE = "#ffffff"

# (text colour, surface, where the app draws it). A theme key, or WHITE
# for the buttons that set their text to white whatever the theme.
PAIRS = [
    ("text", "bg", "text on the window"),
    ("text", "card", "text on a card or panel"),
    ("text", "sidebar", "text in the sidebar"),
    ("subtext", "bg", "secondary text on the window"),
    ("subtext", "card", "secondary text on a card (a note's preview)"),
    ("subtext", "sidebar", "secondary text in the sidebar (Sort, Show)"),
    ("accent", "bg", "accent text on the window (the repeat summary)"),
    ("accent", "card", "accent text on a card or panel"),
    ("accent", "sidebar", "accent text in the sidebar"),
    ("danger", "bg", "warning text on the window"),
    ("danger", "card", "warning text on a card or panel"),
    ("danger", "sidebar", "warning text in the sidebar"),
    ("success", "bg", "confirmation text on the window"),
    ("success", "card", "confirmation text on a card or panel"),
    ("success", "sidebar", "confirmation text in the sidebar"),
    (WHITE, "accent", "white text on an accent button"),
    (WHITE, "accent_hover", "white text on an accent button, pointed at"),
    (WHITE, "danger", "white text on a destructive button"),
    (WHITE, "success", "white text on a confirming button"),
]

# Below AA today, each for the reason given. Accent, danger and success
# are each used both as text and as a button's fill under white text: on
# a dark theme the first wants a lighter shade and the second a darker one,
# so no single shade serves both, and a light theme's fix -- one darker
# shade -- changes how the theme looks. Which way to go is a design
# choice, set out in ARCHITECTURE.md (Contrast, measured), and waits for
# the person who decides how the app looks.
AWAITING_CHOICE = "a design choice about the accent colours, not made yet"
_ON_ALL = [(fg, s) for fg in ("accent", "danger", "success")
           for s in ("bg", "card", "sidebar")]
_WHITE_ON = [(WHITE, fill) for fill in ("accent", "accent_hover", "danger",
                                        "success")]
BELOW_AA = {
    "dark": [("accent", "bg"), ("accent", "card"), ("accent", "sidebar"),
             ("danger", "card")] + _WHITE_ON,
    "dark_ocean": [("accent", "card")] + _WHITE_ON,
    "dark_forest": _WHITE_ON,
    "dark_slate": _WHITE_ON,
    "light": _ON_ALL + [(WHITE, "accent"), (WHITE, "danger"),
                        (WHITE, "success")],
    "light_sky": _ON_ALL + [(WHITE, "accent"), (WHITE, "danger"),
                            (WHITE, "success")],
    "light_mint": _ON_ALL + _WHITE_ON,
    "light_warm": _ON_ALL + _WHITE_ON,
}


def listed_below_aa():
    """{(theme, fg, bg): reason} for every pair BELOW_AA lists."""
    return {(theme, fg, bg): AWAITING_CHOICE
            for theme, pairs in BELOW_AA.items() for fg, bg in pairs}


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
    return key if key.startswith("#") else themes.THEMES[theme][key]


def measured():
    """{(theme, fg, bg): ratio} for every theme and pair."""
    out = {}
    for theme in themes.THEMES:
        for fg, bg, _where in PAIRS:
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


def theme_order():
    return list(themes.DARK_THEMES) + list(themes.LIGHT_THEMES)


def markdown(ratios):
    order = theme_order()
    lines = ["| Text, and where | "
             + " | ".join(themes.THEME_LABELS[t] for t in order) + " |",
             "|---|" + "---:|" * len(order)]
    for fg, bg, where in PAIRS:
        cells = []
        for theme in order:
            value = ratio_text = "%.1f" % ratios[(theme, fg, bg)]
            if ratios[(theme, fg, bg)] < AA_NORMAL:
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
    for key, value in sorted(ratios.items()):
        listed = key in below
        if value < AA_NORMAL and not listed:
            problems.append("%s: %s on %s is %.2f:1, below %.1f:1"
                            % (key[0], key[1], key[2], value, AA_NORMAL))
        elif value >= AA_NORMAL and listed:
            problems.append("%s: %s on %s now passes (%.2f:1) -- take it out "
                            "of BELOW_AA" % (key[0], key[1], key[2], value))
    for key in below:
        if key not in ratios:
            problems.append("BELOW_AA names a pair that is not measured: %s"
                            % (key,))
    for value, keys in sorted(one_value_one_role().items()):
        problems.append("%s is %s in different themes; the theme switch "
                        "remaps by value" % (value, " and ".join(sorted(keys))))
    if problems:
        for line in problems:
            print(line)
        print("\n%d problem(s)." % len(problems))
        return 1
    passing = sum(1 for value in ratios.values() if value >= AA_NORMAL)
    print("Contrast measured: %d of %d text pairs at WCAG AA across %d themes; "
          "%d listed below it, each with its reason."
          % (passing, len(ratios), len(themes.THEMES), len(below)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
