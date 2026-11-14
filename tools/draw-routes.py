# SPDX-License-Identifier: MIT
# Draws the board's copper by hand: every track and via below is a fixed coordinate, so the
# result is the same on every run. Needs the unrouted board from tools/place-pcb.py (it refuses
# a board that already has tracks or zones). Coordinates are mm from the board's top-left corner.
#   "C:\Program Files\KiCad\10.0\bin\python.exe" tools/draw-routes.py [project dir, default: repo root]
# Then: kicad-cli pcb drc --schematic-parity --severity-all ...
# If the placement changes, the pad look-ups still follow the parts, but the waypoints do not:
# re-check every route near the moved part.
import math
import os
import sys

import pcbnew

NAME = "SNAP_Power_Controller"
ORIGIN = (100.0, 100.0)  # must match place-pcb.py
W, H, CHAMFER = 52.0, 29.0, 2.0
F, B = pcbnew.F_Cu, pcbnew.B_Cu
SIG, PWR = 0.25, 0.8
VIA, PVIA = (0.6, 0.3), (0.8, 0.4)  # (diameter, drill)
HOLES = [(4, 4), (W - 4, 4), (4, H - 4), (W - 4, H - 4)]
STITCH_PITCH = 3.0  # GND stitching via grid, mm
ZONE_CLEARANCE = 0.25

path = os.path.join(sys.argv[1] if len(sys.argv) > 1 else ".", NAME + ".kicad_pcb")
board = pcbnew.LoadBoard(path)
if len(board.GetTracks()) or len(board.Zones()):
    sys.exit("board already has tracks or zones: run tools/place-pcb.py first")
mm = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))
PADS = {(fp.GetReference(), p.GetNumber()): p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNumber()}
count = {"track": 0, "via": 0}


def P(ref, num):
    """Pad centre, board mm."""
    c = PADS[(ref, num)].GetPosition()
    return (pcbnew.ToMM(c.x) - ORIGIN[0], pcbnew.ToMM(c.y) - ORIGIN[1])


def net(name):
    n = board.FindNet(name)
    if n is None:
        sys.exit(f"no net {name}")
    return n


def track(name, pts, w=SIG, layer=F):
    """Polyline on one layer. Every segment must be horizontal, vertical or 45 degrees."""
    n = net(name)
    for a, b in zip(pts, pts[1:]):
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        if min(dx, dy) > 0.02 and abs(dx - dy) > 0.02:
            sys.exit(f"{name}: segment {a} -> {b} is not on a 45-degree direction")
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(n)
        board.Add(t)
        count["track"] += 1


def via(name, c, size=VIA):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(*c)); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(F, B)
    v.SetWidth(mm(size[0])); v.SetDrill(mm(size[1])); v.SetNet(net(name))
    board.Add(v)
    count["via"] += 1


def gnd_via(pad, c, w=0.4):
    """Short stub from a GND pad to its own via down to the plane."""
    track("GND", [pad, c], w)
    via("GND", c)


DX = 3.0  # the solar, charger and power-stage blocks sit 3 mm right of where they were first drawn


def X(pts):
    """Waypoints drawn for the 56.5 mm board, moved with their block."""
    return [(x + DX, y) for x, y in pts]


# ---------------------------------------------------------------- solar inputs
r10_1, r10_2 = P("R10", "1"), P("R10", "2")
j1_1, d5_2 = P("J1", "1"), P("D5", "2")
track("/PANEL1", [j1_1, (j1_1[0] + 0.45, 1.95), (r10_1[0], 1.95), r10_1], 0.4)
# down from R10, then 45 degrees into D5's anode pad
track("/PANEL1_D", [r10_2, (r10_2[0], d5_2[1] - (r10_2[0] - d5_2[0])), d5_2], 0.4)
for j, d in (("J2", "D6"), ("J3", "D7"), ("J4", "D8")):
    p, q = P(j, "1"), P(d, "2")
    jog = abs(q[1] - p[1])  # D6 and D7 are a little off their connector's row: finish with a 45-degree step
    track(f"Net-({d}-A)", [p, q] if jog < 1e-6 else [p, (q[0] - jog, p[1]), q], 0.6)
# PV bus down the diode cathodes, with a tee into the west edge of R7's PV pad
track("/PV", [P("D5", "1"), P("D8", "1")], 0.5)
track("/PV", [(P("D5", "1")[0], P("R7", "1")[1]), P("R7", "1")], 0.6)

