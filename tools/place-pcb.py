# SPDX-License-Identifier: MIT
# Builds the draft PCB: footprints from the schematic netlist, placed by hand-tuned
# coordinates, nets assigned, reference labels auto-placed clear of everything, M3 holes
# in the corners and a chamfered Edge.Cuts outline. No tracks. Run with KiCad's Python:
#   "C:\Program Files\KiCad\10.0\bin\python.exe" tools/place-pcb.py <netlist.xml> [project dir, default: repo root]
# Netlist: kicad-cli sch export netlist --format kicadxml -o net.xml SNAP_Power_Controller.kicad_sch
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

FPDIR = "C:/Program Files/KiCad/10.0/share/kicad/footprints"
NAME = "SNAP_Power_Controller"
ORIGIN = (100.0, 100.0)  # board top-left in the editor, mm
W, H = 52.0, 29.0  # board size, mm
CHAMFER = 2.0  # 45-degree corner chamfer, mm
HOLE_INSET = 4.0  # M3 hole centre distance from each edge, mm
EDGE_CLEAR = 0.6  # courtyard/label to board edge, mm
LABEL_GAP = 0.35  # label to its own courtyard, mm (must exceed the 0.25 mm of check margins)

# ref: (x, y, rotation[, flags]) in mm relative to the board's top-left corner. Position is the
# footprint origin, or the courtyard centre with flag "c". Flag "b" flips the part to the back.
# Left band: M3 holes. Then solar inputs, the CN3791 buck stage and the INA3221, the
# battery/load/switch connectors, and the right band: M3 holes + I2C connector.
PLACEMENT = {
    "H1": (HOLE_INSET, HOLE_INSET, 0, "c"),
    "H2": (W - HOLE_INSET, HOLE_INSET, 0, "c"),
    "H3": (HOLE_INSET, H - HOLE_INSET, 0, "c"),
    "H4": (W - HOLE_INSET, H - HOLE_INSET, 0, "c"),
    # Left band, between the holes: I2C connector at the edge, INA3221 beside it. U2 is turned so
    # I2C faces J9, channel 3 comes in from the top, channel 2 from the right, channel 1 from below.
    "J9": (2.85, 15.5, 90, "c"),
    "U2": (8.0, 15.5, 270),
    "C6": (6.9, 11.1, 90),   # pad 1 (VCC) down, by VS
    "R9": (2.2, 8.7, 180),   # pull-ups above J9: SCL / SDA pads on the left, VCC pads on the right
    "R8": (5.3, 8.7, 180),
    # Solar inputs: connector pin 1 faces its diode's anode; cathodes line up on the PV bus.
    # Panel 1 runs through R10 (INA3221 channel 3 shunt, 0603) in D5's place, low enough for its
    # label above it; D5 drops below it, its cathode still on the PV bus line at x = 19.9.
    # The diodes are SOD-123 (4.7 mm courtyard): they fill the strip between the connectors'
    # courtyards (15.88) and R7's (20.62), which is why J1-J4 sit at 13.84 and not 14.29.
    # D6 is 0.35 mm lower so D5's label fits above it; J2 only 0.2 mm, or its own label would
    # not fit above J3. J3 can only move as far as U2's
    # courtyard allows, so D7 sits further right and 0.3 mm higher, clear of R2's courtyard.
    "J1": (13.84, 2.4, 180), "R10": (18.45, 3.0, 180), "D5": (18.25, 4.95, 180),
    "J2": (13.84, 8.9, 180), "D6": (18.25, 9.05, 180),
    "J3": (13.99, 15.0, 180), "D7": (18.4, 14.7, 180),
    "J4": (13.84, 21.3, 180), "D8": (18.25, 21.3, 180),
    # Solar shunt and input caps next to the P-FET (short hot loop: C1 -> Q1 -> D2).
    "R7": (21.8, 5.4, 90),
    "C1": (25.3, 5.4, 270),
    "C5": (28.3, 5.4, 270),
    "Q1": (31.8, 5.4, 0),
    "D2": (31.8, 10.9, 0),
    "L1": (39.3, 6.4, 0),
    "R5": (39.3, 12.7, 0),
    "C3": (43.1, 12.4, 90),
    # CN3791 and its support parts
    "U1": (26.8, 16.9, 0),
    "C2": (25.3, 11.9, 180),
    "R2": (21.5, 17.4, 270),
    "C4": (21.5, 21.4, 270),
    "R3": (32.3, 17.4, 270),
    "R4": (32.3, 20.9, 270),
    "D4": (27.8, 22.9, 0),
    "D3": (24.3, 22.9, 0),
    "R1": (24.0, 25.8, 0),
    # LED supply solder jumper, right of R1 (pad 2 to R1, pad 1 up to the LED anode track)
    "JP1": (27.25, 25.4, 180),
    # Battery side, under L1: shunt R6 (BATT+ pad up) and the reverse-battery P-FET Q2 below it,
    # then the battery (J5) and VOUT (J6) connectors, pin 1 on the right
    "R6": (36.6, 17.6, 270),
    "Q2": (36.0, 22.3, 270),
    "J6": (42.4, 17.3, 180),
    "J5": (42.4, 23.5, 180),
    # Right band, between the holes: the two switch headers, pin 1 (VBAT) on the right
    "J7": (49.54, 10.8, 270),
    "J8": (49.54, 17.7, 270),
}

