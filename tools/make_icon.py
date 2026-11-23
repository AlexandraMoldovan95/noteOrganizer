"""Draw the application icon, from code.

WHY THIS IS A SCRIPT AND NOT A FILE
-----------------------------------
An `.ico` checked in on its own is a binary nobody can change: the next
person who wants it a shade darker, or needs a 512px version for a store
listing, has to start over in an image editor. Here the drawing IS the
source, it regenerates at any size, and a change shows up in a diff like
anything else.

THE DESIGNS
-----------
Nine, in two families, so there is something to choose between rather than
something to accept. The one that ships is ``tool`` (DEFAULT_DESIGN), of
the second family -- square-cornered, in the app's own desktop idiom (see
the comment above ``design_desktop``). The first family's five are below.
Each has to say something true about this app, and each has to survive
16x16 in a taskbar -- the constraint that kills most icon ideas:

``card``      A note card with a coloured stripe down its left edge.
              Every note in the app's list wears one, in its category's
              colour, so this says "a note that belongs somewhere"
              rather than "a page".
``stack``     Cards behind each other, each in a different category
              colour. The *organizer* half of the name: not one note, a
              filed collection.
``calendar``  A card whose head is a date band, with days below and one
              of them marked. The calendar is a first-class tab here,
              and dated and repeating notes are what this app does that
              a plain notes app does not.
``check``     A card with a tick. The most legible glyph there is at
              16px, and the checklist is real -- but it argues the app
              is a to-do list, which is only half true.
``stripe``    No card at all: a bold colour bar and lines, straight on
              the tile. The most modern, the most legible small, and it
              says the least.

Small sizes are REDRAWN, not shrunk. At 16px a card drawn with the large
proportions swallows the tile and becomes a white blob with no colour
left to identify it, so every design below changes its proportions and
drops its detail below 48px.

Drawn at 8x and downsampled, because Pillow's shapes have no
anti-aliasing of their own.

RUNNING IT
----------
    py tools/make_icon.py                  # the chosen design -> assets/
    py tools/make_icon.py --all            # one icon per theme accent
    py tools/make_icon.py --sheet          # all nine, side by side
    py tools/make_icon.py --design stack   # build a different one

The `.ico` carries the six sizes Windows asks for (16 through 256).
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets")
# Preview sheets live one level down, out of the way of the build. The
# spec globs assets/icon*.ico and assets/icon*.png into the bundle, and
# a comparison sheet sitting beside the real icons was shipping with the
# app -- the kind of thing a glob does quietly.
PREVIEW_DIR = os.path.join(OUT_DIR, "previews")

# The app's own palette (noteorganizer/core/themes.py, the default theme).
# ACCENT is rebound per drawing -- see draw_icon and accents_in_use below -- so
# that every theme gets an icon in its own colour. Everything else stays
# put on purpose: the panel keeps the dark background whatever the theme,
# because a light icon disappears into a light taskbar, and the category
# stripes are the category palette, which does not follow the theme.
ACCENT = (124, 92, 255)          # #7c5cff
ACCENT_DEEP = (98, 70, 214)      # a shade down, for the tile's depth


def _deepen(rgb, factor=0.79):
    """The shade used under the accent, derived rather than listed."""
    return tuple(max(0, min(255, int(round(c * factor)))) for c in rgb)


def _rgb(hex_colour):
    return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))


def accents_in_use():
    """Every distinct accent the app's themes wear, read from the themes.

    Read rather than listed, and the FILE IS NAMED AFTER THE COLOUR --
    `icon_d97a2b.ico` -- on purpose. A table mapping theme names to icon
    names would be a second place to keep in step, and a theme added
    later would quietly get the wrong icon or none. This way the app
    computes the filename from the colour it is already holding, and a
    new theme's accent needs only a re-run of this script (--all); the
    rest of a new theme is in core/themes.py's docstring.
    """
    import sys
    sys.path.insert(0, ROOT)
    from noteorganizer.core.themes import THEMES
    found = {}
    for theme, palette in THEMES.items():
        found.setdefault(palette["accent"].lower(), []).append(theme)
    return found
CARD = (248, 248, 252)           # the note card
CARD_DIM = (214, 210, 236)       # cards sitting behind the front one
# The stripe is deliberately NOT the accent. The first version made it
# the same purple as the tile and it vanished -- what was left was the
# generic document glyph every notes app has.
MINT = (76, 217, 163)            # #4cd9a3 — the palette's success
CORAL = (255, 92, 124)           # #ff5c7c — the palette's danger
SKY = (47, 155, 224)             # #2f9be0 — another theme's accent
INK = (150, 150, 175)            # the "text" lines

SCALE = 8
SIZES = (256, 128, 64, 48, 32, 16)
# Chosen 2026-09-12: the icon is a picture of the window that opens.
# The rounded-tile family was drawn first and looked good, but it is
# the idiom of phone and web apps -- an icon promising one of those
# and then opening a dense Tkinter desktop tool breaks its promise
# in the first second.
DEFAULT_DESIGN = "tool"


def _tile(d, s):
    """The rounded app tile every design sits on."""
    pad = s * 0.03
    radius = s * 0.22
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=radius,
                        fill=ACCENT)
    return pad, radius


def _depth(img, s, pad, radius):
    """A slightly deeper band along the bottom, clipped to the tile, so it
    reads as an object rather than a flat swatch at large sizes."""
    band = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(band).rounded_rectangle(
        [pad, pad, s - pad, s - pad], radius=radius, fill=ACCENT_DEEP)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rectangle([0, s * 0.72, s, s], fill=90)
    img.paste(band, (0, 0), mask)


def _lines(d, s, x0, x1, y0, widths, thickness=0.048, gap=0.15):
    for i, width in enumerate(widths):
        y = y0 + i * s * gap
        d.rounded_rectangle([x0, y, x0 + (x1 - x0) * width, y + s * thickness],
                            radius=s * 0.024, fill=INK)


def _plate(d, s, x0, y0, x1, y1, fill, stripe, stripe_frac, small):
    """A card with its category stripe down the left edge."""
    d.rounded_rectangle([x0, y0, x1, y1],
                        radius=s * (0.04 if small else 0.05), fill=fill)
    sw = (x1 - x0) * stripe_frac
    d.rounded_rectangle([x0, y0, x0 + sw, y1],
                        radius=s * (0.04 if small else 0.03), fill=stripe)
    d.rectangle([x0 + sw * 0.5, y0, x0 + sw, y1], fill=stripe)
    return sw


def design_card(d, s, size, small):
    """A note card wearing its category's stripe."""
    inset_x = 0.30 if small else 0.24
    inset_y = 0.24 if small else 0.19
    x0, y0 = s * inset_x, s * inset_y
    x1, y1 = s * (1 - inset_x), s * (1 - inset_y)
    sw = _plate(d, s, x0, y0, x1, y1, CARD, MINT,
                0.30 if small else 0.14, small)
    if size >= 48:
        _lines(d, s, x0 + sw + s * 0.05, x1 - s * 0.06, y0 + s * 0.13,
               (1.0, 1.0, 0.6))


