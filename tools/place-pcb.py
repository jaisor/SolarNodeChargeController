# Builds the draft PCB: footprints from the schematic netlist, placed by hand-tuned
# coordinates, nets assigned, reference labels auto-placed clear of everything, M3 holes
# in the corners and a chamfered Edge.Cuts outline. No tracks. Run with KiCad's Python:
#   "C:\Program Files\KiCad\10.0\bin\python.exe" tools/place-pcb.py SolarNodeChargeController <netlist.xml>
# Netlist: kicad-cli sch export netlist --format kicadxml -o net.xml SolarNodeChargeController/SolarNodeChargeController.kicad_sch
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

FPDIR = "C:/Program Files/KiCad/10.0/share/kicad/footprints"
NAME = "SolarNodeChargeController"
ORIGIN = (100.0, 100.0)  # board top-left in the editor, mm
W, H = 56.5, 29.0  # board size, mm
CHAMFER = 2.0  # 45-degree corner chamfer, mm
HOLE_INSET = 4.0  # M3 hole centre distance from each edge, mm
EDGE_CLEAR = 0.6  # courtyard/label to board edge, mm
LABEL_GAP = 0.35  # label to its own courtyard, mm (must exceed the 0.25 mm of check margins)

# ref: (x, y, rotation[, "c"]) in mm relative to the board's top-left corner. Position is the
# footprint origin, or the courtyard centre when the 4th element is "c".
# Left band: M3 holes + SOLAR/BATT switch. Then solar inputs, the CN3791 buck stage and the
# INA219, the battery/load/switch connectors, and the right band: M3 holes + I2C connector.
PLACEMENT = {
    "H1": (HOLE_INSET, HOLE_INSET, 0, "c"),
    "H2": (W - HOLE_INSET, HOLE_INSET, 0, "c"),
    "H3": (HOLE_INSET, H - HOLE_INSET, 0, "c"),
    "H4": (W - HOLE_INSET, H - HOLE_INSET, 0, "c"),
    "SW3": (3.75, H / 2, 90, "c"),
    "J9": (W - 3.75, H / 2, 90, "c"),
    # Solar inputs: connector pin 1 faces its diode's anode; cathodes line up on the PV bus.
    "J1": (11.29, 2.4, 180), "D5": (15.45, 2.4, 180),
    "J2": (11.29, 8.7, 180), "D6": (15.45, 8.7, 180),
    "J3": (11.29, 15.0, 180), "D7": (15.45, 15.0, 180),
    "J4": (11.29, 21.3, 180), "D8": (15.45, 21.3, 180),
    # Solar shunt and input caps next to the P-FET (short hot loop: C1 -> Q1 -> D2).
    "R7": (18.8, 5.4, 90),
    "C1": (22.3, 5.4, 90),
    "C5": (25.3, 5.4, 90),
    "Q1": (28.8, 5.4, 0),
    "D2": (28.8, 10.9, 0),
    "L1": (36.3, 6.4, 0),
    "R5": (36.3, 12.7, 0),
    "C3": (40.1, 12.4, 90),
    # CN3791 and its support parts
    "U1": (23.8, 16.9, 0),
    "C2": (22.3, 11.9, 0),
    "R2": (18.5, 17.4, 90),
    "C4": (18.5, 21.4, 90),
    "R3": (29.3, 17.4, 90),
    "R4": (29.3, 20.9, 90),
    "D4": (21.3, 22.9, 0),
    "D3": (24.8, 22.9, 0),
    "R1": (21.0, 25.8, 0),
    # INA219 monitor
    "U2": (37.3, 18.9, 0),
    "C6": (37.3, 23.3, 0),
    "R8": (30.8, 24.4, 90),
    "R9": (33.3, 24.4, 90),
    "R6": (37.95, 25.4, 0),
    # Right column: switch leads, battery, load
    "J7": (45.14, 3.3, 0),
    "J8": (45.14, 9.6, 0),
    "J5": (45.14, 15.9, 0),
    "J6": (45.14, 22.2, 0),
}