# ---------------------------------------------------------------- buck power stage
# VIN: R7 -> C1 -> C5 in a straight line along the top, then down to Q1's source
track("/VIN", [P("R7", "2")] + X([(22.3, 3.938), (24.3, 3.938), (24.987, 4.625)]) + [P("C5", "1")]
      + X([(25.835, 4.625), (27.56, 6.35)]) + [P("Q1", "2")], PWR)
# switch node: Q1 drain to L1, and down to D2's cathode
track("Net-(D2-K)", [P("Q1", "3")] + X([(33.225, 5.4)]) + [P("L1", "1")], PWR)
track("Net-(D2-K)", [P("Q1", "3")] + X([(29.738, 6.6), (27.3, 9.038), (27.3, 10.9)]) + [P("D2", "1")], PWR)
# L1 -> R5 (charge-current shunt) -> C3
track("/CSP", [P("L1", "2")] + X([(38.375, 9.163)]) + [P("R5", "1")], PWR)
track("/VBAT", [P("R5", "2")] + X([(38.925, 12.7)]) + [P("C3", "1")], PWR)
# gate drive: up the west side of D2, one hop on B.Cu under the VIN track into Q1's gate
track("/DRV", [P("U1", "10")] + X([(25.6, 14.15), (25.15, 13.7), (25.15, 9.0), (26.3, 7.85), (26.3, 6.9)]))
via("/DRV", (29.3, 6.9))
track("/DRV", X([(26.3, 6.9), (26.3, 4.2), (26.6, 3.9)]), layer=B)
via("/DRV", (29.6, 3.9))
track("/DRV", X([(26.6, 3.9), (27.15, 4.45)]) + [P("Q1", "1")])

# ---------------------------------------------------------------- CN3791 and its parts
# VIN to C2 and, under the IC between its pin rows, to pin 9
track("/VIN", X([(24.0, 3.938), (24.0, 10.6), (23.075, 11.525)]) + [P("C2", "1")], 0.4)
track("/VIN", [P("C2", "1")] + X([(23.075, 12.7), (23.9, 13.525), (23.9, 15.1), (24.7, 15.9)]) + [P("U1", "9")])
# ...on to R3 (MPPT divider) with a hop on B.Cu under the charge-current sense pair
track("/VIN", [P("U1", "9"), (29.95, 15.9), (30.25, 15.6)])
via("/VIN", (30.25, 15.6))
track("/VIN", [(30.25, 15.6), (30.45, 15.4), (33.3, 15.4)], layer=B)
via("/VIN", (33.3, 15.4))
track("/VIN", [(33.3, 15.4), (33.3, 16.05), (32.775, 16.575), P("R3", "1")])
# ...and out under the IC, round the LEDs and JP1, to R1 (LED supply)
track("/VIN", X([(23.9, 15.1), (23.9, 19.9), (26.45, 22.45), (26.45, 26.45), (26.25, 26.65), (20.6, 26.65),
                 (20.175, 26.225)]) + [P("R1", "1")])
track("Net-(U1-VG)", [P("C2", "2")] + X([(21.525, 12.4), (21.25, 12.675)]) + [P("U1", "1")])
# charge-current sense: Kelvin pair from R5's pads straight into pins 8 and 7
# (0.2 mm wide: the pair squeezes between pin 8 and R3)
track("/CSP", [P("R5", "1")] + X([(34.838, 13.7), (34.538, 14.0), (29.894, 14.0), (26.994, 16.9)]) + [P("U1", "8")], 0.2)
track("/VBAT", [P("R5", "2")] + X([(37.762, 14.15), (37.462, 14.45), (30.08, 14.45), (26.63, 17.9)]) + [P("U1", "7")], 0.2)
# MPPT node: pin 6 and the R3/R4 junction, kept short
track("/MPPT", [P("R3", "2"), P("R4", "1")])
track("/MPPT", [P("U1", "6")] + X([(28.6, 18.9), (28.85, 19.15), (29.3, 19.15)]))
# compensation network
track("Net-(U1-COM)", [P("U1", "5")] + X([(20.2, 18.9), (19.65, 18.35), (19.65, 17.25), (18.975, 16.575)]) + [P("R2", "1")])
track("Net-(C4-Pad1)", [P("R2", "2"), P("C4", "1")])
# status LEDs: cathodes out under the IC, anodes joined below the LEDs and down to JP1
track("/~{DONE}", [P("U1", "4")] + X([(22.2, 17.9), (22.2, 19.9), (20.513, 21.587)]) + [P("D3", "1")])
track("/~{CHRG}", [P("U1", "3")] + X([(22.65, 16.9), (22.65, 20.3), (24.013, 21.663)]) + [P("D4", "1")])
track("Net-(D3-A)", [P("D3", "2")] + X([(22.088, 23.6), (22.388, 23.9), (25.288, 23.9), (25.588, 23.6)]) + [P("D4", "2")])
track("Net-(D3-A)", [(27.9, 23.9), P("JP1", "1")])
track("Net-(JP1-B)", [P("R1", "2"), (25.225, 25.4), P("JP1", "2")])