# Function labels on F.Silkscreen, vertical, just left of each right-column connector.
FUNCTION_LABELS = {"J5": "BATT", "J6": "VOUT"}
# Function labels for the switch headers: horizontal, above each one (no room beside them)
TOP_LABELS = {"J7": "SW_BATT", "J8": "SW_LOAD"}
FUNCTION_TEXT = 0.8  # mm
# Right edge of a label, mm, where the default (courtyard minus 0.35 mm) would hit C3. The header
# courtyards are wider than their silkscreen outlines, so these labels sit inside them.
FUNCTION_LABEL_RIGHT = {}
SOLAR_LABEL = "Solar_5V"  # one label for J1-J4, with a bracket along their left side
SOLAR_BRACKET_X = 10.75
# Back label, mirrored on B.Silkscreen: module ID, then ratings and a disclaimer. (text, height mm)
# per line, None for a gap. Centred on BACK_X, the middle of the strip between the solder pads of
# J1-J4 and J5/J6, and centred top to bottom. Limits: 20 V is set by C1/C5 (25 V) and the CN3791's
# MPPT pin (6.5 V max through R3/R4); 0.5 A per input is about 0.2 W in a 1N5819W (SOD-123); 1 A is the
# PicoBlade contact rating at J5/J6.
BACK_TEXT = [
    ("SNAP Power Controller v1.1", 1.2),
    ("by JaisorGadgets - Nov. 14, 2026", 1.0),
    None,
    ("CHECK POLARITY BEFORE USE", 1.0),
    ("BATTERY: 1S LI-ION 4.2V ONLY", 1.0),
    ("SOLAR: 5-6V PANELS, 20V MAX,", 1.0),
    ("0.5A MAX PER INPUT", 1.0),
    ("LOAD (VOUT): 1A MAX", 1.0),
    None,
    ("PROVIDED AS IS. NO WARRANTY.", 1.0),
    ("USE AT YOUR OWN RISK.", 1.0),
    ("LIABILITY LIMITED TO", 1.0),
    ("THE PURCHASE PRICE.", 1.0),
]
BACK_X = 28.0  # mm
BACK_LINE_GAP = 0.8  # between lines, added to the text height
BACK_BLOCK_GAP = 0.7  # extra, for a None entry
# + and - on F.Silkscreen under each power connector, either side of its reference, on the side of
# the matching pad: GND pad "-", the other "+".
POLARITY_REFS = ("J1", "J2", "J3", "J4", "J5", "J6")
POLARITY_TEXT = 1.0  # mm
POLARITY_OFFSET = 1.75  # sign centre from the connector centre, mm
# I2C connector J9: front label below it, pin names on B.Silkscreen beside each pad
I2C_LABEL = "I2C"
I2C_PINS = {"1": "VCC", "2": "GND", "3": "SCL", "4": "SDA"}  # red, black, yellow, white cable
I2C_PIN_TEXT = 0.8  # mm; the pads are on a 1.25 mm pitch
# Back-side parts: reference beside the upper pad and this label beside the lower pad, both on
# B.Silkscreen right of the courtyard. They are left out of the front label placement. (Empty since
# JP1 moved to the top; kept for parts placed with the "b" flag.)
BACK_LABELS = {}

