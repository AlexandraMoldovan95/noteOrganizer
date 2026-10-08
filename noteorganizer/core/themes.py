"""Colour palettes, themes, and the fixed layout numbers.

WHAT THIS MODULE IS FOR
-----------------------
Pure data: no logic, no file access, nothing that can fail. Everything the
app needs to know about how it should *look*, in one place.

* :data:`THEMES` — eight palettes (four dark, four light). Each maps the
  same set of role names (``bg``, ``card``, ``text``, ``accent``...) to a
  hex colour, which is what lets a theme switch be a straight swap.
* :data:`DARK_THEMES` / :data:`LIGHT_THEMES` — which names belong to which
  mode, so "switch to light" knows where to go.
* :data:`THEME_LABELS` — the friendly names shown in Settings.
* :data:`DEFAULT_CATEGORY_COLORS`, :data:`PROTECTED_CATEGORY` — the
  starting categories, and the one that can never be deleted.
* :data:`PALETTE_COLORS`, :data:`PRESET_NOTE_COLORS`,
  :data:`HIGHLIGHT_COLOR_PALETTE` — swatches the user picks from.
* :data:`SIDEBAR_WIDTH`, :data:`EDITOR_MIN_WIDTH` — fixed layout sizes.

WHY THEMES ARE SHAPED THIS WAY
------------------------------
Every theme defines exactly the same keys. Nothing in the app asks "which
theme is this?" before choosing a colour — it asks for ``colors["card"]``
and gets whatever that means in the current theme. Adding a ninth theme
means adding one dict here and nothing else.

That uniformity is also what makes the theme-switch safety net possible:
because the palettes are known, the app can spot a widget still holding a
colour from a *different* theme and remap it. See ``_recolor_stragglers``
in the UI, and `docs/ISSUES_LOG.md` on the theme-switch flicker.

FILL AND TEXT
-------------
``accent``, ``danger`` and ``success`` are FILLS: the colour of a button,
a banner, a selected tab. Each has a twin for words on an ordinary
surface -- ``accent_text``, ``danger_text``, ``success_text`` -- because
no single shade can be both on a dark theme: words on a dark surface want
a lighter one, a fill under its own words a darker one. The words ON a
fill are not written down at all: :func:`letters_on` picks white or
near-black by measured contrast, and the names ``on_accent``,
``on_danger``, ``on_success`` ask for them (:func:`palette_value`).
Delete is the dark fill with white words in every theme and Save a light
one with dark words, so the two differ in lightness as well as hue: a
reader who cannot tell red from green still tells them apart.
``tools/check_contrast.py`` measures every pair; see "Contrast, measured"
in `docs/ARCHITECTURE.md`.

NOTE ON WHAT IS *NOT* HERE
--------------------------
The live, mutable category map (``CATEGORY_COLORS``) and the functions
that load and save it are still in ``note_organizer.py``: they read and
write ``settings.json``, so they belong with the storage layer, which
hasn't been extracted yet. Only the immutable defaults live here.
"""

import colorsys
import functools