# ---------------------------------------------------------------- battery, load, switches
# VBAT from C3 up and over J7 to the two headers' right-hand pins
track("/VBAT", [P("C3", "1"), (44.75, 13.875), (44.75, 9.4), (45.15, 9.0), (49.54, 9.0), P("J7", "1"), P("J8", "1")], PWR)
# BATT+ from J7 down between the headers and west, over J6, into the top of R6
track("/BATT+", [P("J7", "2"), (47.0, 14.0), (45.8, 15.2), (37.4, 15.2), (36.6, 16.0), P("R6", "1")], PWR)
track("/VOUT", [P("J8", "2"), (46.6, 17.3), P("J6", "1")], PWR)
# R6 -> Q2 (reverse-battery FET) -> under J5 into its pin 1
track("/BAT_CELL", [P("R6", "2"), (36.6, 19.64), (35.05, 21.19), P("Q2", "2")], PWR)
track("Net-(J5-Pin_1)", [P("Q2", "3"), (36.0, 24.3), (36.65, 24.95), (41.75, 24.95), (42.4, 24.3), P("J5", "1")], PWR)

# ---------------------------------------------------------------- INA3221 and J9, left band
U = {n: P("U2", n) for n in map(str, range(1, 18))}
# ground: pin 3 into the exposed pad, one via in the middle of the pad
track("GND", [U["3"], (U["3"][0], 14.6)])
via("GND", U["17"])
# supply: C6 to VS; the VCC via beside C6 collects J9 pin 1 (B.Cu) and VPU (B.Cu, under U2)
VCC = (5.75, 12.7)
via("/VCC_MCU", VCC)
track("/VCC_MCU", [VCC, (6.25, 12.2), (6.9, 12.2)])
track("/VCC_MCU", [P("C6", "1"), (6.9, 12.6), (7.025, 12.725), U["4"]])
track("/VCC_MCU", [P("J9", "1"), (5.0, 17.375), (5.75, 16.625), VCC], layer=B)
track("/VCC_MCU", [U["16"], (10.075, 14.525), (10.7, 13.9)])
via("/VCC_MCU", (10.7, 13.9))
track("/VCC_MCU", [(10.7, 13.9), (6.95, 13.9), VCC], layer=B)
# pull-ups: VCC pads joined above the resistors and down to the VCC via
track("/VCC_MCU", [P("R9", "1"), (3.025, 8.0), (3.275, 7.75), (5.875, 7.75), (6.125, 8.0), P("R8", "1"),
                   (6.125, 9.3), (5.6, 9.825), (5.6, 12.55), VCC])
# I2C: A0 and SCL straight across to J9; SDA (pin 7) reaches J9 pin 4 with a hop on B.Cu
j9_3, j9_4 = P("J9", "3"), P("J9", "4")
track("/SDA", [U["5"], (4.6, 14.525), (3.7, 13.625), j9_4])
track("/SCL", [U["6"], (4.3, 15.175), (4.0, 14.875), j9_3])
track("/SDA", [U["7"], (4.9, 15.825)])
via("/SDA", (4.9, 15.825))
track("/SDA", [(4.9, 15.825), (4.9, 14.0), (4.525, 13.625), j9_4], layer=B)
track("/SDA", [j9_4, (3.305, 11.5), (4.475, 10.33), P("R8", "2")])
track("/SCL", [j9_3, (2.0, 14.875), (1.6, 14.475), (1.6, 9.3), (1.375, 9.075), P("R9", "2")])
# channel 3 (R10, panel 1): PANEL1 over the top of J1, PANEL1_D under it, both down into U2
track("/PANEL1", [r10_1, (19.9, r10_1[1]), (20.15, r10_1[1] - 0.25), (20.15, 1.05), (19.9, 0.8), (8.575, 0.8),
                  (8.325, 1.05), U["2"]])
track("/PANEL1_D", [r10_2, (16.75, r10_2[1]), (16.1, r10_2[1] + 0.65), (9.2, r10_2[1] + 0.65),
                    (8.975, r10_2[1] + 0.875), U["1"]])
