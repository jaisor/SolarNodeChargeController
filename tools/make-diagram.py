# SPDX-License-Identifier: MIT
# Draws docs/images/wiring-diagram.png: the board render with a callout per connector and the
# parts of a SNAP-style solar mesh node wired to them, in the style of the SNAP component map.
# Run with KiCad's Python (has Pillow + numpy) from the repo root, after refreshing pcb-top.png:
#   "C:\Program Files\KiCad\10.0\bin\python.exe" tools/make-diagram.py
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 2000, 1580
BG = (13, 17, 23)
INK = (230, 237, 243)
DIM = (139, 148, 158)
CYAN, MAGENTA, YELLOW = (0, 229, 255), (255, 64, 200), (255, 214, 0)
ORANGE, GREEN, RED, BLUE = (255, 150, 40), (63, 230, 100), (255, 82, 82), (90, 160, 255)

FONTS = "C:/Windows/Fonts/"
title_font = ImageFont.truetype(FONTS + "seguibl.ttf", 58)
sub_font = ImageFont.truetype(FONTS + "consola.ttf", 22)
box_title = ImageFont.truetype(FONTS + "consolab.ttf", 23)
box_sub = ImageFont.truetype(FONTS + "consola.ttf", 17)
small = ImageFont.truetype(FONTS + "consola.ttf", 16)

BOARD_W_MM, BOARD_H_MM = 52.0, 29.0
# Mechanical data for the dimension drawing (W, H, CHAMFER, HOLE_INSET in tools/place-pcb.py)
CHAMFER_MM, HOLE_INSET_MM, HOLE_DIA_MM = 2.0, 4.0, 3.2
# Connector body centres in board mm (from tools/place-pcb.py PLACEMENT)
CONN = {
    "J1": (13.25, 2.85), "J2": (13.25, 9.35), "J3": (13.4, 15.45), "J4": (13.25, 21.75),
    "J7": (48.27, 10.8), "J8": (48.27, 17.7), "J6": (41.8, 17.3), "J5": (41.8, 23.5),
    "J9": (3.3, 15.5),
}

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Title, in the style of the SNAP component map
d.text((70, 38), "SOLAR NODE  //  CHARGE MODULE", font=title_font, fill=INK)
d.line((70, 112, 980, 112), fill=CYAN, width=4)
d.text((70, 124), "v1.1 · CN3791 MPPT · INA3221 · 4 × Micro JST 1.25 solar in · 2.54mm switch headers · drop-in for SNAP v1.2",
       font=sub_font, fill=MAGENTA)

# Board render: crop to the board itself (non-transparent, non-shadow pixels)
render = Image.open("docs/images/pcb-top.png").convert("RGBA")
a = np.asarray(render)
board_px = (a[:, :, 3] > 200) & (a[:, :, 1] > a[:, :, 0] + 8)  # opaque and green-dominant
ys, xs = np.nonzero(board_px)
board = render.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
BX0, BY0, BW = 560, 390, 860
BH = round(BW * board.height / board.width)
board = board.resize((BW, BH), Image.LANCZOS)
img.paste(board, (BX0, BY0), board)
d.rounded_rectangle((BX0 - 14, BY0 - 14, BX0 + BW + 14, BY0 + BH + 14), radius=10, outline=(48, 54, 61), width=2)


def at(ref):
    x, y = CONN[ref]
    return BX0 + x / BOARD_W_MM * BW, BY0 + y / BOARD_H_MM * BH


def callout(ref, box_xy, colour, title, sub, side):
    """Dot on the connector, leader line, and a neon-outlined label box (left or right side)."""
    cx, cy = at(ref)
    bx, by = box_xy
    tw = max(d.textlength(title, font=box_title), d.textlength(sub, font=box_sub))
    bw, bh = tw + 34, 66
    x0 = bx if side == "right" else bx - bw
    anchor = (x0, by + bh / 2) if side == "right" else (x0 + bw, by + bh / 2)
    d.line((cx, cy, anchor[0], anchor[1]), fill=colour, width=3)
    d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), outline=colour, width=3)
    d.rectangle((x0, by, x0 + bw, by + bh), fill=(18, 23, 31), outline=colour, width=2)
    d.rectangle((x0, by, x0 + 6, by + bh), fill=colour)
    d.text((x0 + 18, by + 8), title, font=box_title, fill=INK)
    d.text((x0 + 18, by + 39), sub, font=box_sub, fill=colour)
    return (x0, by, x0 + bw, by + bh)


def wire(points, colour, width=5):
    d.line(points, fill=colour, width=width, joint="curve")