def design_stack(d, s, size, small):
    """Filed cards, each in a different category colour."""
    if small:
        # Two cards only: three at 16px is a smear.
        plates = ((0.10, -0.10, CARD_DIM, SKY), (0.0, 0.0, CARD, MINT))
        inset_x, inset_y, stripe_frac = 0.28, 0.26, 0.26
    else:
        plates = ((0.13, -0.13, CARD_DIM, CORAL),
                  (0.065, -0.065, CARD_DIM, SKY),
                  (0.0, 0.0, CARD, MINT))
        inset_x, inset_y, stripe_frac = 0.25, 0.24, 0.13
    for dx, dy, fill, stripe in plates:
        _plate(d, s, s * (inset_x + dx), s * (inset_y + dy),
               s * (1 - inset_x + dx), s * (1 - inset_y + dy),
               fill, stripe, stripe_frac, small)
    if size >= 64:
        x0, y0 = s * inset_x, s * inset_y
        x1 = s * (1 - inset_x)
        sw = (x1 - x0) * stripe_frac
        _lines(d, s, x0 + sw + s * 0.045, x1 - s * 0.05, y0 + s * 0.10,
               (1.0, 0.62), thickness=0.042, gap=0.115)


def design_calendar(d, s, size, small):
    """A note that knows what day it is."""
    inset_x = 0.26 if small else 0.21
    inset_y = 0.24 if small else 0.20
    x0, y0 = s * inset_x, s * inset_y
    x1, y1 = s * (1 - inset_x), s * (1 - inset_y)
    radius = s * (0.04 if small else 0.05)
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=CARD)
    # The date band across the head, the way the app's calendar header is
    # the one coloured thing above a page of white cells.
    band_h = (y1 - y0) * (0.32 if small else 0.24)
    d.rounded_rectangle([x0, y0, x1, y0 + band_h + radius], radius=radius,
                        fill=MINT)
    d.rectangle([x0, y0 + band_h * 0.5, x1, y0 + band_h], fill=MINT)
    cols, rows = (3, 2) if small else (4, 3)
    pad = (x1 - x0) * (0.13 if small else 0.11)
    gx0, gy0 = x0 + pad, y0 + band_h + pad * 0.9
    gx1, gy1 = x1 - pad, y1 - pad * 0.9
    cw = (gx1 - gx0) / cols
    ch = (gy1 - gy0) / rows
    dot = min(cw, ch) * (0.66 if small else 0.52)
    marked = (0, 1) if small else (1, 1)
    for r in range(rows):
        for c in range(cols):
            cxm = gx0 + cw * (c + 0.5)
            cym = gy0 + ch * (r + 0.5)
            # One day marked, the way a note sits on a date.
            fill = ACCENT if (r, c) == marked else INK
            d.ellipse([cxm - dot / 2, cym - dot / 2,
                       cxm + dot / 2, cym + dot / 2], fill=fill)


