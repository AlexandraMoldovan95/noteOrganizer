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

NOTE ON WHAT IS *NOT* HERE
--------------------------
The live, mutable category map (``CATEGORY_COLORS``) and the functions
that load and save it are still in ``note_organizer.py``: they read and
write ``settings.json``, so they belong with the storage layer, which
hasn't been extracted yet. Only the immutable defaults live here.
"""

# ---- Themes ----
THEMES = {
    # ---- DARK variants ----
    "dark": {  # Midnight Purple (original)
        "bg": "#1e1e2f",
        "sidebar": "#26263f",
        "accent": "#7c5cff",
        "accent_hover": "#9377ff",
        "card": "#2e2e48",
        "text": "#f2f2f7",
        "subtext": "#a0a0c0",
        "danger": "#ff5c7c",
        "success": "#4cd9a3",
        "calendar_has_notes": "#3d3168",
    },
    "dark_ocean": {  # deep blue
        "bg": "#0f1b2d",
        "sidebar": "#16273f",
        "accent": "#2f9be0",
        "accent_hover": "#54b0ec",
        "card": "#1c3350",
        "text": "#eaf2fb",
        "subtext": "#8fa8c4",
        "danger": "#ff6b6b",
        "success": "#3ecf8e",
        "calendar_has_notes": "#1f4266",
    },
    "dark_forest": {  # deep green
        "bg": "#14231b",
        "sidebar": "#1b3227",
        "accent": "#43c07a",
        "accent_hover": "#5ed494",
        "card": "#213e30",
        "text": "#eafaf0",
        "subtext": "#8fbaa1",
        "danger": "#ff7a7a",
        "success": "#4cd9a3",
        "calendar_has_notes": "#254e39",
    },
    "dark_slate": {  # neutral charcoal, warm accent
        "bg": "#1c1c22",
        "sidebar": "#26262e",
        "accent": "#e0863f",
        "accent_hover": "#ec9d5a",
        "card": "#2d2d38",
        "text": "#f3f2f0",
        "subtext": "#a8a8b0",
        "danger": "#ff6b6b",
        "success": "#4cd9a3",
        "calendar_has_notes": "#3a2f22",
    },
    # ---- LIGHT variants ----
    "light": {  # Soft Lavender (original)
        "bg": "#f5f5fa",
        "sidebar": "#e9e9f5",
        "accent": "#7c5cff",
        "accent_hover": "#6a49e6",
        "card": "#ffffff",
        "text": "#22223a",
        "subtext": "#6b6b85",
        "danger": "#e0405f",
        "success": "#2fae82",
        "calendar_has_notes": "#e3dbff",
    },
    "light_sky": {  # airy blue
        "bg": "#f0f6fc",
        "sidebar": "#dcebf8",
        "accent": "#1f88d6",
        "accent_hover": "#1873ba",
        "card": "#ffffff",
        "text": "#173049",
        "subtext": "#5a748c",
        "danger": "#e0405f",
        "success": "#2fae82",
        "calendar_has_notes": "#d3e7f8",
    },
    "light_mint": {  # fresh green
        "bg": "#f1f9f4",
        "sidebar": "#dcefe3",
        "accent": "#2aa971",
        "accent_hover": "#238e5f",
        "card": "#ffffff",
        "text": "#183328",
        "subtext": "#5b7d6c",
        "danger": "#e0405f",
        "success": "#2fae82",
        "calendar_has_notes": "#d3edde",
    },
    "light_warm": {  # warm cream, orange accent
        "bg": "#faf6f0",
        "sidebar": "#f1e7da",
        "accent": "#d97a2b",
        "accent_hover": "#bd6822",
        "card": "#ffffff",
        "text": "#3a2c1c",
        "subtext": "#8a7660",
        "danger": "#e0405f",
        "success": "#2fae82",
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


def contrasting_fg(hex_color):
    """Black or near-white, whichever reads better against *hex_color*.

    The standard perceived-luminance weighting: the eye is far more
    sensitive to green than to blue, so a plain average of the channels
    picks the wrong side on colours like pure blue.

    This exists because the text-colour and highlight buttons show a swatch
    of the active colour as their own background, and the letter on top has
    to stay legible against any colour in the palette on any of the themes.
    """
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1a1a1a" if luminance > 0.6 else "#ffffff"