def panel(x, y, w, h, label):
    """Small polycrystalline panel: dark blue cells on a silver grid."""
    d.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=(26, 44, 92), outline=(170, 180, 195), width=3)
    for i in range(1, 6):
        gx = x + i * w / 6
        d.line((gx, y + 4, gx, y + h - 4), fill=(120, 140, 175), width=1)
    d.line((x + 4, y + h / 2, x + w - 4, y + h / 2), fill=(120, 140, 175), width=1)
    d.line((x + w * 0.5, y + 6, x + w * 0.5, y + h - 6), fill=(200, 205, 215), width=2)
    d.text((x, y + h + 8), label, font=small, fill=DIM)


def switch(x, y, label):
    """Latching panel-mount push switch, seen from the front."""
    d.ellipse((x, y, x + 64, y + 64), fill=(40, 44, 52), outline=(180, 186, 196), width=4)
    d.ellipse((x + 16, y + 16, x + 48, y + 48), fill=(70, 76, 88), outline=ORANGE, width=3)
    d.text((x + 80, y + 20), label, font=small, fill=DIM)


def jumper_cap(x, y):
    """2.54mm jumper cap seen from above, bridging the two header pins."""
    d.rounded_rectangle((x, y, x + 46, y + 24), radius=4, fill=(30, 30, 34), outline=(150, 156, 166), width=2)
    for px in (x + 12, x + 34):
        d.rectangle((px - 4, y + 8, px + 4, y + 16), fill=(212, 175, 55))


def cell18650(x, y):
    """18650 Li-ion cell lying on its side."""
    d.rounded_rectangle((x, y, x + 230, y + 66), radius=14, fill=(46, 160, 92), outline=(150, 230, 170), width=3)
    d.rectangle((x + 230, y + 18, x + 242, y + 48), fill=(190, 196, 206))
    d.text((x + 22, y + 10), "18650", font=box_title, fill=(10, 30, 18))
    d.text((x + 22, y + 38), "Li-ion 1S · 3.0–4.2 V", font=box_sub, fill=(10, 30, 18))


def node(x, y):
    """Mesh radio node: XIAO nRF52840 on a Wio-SX1262 LoRa board."""
    d.rounded_rectangle((x, y, x + 300, y + 190), radius=10, fill=(20, 40, 70), outline=BLUE, width=3)
    d.rounded_rectangle((x + 24, y + 26, x + 150, y + 120), radius=6, fill=(25, 25, 30), outline=(200, 200, 210), width=2)
    d.text((x + 34, y + 36), "XIAO", font=box_title, fill=INK)
    d.text((x + 34, y + 66), "nRF52840", font=box_sub, fill=DIM)
    d.rounded_rectangle((x + 165, y + 26, x + 280, y + 120), radius=6, fill=(30, 60, 40), outline=(160, 210, 170), width=2)
    d.text((x + 175, y + 36), "Wio-", font=box_title, fill=INK)
    d.text((x + 175, y + 66), "SX1262", font=box_sub, fill=DIM)
    d.line((x + 225, y + 26, x + 225, y - 60), fill=(60, 60, 66), width=10)  # antenna
    d.text((x + 24, y + 132), "Meshtastic / MeshCore", font=box_sub, fill=CYAN)
    d.text((x + 24, y + 156), "BAT pads · I2C SDA/SCL", font=box_sub, fill=DIM)


# Left side: solar panels -> J1..J4
panel(50, 250, 190, 104, "5V 200mA · 110×60mm")
panel(50, 430, 190, 104, "5V 200mA · 110×60mm")
solar_box = callout("J2", (520, 600), YELLOW, "SOLAR IN  J1–J4", "up to 4 × 5V panels", "left")
callout("J1", (520, 250 + 20), YELLOW, "Solar_5V", "own 1N5819W · 0.5A max", "left")
for py in (302, 482):
    wire([(240, py), (270, py), (270, 650), (solar_box[0], 650)], RED, 4)

# Right side: switches, battery, node
sw_batt = callout("J7", (1480, 200), ORANGE, "SW_BATT  J7", "2.54mm header · battery cut-off", "right")
sw_load = callout("J8", (1480, 300), ORANGE, "SW_LOAD  J8", "2.54mm header · node power", "right")
vout = callout("J6", (1480, 420), RED, "VOUT  J6", "battery power to the node", "right")
batt = callout("J5", (1480, 600), GREEN, "BATT  J5", "18650 cell, 0.8 A charge", "right")
i2c = callout("J9", (520, 820), CYAN, "I2C  J9", "INA3221 @ 0x42 → node", "left")
SWX = 1850  # switch column, right of the widest callout box
switch(SWX, 201, "")
switch(SWX, 301, "")
for text, ty in (("panel-mount SPST ≥1A", 172), ("or a jumper cap", 404)):
    d.text((SWX + 32 - d.textlength(text, font=small) / 2, ty), text, font=small, fill=DIM)