# Label side preference per reference (N/S/E/W); anything unlisted tries N, S, E, W.
# Connectors and the solar diodes label underneath so each label reads with its own part.
LABEL_SIDES = {r: "SN" for r in ("J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "D5", "D6", "D7", "D8", "R5")}
LABEL_SIDES.update({"U2": "WNSE", "J9": "NS"})


def mm(v):
    return pcbnew.FromMM(v)


def courtyard(fp):
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    return cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)


def inflate(bb, d):
    b = pcbnew.BOX2I(bb.GetOrigin(), bb.GetSize())
    b.Inflate(mm(d))
    return b


def inside_board(bb):
    return (bb.GetLeft() >= mm(EDGE_CLEAR) and bb.GetTop() >= mm(EDGE_CLEAR)
            and bb.GetRight() <= mm(W - EDGE_CLEAR) and bb.GetBottom() <= mm(H - EDGE_CLEAR))


def place_labels(fps, boxes, extra_obstacles):
    """Put each visible reference beside its footprint, on the first side (then nudged
    along that side) where it clears every courtyard, every other label and the edge."""
    obstacles = [inflate(b, 0.15) for r, b in boxes.items() if not fps[r].IsFlipped()]
    obstacles += [inflate(b, 0.3) for b in extra_obstacles]
    failed = []
    for ref in sorted(fps, key=lambda r: -boxes[r].GetArea()):
        field = fps[ref].Reference()
        if not field.IsVisible() or fps[ref].IsFlipped():
            continue
        default_pos = field.GetPosition()
        field.SetTextAngleDegrees(0)
        field.SetKeepUpright(True)
        # The stroke outline, not GetBoundingBox(), which pads in a full line height.
        ink = lambda: field.GetEffectiveTextShape().BBox()
        tb = ink()
        w, h = pcbnew.ToMM(tb.GetWidth()), pcbnew.ToMM(tb.GetHeight())
        cb = boxes[ref]
        cx, cy = pcbnew.ToMM(cb.Centre().x), pcbnew.ToMM(cb.Centre().y)
        l, r, t, b = (pcbnew.ToMM(v) for v in (cb.GetLeft(), cb.GetRight(), cb.GetTop(), cb.GetBottom()))
        sides = {
            "N": (cx, t - LABEL_GAP - h / 2, (1, 0)),
            "S": (cx, b + LABEL_GAP + h / 2, (1, 0)),
            "E": (r + LABEL_GAP + w / 2, cy, (0, 1)),
            "W": (l - LABEL_GAP - w / 2, cy, (0, 1)),
        }
        done = False
        for nudge in [0] + [s * k * 0.25 for k in range(1, 11) for s in (1, -1)]:
            for side in LABEL_SIDES.get(ref, "NSEW"):
                x, y, (dx, dy) = sides[side]
                field.SetPosition(pcbnew.VECTOR2I(mm(x + dx * nudge), mm(y + dy * nudge)))
                # Re-centre: the anchor is not exactly the ink centre.
                c = ink().Centre()
                field.Move(pcbnew.VECTOR2I(mm(x + dx * nudge) - c.x, mm(y + dy * nudge) - c.y))
                lb = inflate(ink(), 0.1)
                if inside_board(lb) and not any(lb.Intersects(o) for o in obstacles):
                    # Wider margin around labels so neighbouring labels don't read as one word.
                    obstacles.append(inflate(ink(), 0.6))
                    done = True
                    break
            if done:
                break
        if not done:
            # Last resort: the footprint library's own label position, if it only overlaps its
            # own courtyard (fine for DRC) and none of its pads.
            field.SetPosition(default_pos)
            lb = inflate(ink(), 0.1)
            own = inflate(cb, 0.15)
            pads = [inflate(p.GetBoundingBox(), 0.1) for p in fps[ref].Pads()]
            if inside_board(lb) and not any(lb.Intersects(o) for o in obstacles if o != own) \
                    and not any(lb.Intersects(p) for p in pads):
                obstacles.append(inflate(ink(), 0.6))
            else:
                failed.append(ref)
    return failed


def silk_text(board, text, x, y, height, layer=pcbnew.F_SilkS, angle=0, left=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(height), mm(height)))
    t.SetTextThickness(mm(0.15))
    t.SetTextAngleDegrees(angle)
    t.SetMirrored(layer == pcbnew.B_SilkS)
    if left:
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    board.Add(t)
    return t


def silk_line(board, a, b):
    seg = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    seg.SetLayer(pcbnew.F_SilkS)
    seg.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
    seg.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
    seg.SetWidth(mm(0.15))
    board.Add(seg)
    return seg


def back_lines():
    """(text, height, y) for each BACK_TEXT line, the block centred on the board's height."""
    steps = [BACK_BLOCK_GAP if e is None else e[1] + BACK_LINE_GAP for e in BACK_TEXT]
    y = H / 2 - (sum(steps) - steps[-1]) / 2
    out = []
    for e, step in zip(BACK_TEXT, steps):
        if e is not None:
            out.append((e[0], e[1], round(y, 3)))
        y += step
    return out


