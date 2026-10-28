# Builds the draft PCB: footprints from the schematic netlist, placed by hand-tuned
# coordinates, nets assigned, and a rectangular Edge.Cuts outline hugging the courtyards.
# No tracks. Run with KiCad's Python (needs pcbnew):
#   "C:\Program Files\KiCad\10.0\bin\python.exe" tools/place-pcb.py SolarNodeChargeController <netlist.xml>
# Netlist: kicad-cli sch export netlist --format kicadxml -o net.xml SolarNodeChargeController/SolarNodeChargeController.kicad_sch
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

FPDIR = "C:/Program Files/KiCad/10.0/share/kicad/footprints"
NAME = "SolarNodeChargeController"
ORIGIN = (100.0, 100.0)  # board top-left in the editor, mm
MARGIN = 0.5  # courtyard-to-edge clearance, mm

# ref: (x, y, rotation) in mm relative to the board's top-left corner.
# Left edge: solar inputs. Middle: CN3791 buck stage and INA219. Right edge: battery, load, switch leads.
PLACEMENT = {
    # Solar inputs: connector pin 1 faces its diode's anode; cathodes line up on the PV bus.
    "J1": (3.79, 2.2, 180), "D5": (7.95, 2.2, 180),
    "J2": (3.79, 7.0, 180), "D6": (7.95, 7.0, 180),
    "J3": (3.79, 11.8, 180), "D7": (7.95, 11.8, 180),
    "J4": (3.79, 16.6, 180), "D8": (7.95, 16.6, 180),
    # Solar shunt and input caps next to the P-FET (short hot loop: C1 -> Q1 -> D2).
    "R7": (11.3, 4.0, 90),
    "C1": (14.8, 4.0, 90),
    "C5": (17.8, 4.0, 90),
    "Q1": (21.3, 4.0, 0),
    "D2": (21.3, 9.5, 0),
    "L1": (28.8, 5.0, 0),
    "R5": (28.8, 11.0, 0),
    "C3": (33.8, 11.0, 90),
    # CN3791 and its support parts
    "U1": (16.3, 15.5, 0),
    "C2": (14.8, 10.5, 0),
    "R2": (11.0, 16.0, 90),
    "C4": (11.0, 20.0, 90),
    "R3": (21.8, 16.0, 90),
    "R4": (21.8, 19.5, 90),
    "D4": (13.8, 21.5, 0),
    "D3": (17.3, 21.5, 0),
    "R1": (21.7, 23.5, 0),
    # INA219 monitor and its bottom row; selector switch under the solar inputs
    "U2": (29.8, 17.0, 0),
    "C6": (29.8, 21.5, 0),
    "R8": (25.8, 21.5, 0),
    "R9": (25.8, 23.5, 0),
    "R6": (29.95, 23.6, 0),
    "SW3": (2.79, 20.69, 0),
    # Right edge: switch leads, battery, load; I2C header (4-pin) under them
    "J7": (37.34, 3.1, 0),
    "J8": (37.34, 7.9, 0),
    "J5": (37.34, 12.7, 0),
    "J6": (37.34, 17.5, 0),
    "J9": (35.2, 22.4, 0),
}


def mm(v):
    return pcbnew.FromMM(v)


def courtyard(fp):
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    return cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)


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
        x, y, rot = PLACEMENT[ref]
        fp.SetPosition(pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y)))
        fp.SetOrientationDegrees(rot)
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

    # Courtyard overlap check and the outline that hugs them.
    boxes = {ref: courtyard(fp) for ref, fp in fps.items()}
    clashes = [(a, b) for i, a in enumerate(boxes) for b in list(boxes)[i + 1:] if boxes[a].Intersects(boxes[b])]
    for a, b in clashes:
        print(f"OVERLAP {a} / {b}")
    left = min(b.GetLeft() for b in boxes.values()) - mm(MARGIN)
    top = min(b.GetTop() for b in boxes.values()) - mm(MARGIN)
    right = max(b.GetRight() for b in boxes.values()) + mm(MARGIN)
    bottom = max(b.GetBottom() for b in boxes.values()) + mm(MARGIN)
    # Snap outward to 0.5 mm so the board has round dimensions.
    snap = mm(0.5)
    left, top = (left // snap) * snap, (top // snap) * snap
    right, bottom = -((-right) // snap) * snap, -((-bottom) // snap) * snap

    edge = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetStart(pcbnew.VECTOR2I(int(left), int(top)))
    edge.SetEnd(pcbnew.VECTOR2I(int(right), int(bottom)))
    edge.SetWidth(mm(0.05))
    board.Add(edge)

    pcbnew.SaveBoard(pcb_path, board)
    print(f"board {pcbnew.ToMM(right - left):.1f} x {pcbnew.ToMM(bottom - top):.1f} mm, "
          f"{len(fps)} footprints, {board.GetNetCount()} nets, {len(clashes)} courtyard overlaps")
    for ref, b in sorted(boxes.items()):
        print(f"  {ref:4} x {pcbnew.ToMM(b.GetLeft()) - ORIGIN[0]:6.2f}..{pcbnew.ToMM(b.GetRight()) - ORIGIN[0]:6.2f}"
              f"  y {pcbnew.ToMM(b.GetTop()) - ORIGIN[1]:6.2f}..{pcbnew.ToMM(b.GetBottom()) - ORIGIN[1]:6.2f}")


main()