def design_check(d, s, size, small):
    """A card with a tick — the most legible glyph at 16px."""
    inset_x = 0.28 if small else 0.23
    inset_y = 0.24 if small else 0.19
    x0, y0 = s * inset_x, s * inset_y
    x1, y1 = s * (1 - inset_x), s * (1 - inset_y)
    d.rounded_rectangle([x0, y0, x1, y1],
                        radius=s * (0.04 if small else 0.05), fill=CARD)
    w, h = x1 - x0, y1 - y0
    # The tick fills the card at small sizes, and sits in its top half
    # when there are lines to keep it company.
    if small:
        cx, cy, span, thick = x0 + w * 0.5, y0 + h * 0.50, w * 0.60, s * 0.080
    else:
        cx, cy, span, thick = x0 + w * 0.5, y0 + h * 0.36, w * 0.54, s * 0.055
    d.line([(cx - span * 0.5, cy),
            (cx - span * 0.12, cy + span * 0.36),
            (cx + span * 0.5, cy - span * 0.38)],
           fill=MINT, width=max(1, int(thick)), joint="curve")
    if size >= 48:
        _lines(d, s, x0 + w * 0.16, x1 - w * 0.16, y0 + h * 0.60,
               (1.0, 0.6), thickness=0.045, gap=0.135)


def design_stripe(d, s, size, small):
    """No card: a bold bar and lines, straight on the tile."""
    x0, x1 = s * 0.27, s * 0.73
    y0, y1 = s * 0.28, s * 0.72
    bar_w = (x1 - x0) * (0.28 if small else 0.20)
    d.rounded_rectangle([x0, y0, x0 + bar_w, y1], radius=s * 0.035, fill=MINT)
    lines = (1.0, 0.62) if small else (1.0, 1.0, 0.6)
    thickness = 0.090 if small else 0.062
    spacing = (y1 - y0 - s * thickness) / (len(lines) - 1) / s
    _lines(d, s, x0 + bar_w + s * 0.06, x1, y0, lines,
           thickness=thickness, gap=spacing)



# ---------------------------------------------------------------------
# A second family, in the app's own visual language rather than the web's.
#
# The five above are drawn in the idiom every phone and web app has used
# for a decade: a rounded squircle tile, a soft palette, generous empty
# space. They look good, and they describe a different program. This one
# is a dense Tkinter desktop tool -- square-cornered rectangles, thin
# accent borders, small type, everything packed close. An icon promising
# a glossy web app and then opening that window breaks its promise in
# the first second.
#
# So these four borrow from where the app actually lives: Windows
# desktop utilities, most of which do not use a tile at all.
# ---------------------------------------------------------------------

# The app's real category colours (noteorganizer/core/themes.py's
# DEFAULT_CATEGORY_COLORS). There is no green among them -- the mint an
# earlier draft used for the selected card was invented, and it is the
# success colour, which the note list never shows.
CAT_GENERAL = (124, 92, 255)     # #7c5cff
CAT_WORK = (76, 201, 240)        # #4cc9f0
CAT_PERSONAL = (249, 199, 79)    # #f9c74f