jumper_cap(SWX + 9, 374)
wire([(sw_batt[2], 233), (SWX, 233)], ORANGE, 4)
wire([(sw_load[2], 333), (SWX, 333)], ORANGE, 4)
cell18650(1500, 705)
wire([(1615, batt[3]), (1615, 705)], GREEN, 4)
node(1480, 900)
wire([(i2c[0] + 60, i2c[3]), (i2c[0] + 60, 1010), (1480, 1010)], CYAN, 5)
wire([(vout[2], 453), (1800, 453), (1800, 960), (1780, 960)], RED, 5)

# ---------- Board dimensions: outline drawing, to scale ----------
DY = 1120  # top of the dimension strip
d.line((70, DY, W - 70, DY), fill=(48, 54, 61), width=2)
d.text((70, DY + 28), "BOARD DIMENSIONS", font=box_title, fill=INK)
d.text((70, DY + 60), "all in mm · top view", font=box_sub, fill=CYAN)
S = 8.0  # px per mm
OX, OY = 600, DY + 95
bw, bh, c = BOARD_W_MM * S, BOARD_H_MM * S, CHAMFER_MM * S
d.polygon([(OX + c, OY), (OX + bw - c, OY), (OX + bw, OY + c), (OX + bw, OY + bh - c),
           (OX + bw - c, OY + bh), (OX + c, OY + bh), (OX, OY + bh - c), (OX, OY + c)],
          fill=(24, 44, 30), outline=INK, width=3)
hi, hr = HOLE_INSET_MM * S, HOLE_DIA_MM * S / 2
holes = [(OX + hi, OY + hi), (OX + bw - hi, OY + hi), (OX + hi, OY + bh - hi), (OX + bw - hi, OY + bh - hi)]
for hx, hy in holes:
    d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=BG, outline=INK, width=2)
    d.line((hx - hr - 5, hy, hx + hr + 5, hy), fill=DIM, width=1)
    d.line((hx, hy - hr - 5, hx, hy + hr + 5), fill=DIM, width=1)


def dim_h(x0, x1, y, from_y, text, colour):
    """Horizontal dimension at height y, with extension lines from from_y."""
    for x in (x0, x1):
        d.line((x, from_y, x, y + (6 if y > from_y else -6)), fill=colour, width=1)
        d.line((x - 5, y + 5, x + 5, y - 5), fill=colour, width=2)
    d.line((x0, y, x1, y), fill=colour, width=2)
    tw = d.textlength(text, font=box_sub)
    tx, ty = (x0 + x1) / 2 - tw / 2, y - 9
    d.rectangle((tx - 6, ty - 2, tx + tw + 6, ty + 20), fill=BG)
    d.text((tx, ty), text, font=box_sub, fill=colour)


def dim_v(y0, y1, x, from_x, text, colour):
    """Vertical dimension at x, with extension lines from from_x; the text sits on the outer side."""
    for y in (y0, y1):
        d.line((from_x, y, x + (6 if x > from_x else -6), y), fill=colour, width=1)
        d.line((x - 5, y + 5, x + 5, y - 5), fill=colour, width=2)
    d.line((x, y0, x, y1), fill=colour, width=2)
    tw = d.textlength(text, font=box_sub)
    tx = x + 10 if x > from_x else x - 10 - tw
    d.text((tx, (y0 + y1) / 2 - 9), text, font=box_sub, fill=colour)


dim_h(OX, OX + bw, OY - 34, OY, "52", INK)                                    # board width
dim_h(holes[2][0], holes[3][0], OY + bh + 34, holes[2][1], "44", YELLOW)      # hole centres, across
dim_v(OY, OY + bh, OX - 34, OX, "29", INK)                                    # board height
dim_v(holes[1][1], holes[3][1], OX + bw + 34, holes[1][0], "21", YELLOW)      # hole centres, down
# Hole callout, from the top-right hole
lx, ly = OX + bw + 150, OY + 6
d.line((holes[1][0] + hr * 0.7, holes[1][1] - hr * 0.7, lx - 12, ly + 12), fill=YELLOW, width=2)
NX = lx
for i, (text, colour) in enumerate((
        ("4 × Ø3.2 mounting holes for M3 screws, not plated", YELLOW),
        ("hole centres 4 from each edge · 44 × 21 apart", YELLOW),
        ("", INK),
        ("Outline 52 × 29, four 2 × 45° corner chamfers", INK),
        ("PCB 1.6 thick, 2 layers · parts on the top side only", INK),
        ("Solder pins of the through-hole connectors stick out the back", DIM))):
    d.text((NX, ly + i * 30), text, font=box_sub, fill=colour)

d.text((70, H - 50), "Replaces the CN3158 module, discrete Schottky diodes and loose wiring of a SNAP v1.2 build.",
       font=small, fill=DIM)
d.text((W - 300, H - 50), "JAISORGADGETS", font=box_title, fill=CYAN)
img.save("docs/images/wiring-diagram.png", optimize=True)
print("wrote docs/images/wiring-diagram.png", img.size)