# ---- Themes ----
THEMES = {
    # ---- DARK variants ----
    "dark": {  # Midnight Purple (original)
        "bg": "#1e1e2f",
        "sidebar": "#26263f",
        "accent": "#a48fff",
        "accent_hover": "#bcadff",
        "card": "#2e2e48",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#f2f2f7",
        "subtext": "#a0a0c0",
        "danger": "#b01c3c",
        "success": "#4cd9a3",
        # The same three roles as words on a surface (see FILL AND TEXT).
        "accent_text": "#aba4ff",
        "danger_text": "#ff8d9d",
        "success_text": "#72e2b9",
        "find_miss": "#522b33",
        "calendar_has_notes": "#3d3168",
    },
    "dark_ocean": {  # deep blue
        "bg": "#0f1b2d",
        "sidebar": "#16273f",
        "accent": "#2f9be0",
        "accent_hover": "#54b0ec",
        "card": "#1c3350",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#eaf2fb",
        "subtext": "#8fa8c4",
        "danger": "#b01c3c",
        "success": "#3ecf8e",
        "accent_text": "#50b5fa",
        "danger_text": "#ff8f8f",
        "success_text": "#62dba4",
        "find_miss": "#522f2f",
        "calendar_has_notes": "#1f4266",
    },
    "dark_forest": {  # deep green
        "bg": "#14231b",
        "sidebar": "#1b3227",
        "accent": "#43c07a",
        "accent_hover": "#5ed494",
        "card": "#213e30",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#eafaf0",
        "subtext": "#8fbaa1",
        "danger": "#b01c3c",
        "success": "#4fd3e0",
        "accent_text": "#4ec983",
        "danger_text": "#ffa09d",
        "success_text": "#7fdfea",
        "find_miss": "#523333",
        "calendar_has_notes": "#254e39",
    },
    "dark_slate": {  # neutral charcoal, warm accent
        "bg": "#1c1c22",
        "sidebar": "#26262e",
        "accent": "#e0863f",
        "accent_hover": "#ec9d5a",
        "card": "#2d2d38",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#f3f2f0",
        "subtext": "#a8a8b0",
        "danger": "#b01c3c",
        "success": "#5ad6d0",
        "accent_text": "#ec914b",
        "danger_text": "#ff8f8f",
        "success_text": "#7fe0dc",
        "find_miss": "#522f2f",
        "calendar_has_notes": "#3a2f22",
    },
    # ---- LIGHT variants ----
    "light": {  # Soft Lavender (original)
        "bg": "#f5f5fa",
        "sidebar": "#e9e9f5",
        "accent": "#6a49e6",
        "accent_hover": "#5a38d6",
        "card": "#ffffff",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#22223a",
        "subtext": "#676780",
        "danger": "#9e1838",
        "success": "#2fae82",
        "accent_text": "#5b2dd2",
        "danger_text": "#a81a3e",
        "success_text": "#00704f",
        "find_miss": "#f9dddd",
        "calendar_has_notes": "#e3dbff",
    },
    "light_sky": {  # airy blue
        "bg": "#f0f6fc",
        "sidebar": "#dcebf8",
        "accent": "#1a73b8",
        "accent_hover": "#135f99",
        "card": "#ffffff",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#173049",
        "subtext": "#536b81",
        "danger": "#9e1838",
        "success": "#2fae82",
        "accent_text": "#005b97",
        "danger_text": "#a81a3e",
        "success_text": "#00704f",
        "find_miss": "#f9dddd",
        "calendar_has_notes": "#d3e7f8",
    },
    "light_mint": {  # fresh green
        "bg": "#f1f9f4",
        "sidebar": "#dcefe3",
        "accent": "#28a66e",
        "accent_hover": "#3cbb83",
        "card": "#ffffff",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#183328",
        "subtext": "#527061",
        "danger": "#9e1838",
        "success": "#2db4c2",
        "accent_text": "#006640",
        "danger_text": "#a81a3e",
        "success_text": "#00707c",
        "find_miss": "#f9dddd",
        "calendar_has_notes": "#d3edde",
    },
    "light_warm": {  # warm cream, orange accent
        "bg": "#faf6f0",
        "sidebar": "#f1e7da",
        "accent": "#d97a2b",
        "accent_hover": "#e58f47",
        "card": "#ffffff",
        # The well a check mark sits in, light in every theme because the
        # mark is dark. Tk paints the mark in a box's text colour, so a box
        # with words draws its own (_drawn_tick_box); the rest keep Tk's.
        "check_well": "#f7f7fb",
        "text": "#3a2c1c",
        "subtext": "#776653",
        "danger": "#9e1838",
        "success": "#33b8b0",
        "accent_text": "#8a4600",
        "danger_text": "#a81a3e",
        "success_text": "#00726b",
        "find_miss": "#f9dddd",
        "calendar_has_notes": "#f3e2cd",
    },
}

# Which variants are dark vs light — used to keep 'light is light, dark is dark'
# behavior and to group them in the theme picker.
DARK_THEMES = ["dark", "dark_ocean", "dark_forest", "dark_slate"]
LIGHT_THEMES = ["light", "light_sky", "light_mint", "light_warm"]