def board_silk(board, fps, boxes):
    """Function labels, the shared Solar_5V label with its bracket, and the module ID on the
    back. Returns the new items (board coordinates) so reference labels can avoid them."""
    items = []
    for ref, text in FUNCTION_LABELS.items():
        cb = boxes[ref]
        t = silk_text(board, text, 0, pcbnew.ToMM(cb.Centre().y), FUNCTION_TEXT, angle=90)
        ink = t.GetEffectiveTextShape().BBox()
        right = mm(FUNCTION_LABEL_RIGHT[ref]) if ref in FUNCTION_LABEL_RIGHT else cb.GetLeft() - mm(0.35)
        t.Move(pcbnew.VECTOR2I(right - ink.GetRight(), 0))
        items.append(t)
    for ref, text in TOP_LABELS.items():
        cb = boxes[ref]
        t = silk_text(board, text, pcbnew.ToMM(cb.Centre().x), 0, FUNCTION_TEXT)
        ink = t.GetEffectiveTextShape().BBox()
        t.Move(pcbnew.VECTOR2I(0, cb.GetTop() - mm(0.3) - ink.GetBottom()))
        items.append(t)
    top = pcbnew.ToMM(boxes["J1"].GetTop()) + 0.2
    bottom = pcbnew.ToMM(boxes["J4"].GetBottom()) + 2.7
    items.append(silk_line(board, (SOLAR_BRACKET_X, top), (SOLAR_BRACKET_X, bottom)))
    items.append(silk_line(board, (SOLAR_BRACKET_X, top), (SOLAR_BRACKET_X + 0.3, top)))
    items.append(silk_line(board, (SOLAR_BRACKET_X, bottom), (SOLAR_BRACKET_X + 0.3, bottom)))
    items.append(silk_text(board, SOLAR_LABEL, SOLAR_BRACKET_X + 0.6, bottom, 1.0, left=True))
    for ref in POLARITY_REFS:
        cb = boxes[ref]
        for pad in fps[ref].Pads():
            side = 1 if pad.GetPosition().x > cb.Centre().x else -1
            x = pcbnew.ToMM(cb.Centre().x) + side * POLARITY_OFFSET
            t = silk_text(board, "-" if pad.GetNetname() == "GND" else "+", x, 0, POLARITY_TEXT)
            ink = t.GetEffectiveTextShape().BBox()
            t.Move(pcbnew.VECTOR2I(0, cb.GetBottom() + mm(LABEL_GAP + POLARITY_TEXT / 2) - ink.Centre().y))
            items.append(t)
    for text, height, y in back_lines():
        silk_text(board, text, BACK_X, y, height, layer=pcbnew.B_SilkS)

    # I2C connector: function label under J9 on the front, pin names beside its pads on the back
    # (no room between the pads and the right column on the front).
    cb = boxes["J9"]
    t = silk_text(board, I2C_LABEL, pcbnew.ToMM(cb.Centre().x), 0, 1.0)
    ink = t.GetEffectiveTextShape().BBox()
    t.Move(pcbnew.VECTOR2I(0, cb.GetBottom() + mm(0.35) - ink.GetTop()))
    items.append(t)
    for pad in fps["J9"].Pads():
        bb = pad.GetBoundingBox()
        t = silk_text(board, I2C_PINS[pad.GetNumber()], 0, pcbnew.ToMM(pad.GetPosition().y), I2C_PIN_TEXT, layer=pcbnew.B_SilkS)
        ink = t.GetEffectiveTextShape().BBox()
        # J9 is at the left edge now: names go on the inboard side of the pads
        t.Move(pcbnew.VECTOR2I(bb.GetRight() + mm(0.4) - ink.GetLeft(), pad.GetPosition().y - ink.Centre().y))

    # Back-side parts (JP1): reference at the upper pad, function label at the lower pad.
    for ref, text in BACK_LABELS.items():
        fp = fps[ref]
        right = boxes[ref].GetRight() + mm(0.3)
        ys = sorted(p.GetPosition().y for p in fp.Pads())
        field = fp.Reference()
        field.SetTextAngleDegrees(0)
        field.SetKeepUpright(True)
        t = silk_text(board, text, 0, 0, I2C_PIN_TEXT, layer=pcbnew.B_SilkS)
        for item, y in ((field, ys[0]), (t, ys[-1])):
            item.SetPosition(pcbnew.VECTOR2I(0, y))
            ink = item.GetEffectiveTextShape().BBox()
            item.Move(pcbnew.VECTOR2I(right - ink.GetLeft(), y - ink.Centre().y))
    return items