TOOL_BG = (30, 30, 47)           # #1e1e2f - the app's own background
TOOL_CARD = (46, 46, 72)         # #2e2e48 - its card fill


def design_desktop(d, s, size, small):
    """No tile: the app's own note card, as an object.

    The classic Windows-utility shape -- a thing on transparency rather
    than a glyph inside a badge. Square corners and a thin accent border,
    which is the vocabulary every panel in the program is built from.
    """
    w = s * (0.74 if small else 0.68)
    h = s * (0.86 if small else 0.82)
    x0, y0 = (s - w) / 2, (s - h) / 2
    x1, y1 = x0 + w, y0 + h
    border = max(1.0, s * (0.045 if small else 0.028))
    # Border first, fill inside it: Tk's highlightthickness draws the same
    # way, and it is why every panel in the app has a thin bright edge.
    d.rectangle([x0, y0, x1, y1], fill=ACCENT)
    d.rectangle([x0 + border, y0 + border, x1 - border, y1 - border],
                fill=CARD)
    sw = w * (0.26 if small else 0.15)
    d.rectangle([x0 + border, y0 + border, x0 + border + sw, y1 - border],
                fill=MINT)
    if size >= 48:
        _lines(d, s, x0 + border + sw + s * 0.055, x1 - border - s * 0.05,
               y0 + h * 0.20, (1.0, 1.0, 0.58), thickness=0.045, gap=0.145)


def design_pixel(d, s, size, small):
    """Drawn on a coarse grid, so every edge lands on a whole pixel.

    Utilities that have been on Windows for twenty years look like this:
    hard edges, no blur, legible because the shapes line up with the
    pixel rather than because they are large. Everything snaps to a
    16-unit grid -- the size that actually has to work.
    """
    u = s / 16.0

    def cell(cx, cy, cw, ch, fill):
        d.rectangle([round(cx * u), round(cy * u),
                     round((cx + cw) * u) - 1, round((cy + ch) * u) - 1],
                    fill=fill)

    cell(2, 1, 12, 14, ACCENT)          # the page's outline
    cell(3, 2, 10, 12, CARD)            # the page
    cell(3, 2, 2, 12, MINT)             # the category stripe
    if size >= 32:
        for row, width in ((4, 6), (6, 6), (8, 4)):
            cell(6, row, width, 1, INK)
    else:
        cell(6, 5, 6, 1, INK)
        cell(6, 8, 4, 1, INK)


def design_angled(d, s, size, small):
    """A card with thickness, sitting on more of its kind.

    Not flat and not a tile -- an object on a desk. This is the idiom of
    the desktop note programs people keep for years, and it is warmer
    than anything above without pretending to be a phone app.
    """
    back = s * 0.045
    w = s * (0.70 if small else 0.64)
    h = s * (0.80 if small else 0.78)
    x0, y0 = (s - w) / 2 - back * 0.5, (s - h) / 2 - back * 0.5
    x1, y1 = x0 + w, y0 + h
    d.rectangle([x0 + back, y0 + back, x1 + back, y1 + back], fill=ACCENT_DEEP)
    d.rectangle([x0 + back * 0.5, y0 + back * 0.5,
                 x1 + back * 0.5, y1 + back * 0.5], fill=ACCENT)
    d.rectangle([x0, y0, x1, y1], fill=CARD)
    sw = w * (0.24 if small else 0.14)
    d.rectangle([x0, y0, x0 + sw, y1], fill=MINT)
    if size >= 48:
        _lines(d, s, x0 + sw + s * 0.05, x1 - s * 0.045, y0 + h * 0.19,
               (1.0, 1.0, 0.55), thickness=0.042, gap=0.135)