# Friendly display names for the picker.
THEME_LABELS = {
    "dark": "Midnight Purple",
    "dark_ocean": "Ocean Blue",
    "dark_forest": "Forest Green",
    "dark_slate": "Warm Charcoal",
    "light": "Soft Lavender",
    "light_sky": "Sky Blue",
    "light_mint": "Fresh Mint",
    "light_warm": "Warm Cream",
}

DEFAULT_CATEGORY_COLORS = {
    "General": "#7c5cff",
    "Work": "#4cc9f0",
    "Personal": "#f9c74f",
    "Ideas": "#f77f00",
    "Urgent": "#ff5c7c",
}

# A curated palette for the inline color picker (used for categories and
# calendar day markers). Enough variety without overwhelming; one click picks
# a color, no OS dialog.
PALETTE_COLORS = [
    "#7c5cff", "#4cc9f0", "#f9c74f", "#f77f00", "#ff5c7c",
    "#43aa8b", "#90be6d", "#f94144", "#577590", "#9b5de5",
    "#00bbf9", "#00f5d4", "#fee440", "#ff924c", "#ff6392",
    "#8ac926", "#1982c4", "#6a4c93", "#e07a5f", "#b5838d",
]

# "General" is the safety net: it can't be renamed or deleted, so there is
# always a valid home for notes whose category is removed.
PROTECTED_CATEGORY = "General"


# Quick-pick palette offered when choosing a custom note color, and (below)
# for text color. Swatches only, deliberately — no hex-code entry, since
# most users don't think in hex; the palette is sized generously instead so
# picking a swatch stays a real choice, not just the ten "obvious" colors.
PRESET_NOTE_COLORS = [
    "#7c5cff", "#4cc9f0", "#f9c74f", "#f77f00", "#ff5c7c",
    "#4cd9a3", "#ff8fa3", "#a3a3ff", "#ffd166", "#06d6a0",
    "#e63946", "#3a86ff", "#c77dff", "#8ac926", "#6c757d",
]

# Note body TEXT color reuses PRESET_NOTE_COLORS above, for visual
# consistency with the rest of the app. HIGHLIGHT (background) color gets
# its own, separate palette: deliberately soft/pastel, the way a real
# highlighter marker is, so text drawn on top of it stays readable —
# PRESET_NOTE_COLORS' vivid, saturated tones work fine as a small accent
# dot but would be too strong as a block of background behind text.
HIGHLIGHT_COLOR_PALETTE = [
    "#fff3b0",  # soft yellow
    "#c8f4d9",  # soft green
    "#ffd6e8",  # soft pink
    "#cde7ff",  # soft blue
    "#ffe0b3",  # soft peach
    "#e0d4ff",  # soft purple
    "#ffd1d1",  # soft coral
    "#c8f4ec",  # soft teal
    "#e8e8e8",  # soft gray
    "#f0f4c3",  # soft lime
]

SIDEBAR_WIDTH = 280
EDITOR_MIN_WIDTH = 620


# ---- Colour arithmetic ----
#
# Both were staticmethods on the app class. They are pure colour maths and
# get used from several places, so they belong beside the palettes rather
# than on whatever happens to draw next.

def blend(hex_a, hex_b, t):
    """Mix two ``#rrggbb`` colours. ``t=0`` gives *hex_a*, ``t=1`` gives *hex_b*."""
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % mixed


def inset_surface(palette):
    """The surface of a well sunk *inside* a card, for this palette.

    A step further from the page ground than the card is: lighter on a dark
    theme, darker on a light one, which is why it blends toward ``text``
    rather than hardcoding a direction.
    """
    return blend(palette["card"], palette["text"], 0.07)


def hairline(palette):
    """The colour of a card's border and of the rules between its rows."""
    return blend(palette["card"], palette["subtext"], 0.22)


def miss_surface(palette):
    """The ground of a search box whose words were not found: a tint of the
    theme's warning red over white on a light theme, over near-black on a
    dark one. Mixed into the theme's own surface instead, the red went grey
    on the blue and green themes; one fixed dark red, before that, put dark
    words on dark on the light ones (1.2:1). The strengths, and the light
    themes' truer red, are her choices from photographed boards.

    Written into each palette as ``find_miss`` rather than mixed here: the
    tints were mixed from the warning reds of the time, and those reds have
    since darkened for contrast, which would have moved a shade chosen by
    eye."""
    return palette["find_miss"]