def edge_outline(board):
    c = CHAMFER
    pts = [(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        seg = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetStart(pcbnew.VECTOR2I(mm(ORIGIN[0] + x1), mm(ORIGIN[1] + y1)))
        seg.SetEnd(pcbnew.VECTOR2I(mm(ORIGIN[0] + x2), mm(ORIGIN[1] + y2)))
        seg.SetWidth(mm(0.05))
        board.Add(seg)


def main():
    netfile = sys.argv[1]
    proj = sys.argv[2] if len(sys.argv) > 2 else "."
    pcb_path = os.path.join(proj, NAME + ".kicad_pcb")
    root = ET.parse(netfile).getroot()

    board = pcbnew.NewBoard(pcb_path)
    tb = board.GetTitleBlock()
    tb.SetTitle("SNAP Power Controller")
    tb.SetRevision("1.1")

    fps = {}
    for comp in root.iter("comp"):
        ref = comp.get("ref")
        lib, name = comp.findtext("footprint").split(":")
        fp = pcbnew.FootprintLoad(f"{FPDIR}/{lib}.pretty", name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(comp.findtext("value"))
        # Mirror the symbol's fields so the schematic-parity DRC check stays clean.
        for field, tag in (("Datasheet", "datasheet"), ("Description", "description")):
            if comp.findtext(tag) is not None:
                fp.SetField(field, comp.findtext(tag))
        # Link to the schematic symbol so "Update PCB from Schematic" matches instead of duplicating.
        sheet = comp.find("sheetpath").get("tstamps")
        fp.SetPath(pcbnew.KIID_PATH(sheet + comp.findtext("tstamps")))
        fp.SetSheetname(comp.find("sheetpath").get("names"))
        fp.SetSheetfile(NAME + ".kicad_sch")
        if ref not in PLACEMENT:
            sys.exit(f"no placement for {ref}")
        x, y, rot, *mode = PLACEMENT[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y)))
        if "c" in mode:
            c = courtyard(fp).Centre()
            fp.Move(pcbnew.VECTOR2I(mm(ORIGIN[0] + x) - c.x, mm(ORIGIN[1] + y) - c.y))
        if ref.startswith("H") or ref == "J9":  # J9 is named by its I2C label; no room for both
            fp.Reference().SetVisible(False)
        board.Add(fp)
        if "b" in mode:  # after Add: flipping a footprint that isn't on a board crashes pcbnew
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fps[ref] = fp

    for net in root.iter("net"):
        ni = pcbnew.NETINFO_ITEM(board, net.get("name"))
        board.Add(ni)
        for node in net.iter("node"):
            pads = [p for p in fps[node.get("ref")].Pads() if p.GetNumber() == node.get("pin")]
            if not pads:
                sys.exit(f"{node.get('ref')} has no pad {node.get('pin')}")
            for p in pads:
                p.SetNet(ni)

    # Shift into board coordinates for the checks below.
    board_box = pcbnew.BOX2I(pcbnew.VECTOR2I(0, 0), pcbnew.VECTOR2I(mm(W), mm(H)))
    for fp in fps.values():
        fp.Move(pcbnew.VECTOR2I(-mm(ORIGIN[0]), -mm(ORIGIN[1])))
    boxes = {ref: courtyard(fp) for ref, fp in fps.items()}

    problems = []
    refs = list(boxes)
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            # The boxes include the 0.05 mm courtyard line, so courtyards that only touch (the
            # SOD-123 diodes against their connectors) would count; DRC compares the centre lines.
            if fps[a].IsFlipped() == fps[b].IsFlipped() and inflate(boxes[a], -0.03).Intersects(inflate(boxes[b], -0.03)):
                problems.append(f"courtyard overlap {a}/{b}")
        if not inside_board(boxes[a]) and not a.startswith("H"):
            problems.append(f"{a} too close to the edge")
    silk = board_silk(board, fps, boxes)
    unlabelled = place_labels(fps, boxes, [i.GetEffectiveTextShape().BBox() if isinstance(i, pcbnew.PCB_TEXT) else i.GetBoundingBox() for i in silk])
    problems += [f"no room for label {r}" for r in unlabelled]

    for item in list(fps.values()) + list(board.Drawings()):
        item.Move(pcbnew.VECTOR2I(mm(ORIGIN[0]), mm(ORIGIN[1])))
    edge_outline(board)

    pcbnew.SaveBoard(pcb_path, board)
    print(f"board {W} x {H} mm, {CHAMFER} mm chamfers, {len(fps)} footprints, {board.GetNetCount()} nets")
    for p in problems:
        print("PROBLEM", p)
    print(f"{len(problems)} placement problems")


main()