def design_tool(d, s, size, small):
    """The app's own window, in miniature.

    A dark panel in the program's background colour, square-cornered,
    wearing the thin accent border its panels wear -- and inside it the
    two things the window is: a sidebar of note cards and one note open
    beside them.

    The colours are the app's real ones, which took a correction to get
    right. An earlier version marked the open card in mint; mint is the
    palette's *success* colour, used for toasts and a ticked checklist
    item, and it appears nowhere in the note list. The stripes below are
    the actual category colours, and the open card is marked the way the
    app marks it -- a brighter card with an accent edge, not a different
    hue.
    """
    pad = s * 0.06
    border = max(1.0, s * (0.05 if small else 0.03))
    d.rectangle([pad, pad, s - pad, s - pad], fill=ACCENT)
    x0, y0 = pad + border, pad + border
    x1, y1 = s - pad - border, s - pad - border
    d.rectangle([x0, y0, x1, y1], fill=TOOL_BG)

    side_w = (x1 - x0) * (0.38 if small else 0.32)
    d.rectangle([x0, y0, x0 + side_w, y1], fill=TOOL_CARD)

    # Note cards down the sidebar, each with its category's stripe. Two
    # at small sizes, three when there is room -- the third would be a
    # smear at 16px and its stripe would not read at all.
    cards = ((CAT_GENERAL, True), (CAT_WORK, False), (CAT_PERSONAL, False))
    if small:
        cards = cards[:2]
    gap = (y1 - y0) / (len(cards) + 1.4)
    inset = side_w * 0.13
    for i, (stripe, selected) in enumerate(cards):
        cy0 = y0 + gap * (0.45 + i)
        cy1 = cy0 + gap * 0.70
        cx0 = x0 + inset
        cx1 = x0 + side_w - inset
        if selected:
            # The app draws a 2px accent border round the open card.
            edge = max(1.0, s * (0.022 if small else 0.013))
            d.rectangle([cx0 - edge, cy0 - edge, cx1 + edge, cy1 + edge],
                        fill=ACCENT)
        d.rectangle([cx0, cy0, cx1, cy1], fill=CARD if selected else TOOL_BG)
        sw = (cx1 - cx0) * (0.26 if small else 0.17)
        d.rectangle([cx0, cy0, cx0 + sw, cy1], fill=stripe)

    # The open note, to the right of the sidebar.
    tx0 = x0 + side_w + s * (0.045 if small else 0.055)
    tx1 = x1 - s * (0.045 if small else 0.055)
    if small:
        _lines(d, s, tx0, tx1, y0 + (y1 - y0) * 0.26, (1.0, 0.62),
               thickness=0.080, gap=0.22)
    else:
        _lines(d, s, tx0, tx1, y0 + (y1 - y0) * 0.17,
               (1.0, 1.0, 0.62), thickness=0.045, gap=0.150)


DESIGNS = {
    "card": design_card,
    "stack": design_stack,
    "calendar": design_calendar,
    "check": design_check,
    "stripe": design_stripe,
    "desktop": design_desktop,
    "pixel": design_pixel,
    "angled": design_angled,
    "tool": design_tool,
}


# Designs that draw their own ground. The rounded tile is the web-app
# idiom, and the second family exists to avoid it -- so they must not
# have one painted under them.
TILELESS = {"desktop", "pixel", "angled", "tool"}


def draw_icon(size, design=DEFAULT_DESIGN, accent=None):
    """One icon at `size` pixels, drawn big and brought down.

    `accent` is a CSS hex; the design functions read the module-level
    ACCENT, so it is rebound for the duration of the drawing and put
    back afterwards. Blunt, but it keeps every design function's
    signature about drawing rather than about plumbing.
    """
    global ACCENT, ACCENT_DEEP
    previous = (ACCENT, ACCENT_DEEP)
    if accent:
        ACCENT = _rgb(accent)
        ACCENT_DEEP = _deepen(ACCENT)
    try:
        return _draw_icon(size, design)
    finally:
        ACCENT, ACCENT_DEEP = previous


def _draw_icon(size, design):
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    if design not in TILELESS:
        pad, radius = _tile(ImageDraw.Draw(img), s)
        _depth(img, s, pad, radius)
    DESIGNS[design](ImageDraw.Draw(img), s, size, size <= 32)
    return img.resize((size, size), Image.LANCZOS)