def find_all_surface(palette):
    """The ground of every match the find bar marks in a note: the accent
    at a third of its strength over the card. The current match wears the
    accent itself."""
    return blend(palette["card"], palette["accent"], 0.35)


# The words on a filled control: white, or this near-black.
LETTERS_LIGHT = "#ffffff"
LETTERS_DARK = "#1a1a1a"

# Palette names for the words on each fill. They are worked out from the
# fill (see palette_value), so no palette spells them out.
LETTER_KEYS = {"on_accent": "accent", "on_danger": "danger",
               "on_success": "success"}


def relative_luminance(hex_color):
    """Relative luminance, as WCAG 2.1 defines it, of a ``#rrggbb`` colour."""
    channels = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(one, other):
    """The WCAG 2.1 contrast ratio between two ``#rrggbb`` colours."""
    light, dark = sorted((relative_luminance(one), relative_luminance(other)),
                         reverse=True)
    return (light + 0.05) / (dark + 0.05)


def letters_on(fill):
    """The words for a control filled with *fill*: white or near-black,
    whichever has the higher WCAG contrast on it.

    Not contrasting_fg, which answers a different question (a threshold of
    perceived brightness, for colours the person picks) and puts white on
    most of the fills this answers near-black for. This is the measure the
    contrast gate holds every button to, so the two cannot disagree. A
    colour it cannot read gets white, as contrasting_fg's does."""
    try:
        dark = contrast_ratio(LETTERS_DARK, fill)
        light = contrast_ratio(LETTERS_LIGHT, fill)
    except (TypeError, ValueError, IndexError):
        return LETTERS_LIGHT
    return LETTERS_DARK if dark > light else LETTERS_LIGHT


@functools.lru_cache(maxsize=512)
def legible_on(colour, ground, ink, minimum=4.6):
    """*colour* as words on *ground*: itself when it reads there at
    *minimum*, else the nearest shade of it that does. For a colour the
    person picked -- a category's, a note's own -- shown as words; the stripe
    beside it keeps it whole. On a light ground the shade is darker in the
    same hue, a little richer (mixed toward the theme's bluish text, the
    Personal yellow went khaki); on a dark ground it is mixed toward *ink*,
    the theme's light text. *minimum* is a step over AA, for canvas text at
    8-9 pt. Unreadable input gets *ink*."""
    try:
        if contrast_ratio(colour, ground) >= minimum:
            return colour
        if contrast_ratio(LETTERS_DARK, ground) >= contrast_ratio(LETTERS_LIGHT, ground):
            red, green, blue = (int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
            hue, sat, val = colorsys.rgb_to_hsv(red, green, blue)
            for step in range(1, 101):
                shade = colorsys.hsv_to_rgb(hue, min(1.0, sat * (1 + step / 200)),
                                            val * (1 - step / 100))
                darker = "#%02x%02x%02x" % tuple(round(c * 255) for c in shade)
                if contrast_ratio(darker, ground) >= minimum:
                    return darker
        else:
            for step in range(1, 21):
                mixed = blend(colour, ink, step / 20)
                if contrast_ratio(mixed, ground) >= minimum:
                    return mixed
    except (TypeError, ValueError, IndexError):
        pass
    return ink


def palette_value(palette, key):
    """A colour of *palette* by its name, the ``on_*`` names included."""
    fill = LETTER_KEYS.get(key)
    return letters_on(palette[fill]) if fill else palette[key]


def contrasting_fg(hex_color):
    """Black or near-white, whichever reads better against *hex_color*.

    The standard perceived-luminance weighting: the eye is far more
    sensitive to green than to blue, so a plain average of the channels
    picks the wrong side on colours like pure blue.

    This exists because the text-colour and highlight buttons show a swatch
    of the active colour as their own background, and the letter on top has
    to stay legible against any colour in the palette on any of the themes.

    A colour it cannot read gets white, the answer every painted calendar
    day had before it learned contrast: raising here, in the middle of the
    month's drawing, left the month half drawn and unclickable.
    """
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (AttributeError, ValueError):
        return "#ffffff"
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1a1a1a" if luminance > 0.6 else "#ffffff"