# Function labels on F.Silkscreen, vertical, just left of each right-column connector.
FUNCTION_LABELS = {"J7": "SW_BATT", "J8": "SW_LOAD", "J5": "BATT", "J6": "VOUT"}
FUNCTION_TEXT = 0.8  # mm
SOLAR_LABEL = "Solar_5V"  # one label for J1-J4, with a bracket along their left side
SOLAR_BRACKET_X = 7.75
# Module ID, centred and mirrored on B.Silkscreen: (text, height mm)
BACK_TEXT = [("Solar Charge Module v1.0", 1.2), ("by JaisorGadgets", 1.0), ("Oct. 2026", 1.0)]
# I2C connector J9: front label below it, pin names on B.Silkscreen beside each pad
I2C_LABEL = "I2C"
I2C_PINS = {"1": "VCC", "2": "SDA", "3": "SCL", "4": "GND"}
I2C_PIN_TEXT = 0.8  # mm; the pads are on a 1.25 mm pitch
# SW3 (INA219 shunt selector): two vertical lines on B.Silkscreen beside its pads.
# Rotated 270 so "solar" sits at the PV/VIN throws (pins 1/6) and "batt" at BATT+/BAT_CELL (pins 3/4).
SW3_LABEL = ["i2c power sensor", "solar/batt"]  # nearest the pads first; reads "solar/batt" then "i2c power sensor"

# Label side preference per reference (N/S/E/W); anything unlisted tries N, S, E, W.
# Connectors and the solar diodes label underneath so each label reads with its own part.
LABEL_SIDES = {r: "SN" for r in ("J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "D5", "D6", "D7", "D8", "R5")}
LABEL_SIDES.update({"U2": "WNSE", "J9": "NS", "SW3": "NS"})


def mm(v):
    return pcbnew.FromMM(v)


def courtyard(fp):
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
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
    obstacles = [inflate(b, 0.15) for b in boxes.values()] + [inflate(b, 0.3) for b in extra_obstacles]
    failed = []
    for ref in sorted(fps, key=lambda r: -boxes[r].GetArea()):
        field = fps[ref].Reference()
        if not field.IsVisible():
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


def board_silk(board, fps, boxes):
    """Function labels, the shared Solar_5V label with its bracket, and the module ID on the
    back. Returns the new items (board coordinates) so reference labels can avoid them."""
    items = []
    for ref, text in FUNCTION_LABELS.items():
        cb = boxes[ref]
        t = silk_text(board, text, 0, pcbnew.ToMM(cb.Centre().y), FUNCTION_TEXT, angle=90)
        ink = t.GetEffectiveTextShape().BBox()
        t.Move(pcbnew.VECTOR2I(cb.GetLeft() - mm(0.35) - ink.GetRight(), 0))
        items.append(t)
    top = pcbnew.ToMM(boxes["J1"].GetTop()) + 0.2
    bottom = pcbnew.ToMM(boxes["J4"].GetBottom()) + 2.7
    items.append(silk_line(board, (SOLAR_BRACKET_X, top), (SOLAR_BRACKET_X, bottom)))
    items.append(silk_line(board, (SOLAR_BRACKET_X, top), (SOLAR_BRACKET_X + 0.3, top)))
    items.append(silk_line(board, (SOLAR_BRACKET_X, bottom), (SOLAR_BRACKET_X + 0.3, bottom)))
    items.append(silk_text(board, SOLAR_LABEL, SOLAR_BRACKET_X + 0.6, bottom, 1.0, left=True))
    y = H / 2 - 1.6
    for text, height in BACK_TEXT:
        silk_text(board, text, W / 2, y, height, layer=pcbnew.B_SilkS)
        y += height + 0.8

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
        t.Move(pcbnew.VECTOR2I(bb.GetLeft() - mm(0.4) - ink.GetRight(), pad.GetPosition().y - ink.Centre().y))

    # SW3: what the switch does, on the back between its pads and the solar connectors.
    x = max(p.GetBoundingBox().GetRight() for p in fps["SW3"].Pads()) + mm(0.4)
    cy = boxes["SW3"].Centre().y
    for text in SW3_LABEL:
        t = silk_text(board, text, 0, 0, I2C_PIN_TEXT, layer=pcbnew.B_SilkS, angle=270)
        ink = t.GetEffectiveTextShape().BBox()
        t.Move(pcbnew.VECTOR2I(x - ink.GetLeft(), cy - ink.Centre().y))
        x = t.GetEffectiveTextShape().BBox().GetRight() + mm(0.3)
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
    proj, netfile = sys.argv[1], sys.argv[2]
    pcb_path = os.path.join(proj, NAME + ".kicad_pcb")
    root = ET.parse(netfile).getroot()

    board = pcbnew.NewBoard(pcb_path)
    tb = board.GetTitleBlock()
    tb.SetTitle("Solar Node Charge Controller")
    tb.SetRevision("0.1")
    tb.SetComment(0, "Placement draft - not routed")

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
        if mode == ["c"]:
            c = courtyard(fp).Centre()
            fp.Move(pcbnew.VECTOR2I(mm(ORIGIN[0] + x) - c.x, mm(ORIGIN[1] + y) - c.y))
        if ref.startswith("H"):
            fp.Reference().SetVisible(False)
        board.Add(fp)
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
            if boxes[a].Intersects(boxes[b]):
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