# channel 2 (R7, all panels): one hop each on B.Cu under the PV bus, then between J2 and J3
r7_1 = P("R7", "1")
track("/PV", [(21.3, r7_1[1]), (21.3, 9.95), (20.75, 10.5)])
track("/VIN", [(22.2, 4.2), (22.2, 4.6), (22.55, 4.95), (23.75, 4.95), (23.9, 5.1), (23.9, 10.2), (22.7, 11.4),
               (20.75, 11.4)])
for n, y in (("/PV", 10.5), ("/VIN", 11.4)):
    via(n, (20.75, y)); via(n, (19.05, y))  # either side of the PV bus at x = 19.9
    track(n, [(20.75, y), (19.05, y)], layer=B)
track("/PV", [(19.05, 10.5), (15.045, 10.5), (10.37, 15.175), U["15"]])
track("/VIN", [(19.05, 11.4), (14.795, 11.4), (10.37, 15.825), U["14"]])
# channel 1 (R6, battery): the pair runs down from U2, along the bottom edge, up west of R6
track("/BATT+", [U["12"], (8.975, 26.85), (9.425, 27.3), (33.45, 27.3), (33.9, 26.85), (33.9, 16.338),
                 (34.1, 16.138), P("R6", "1")])
track("/BAT_CELL", [U["11"], (8.325, 27.3), (8.775, 27.75), (33.9, 27.75), (34.35, 27.3), (34.35, 19.262),
                    (34.55, 19.062), P("R6", "2")])

# ---------------------------------------------------------------- GND vias for surface-mount pads
gnd_via(P("C1", "2"), (25.3, 8.15))
gnd_via(P("C5", "2"), (28.3, 7.35))
gnd_via((33.3, 10.4), (33.3, 9.2)); gnd_via((34.3, 10.4), (34.3, 9.2))  # D2 anode
gnd_via(P("C3", "2"), (43.1, 9.75))
gnd_via(P("U1", "2"), (22.9, 15.9), SIG)
gnd_via(P("C4", "2"), (21.5, 23.3))
track("GND", [P("R4", "2"), (33.0, 22.425)], 0.4); via("GND", (33.0, 22.425))
gnd_via(P("C6", "2"), (7.65, P("C6", "2")[1]))
gnd_via(P("Q2", "1"), (37.9, P("Q2", "1")[1]))

# ---------------------------------------------------------------- pours
gnd = net("GND")
for fp in board.GetFootprints():
    if fp.GetReference() in {f"J{i}" for i in range(1, 10)}:
        for p in fp.Pads():
            if p.GetNetname() == "GND":  # connector GND pins: solid, they carry panel/battery current
                p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


def add_zone(layer, connection):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(gnd)
    c = CHAMFER
    for x, y in [(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)]:
        z.AppendCorner(V(x, y), -1)
    z.SetLocalClearance(mm(ZONE_CLEARANCE))
    z.SetMinThickness(mm(0.25))
    z.SetPadConnection(connection)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(0)
    board.Add(z)
    return z


zb = add_zone(B, pcbnew.ZONE_CONNECTION_THERMAL)
zf = add_zone(F, pcbnew.ZONE_CONNECTION_THT_THERMAL)
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())

# Stitching: a GND via wherever a grid point sits inside both pours with room for the via,
# so every piece of the top pour is tied to the bottom plane.
fills = [zf.GetFilledPolysList(F), zb.GetFilledPolysList(B)]
ring = [(0.55 * math.cos(a * math.pi / 8), 0.55 * math.sin(a * math.pi / 8)) for a in range(16)] + [(0, 0)]
drills = [(pcbnew.ToMM(t.GetPosition().x) - ORIGIN[0], pcbnew.ToMM(t.GetPosition().y) - ORIGIN[1])
          for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
drills += [P(*k) for k, p in PADS.items() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
pad_boxes = []
for p in PADS.values():
    bb = p.GetBoundingBox()
    bb.Inflate(mm(0.45))
    pad_boxes.append(bb)
stitched = 0
y = 1.5
while y < H - 1:
    x = 1.5
    while x < W - 1:
        clear = all(math.hypot(x - hx, y - hy) > 3.4 for hx, hy in HOLES) and \
            all(math.hypot(x - hx, y - hy) > 1.2 for hx, hy in drills)
        clear = clear and not any(b.Contains(V(x, y)) for b in pad_boxes)  # no via-in-pad
        if clear and all(f.Contains(V(x + dx, y + dy)) for f in fills for dx, dy in ring):
            via("GND", (x, y))
            drills.append((x, y))
            stitched += 1
        x += STITCH_PITCH
    y += STITCH_PITCH
filler.Fill(board.Zones())

pcbnew.SaveBoard(path, board)
print(f"{count['track']} track segments, {count['via']} vias ({stitched} of them GND stitching), 2 GND pours")