def _row(images, ground, width, height):
    strip = Image.new("RGBA", (width, height), ground)
    x = 20
    for img in images:
        strip.paste(img, (x, (height - img.height) // 2), img)
        x += img.width + 20
    return strip


SHEET = []


def write_sheet():
    """All nine designs, every size, on both grounds — for choosing."""
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("segoeuib.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    label_w = 140
    rows = []
    for name in (SHEET or list(DESIGNS)):
        imgs = [draw_icon(n, name) for n in SIZES]
        w = label_w + sum(i.width for i in imgs) + 20 * (len(imgs) + 1)
        h = imgs[0].height + 36
        band = Image.new("RGBA", (w, h * 2), (22, 22, 34, 255))
        band.paste(_row(imgs, (30, 30, 47, 255), w - label_w, h), (label_w, 0))
        band.paste(_row(imgs, (242, 242, 247, 255), w - label_w, h),
                   (label_w, h))
        ImageDraw.Draw(band).text((18, h - 16), name, fill=(235, 235, 245),
                                  font=font)
        rows.append(band)
    width = max(r.width for r in rows)
    sheet = Image.new("RGBA", (width, sum(r.height + 14 for r in rows)),
                      (22, 22, 34, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 14
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    path = os.path.join(PREVIEW_DIR, "icon_designs%s.png"
                    % ("_" + "_".join(SHEET) if SHEET else ""))
    sheet.save(path)
    print("sheet  ->", path)


def write_every_accent(design=DEFAULT_DESIGN):
    """One .ico and one .png per accent the app can wear.

    One pair per distinct accent: two themes sharing an accent share an
    icon. The app asks by accent hex (``icon_<hex>.ico``), which is why
    the keys of accents_in_use() are the filenames. An accent no theme wears any more leaves its pair
    behind, and the build would ship it: check_contrast names both the
    pairs missing and the pairs left over.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    for accent, themes in sorted(accents_in_use().items()):
        images = [draw_icon(n, design, accent) for n in SIZES]
        stem = "icon_%s" % accent.lstrip("#")
        ico = os.path.join(OUT_DIR, stem + ".ico")
        images[0].save(ico, format="ICO",
                       sizes=[(n, n) for n in sorted(SIZES)])
        images[0].save(os.path.join(OUT_DIR, stem + ".png"))
        print("  %-9s -> %-20s (%s)"
              % (accent, os.path.basename(ico), ", ".join(sorted(themes))))
    # The unsuffixed pair stays as the default, for anything that asks
    # for "the icon" without knowing about themes -- the .exe stamp, and
    # the window before a theme has been read.
    images = [draw_icon(n, design, "#7c5cff") for n in SIZES]
    images[0].save(os.path.join(OUT_DIR, "icon.ico"), format="ICO",
                   sizes=[(n, n) for n in sorted(SIZES)])
    images[0].save(os.path.join(OUT_DIR, "icon_256.png"))
    print("  %-9s -> %s" % ("(default)", "icon.ico + icon_256.png"))


def main(argv):
    import guest  # the memory ceiling, before the themes are imported (tools/guest.py)
    guest.settle(heavy=False)
    os.makedirs(OUT_DIR, exist_ok=True)
    if "--all" in argv:
        print("one icon per accent:")
        write_every_accent()
        return 0
    if "--sheet" in argv:
        after = argv[argv.index("--sheet") + 1:]
        SHEET[:] = [a for a in after if a in DESIGNS]
        write_sheet()
        return 0

    design = DEFAULT_DESIGN
    if "--design" in argv:
        design = argv[argv.index("--design") + 1]
        if design not in DESIGNS:
            print("unknown design %r; have: %s" % (design, ", ".join(DESIGNS)))
            return 2

    images = [draw_icon(n, design) for n in SIZES]
    w = sum(i.width for i in images) + 20 * (len(images) + 1)
    h = images[0].height + 40
    preview = Image.new("RGBA", (w, h * 2), (30, 30, 47, 255))
    preview.paste(_row(images, (30, 30, 47, 255), w, h), (0, 0))
    preview.paste(_row(images, (242, 242, 247, 255), w, h), (0, h))
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    preview.save(os.path.join(PREVIEW_DIR, "icon_preview.png"))
    print("preview ->", os.path.join(PREVIEW_DIR, "icon_preview.png"))

    ico_path = os.path.join(OUT_DIR, "icon.ico")
    images[0].save(ico_path, format="ICO",
                   sizes=[(n, n) for n in sorted(SIZES)])
    print("icon   -> %s (%s, design=%s)"
          % (ico_path, ", ".join("%dx%d" % (n, n) for n in sorted(SIZES)),
             design))
    images[0].save(os.path.join(OUT_DIR, "icon_256.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
