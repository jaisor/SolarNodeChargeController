# Draws docs/images/wiring-diagram.png: the board render with a callout per connector and the
# parts of a SNAP-style solar mesh node wired to them, in the style of the SNAP component map.
# Run with KiCad's Python (has Pillow + numpy) from the repo root, after refreshing pcb-top.png:
#   "C:\Program Files\KiCad\10.0\bin\python.exe" tools/make-diagram.py
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 2000, 1180
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

BOARD_W_MM, BOARD_H_MM = 56.5, 29.0
# Connector body centres in board mm (from tools/place-pcb.py PLACEMENT)
CONN = {
    "J1": (10.7, 2.85), "J2": (10.7, 9.15), "J3": (10.7, 15.45), "J4": (10.7, 21.75),
    "SW3": (3.75, 14.5),
    "J7": (45.8, 2.85), "J8": (45.8, 9.15), "J5": (45.8, 15.45), "J6": (45.8, 21.75),
    "J9": (52.75, 14.5),
}

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Title, in the style of the SNAP component map
d.text((70, 38), "SOLAR NODE  //  CHARGE MODULE", font=title_font, fill=INK)
d.line((70, 112, 980, 112), fill=CYAN, width=4)
d.text((70, 124), "v1.0 · CN3791 MPPT · INA219 · 4 × Micro JST 1.25 solar in · drop-in for SNAP v1.2",
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


# Left side: solar panels -> J1..J4, and the INA219 selector switch
panel(50, 250, 190, 104, "5V 200mA · 110×60mm")
panel(50, 430, 190, 104, "5V 200mA · 110×60mm")
solar_box = callout("J2", (520, 600), YELLOW, "SOLAR IN  J1–J4", "up to 4 × 5V panels", "left")
callout("J1", (520, 250 + 20), YELLOW, "Solar_5V", "own 1N5819WS per input", "left")
for py in (302, 482):
    wire([(240, py), (270, py), (270, 650), (solar_box[0], 650)], RED, 4)
callout("SW3", (520, 820), MAGENTA, "SW3  SOLAR / BATT", "INA219 measures panel or cell", "left")

# Right side: switches, battery, node
sw_batt = callout("J7", (1480, 200), ORANGE, "SW_BATT  J7", "battery cut-off switch", "right")
sw_load = callout("J8", (1480, 300), ORANGE, "SW_LOAD  J8", "node power switch", "right")
batt = callout("J5", (1480, 420), GREEN, "BATT  J5", "18650 cell, 0.8 A charge", "right")
i2c = callout("J9", (1480, 640), CYAN, "I2C  J9", "INA219 @ 0x40 → node", "right")
vout = callout("J6", (1480, 750), RED, "VOUT  J6", "battery power to the node", "right")
switch(1770, 201, "")
switch(1770, 301, "")
wire([(sw_batt[2], 233), (1770, 233)], ORANGE, 4)
wire([(sw_load[2], 333), (1770, 333)], ORANGE, 4)
cell18650(1500, 525)
wire([(1615, batt[3]), (1615, 525)], GREEN, 4)
node(1480, 900)
wire([(i2c[2], 673), (1768, 673), (1768, 900)], CYAN, 5)
wire([(1560, vout[3]), (1560, 900)], RED, 5)

d.text((70, 1130), "Replaces the CN3158 module, discrete Schottky diodes and loose wiring of a SNAP v1.2 build.",
       font=small, fill=DIM)
d.text((W - 300, 1130), "JAISORGADGETS", font=box_title, fill=CYAN)
img.save("docs/images/wiring-diagram.png", optimize=True)
print("wrote docs/images/wiring-diagram.png", img.size)
