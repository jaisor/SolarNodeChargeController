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
    "J1": (5.0, 3.85, 180), "D5": (20.5, 3.85, 180),
    "J2": (5.0, 9.85, 180), "D6": (20.5, 9.85, 180),
    "J3": (5.0, 15.85, 180), "D7": (20.5, 15.85, 180),
    "J4": (5.0, 21.85, 180), "D8": (20.5, 21.85, 180),
    # Solar shunt and input caps next to the P-FET (short hot loop: C1 -> Q1 -> D2).
    "R7": (25.0, 4.0, 90),
    "C1": (28.5, 4.0, 90),
    "C5": (31.5, 4.0, 90),
    "Q1": (35.0, 4.0, 0),
    "D2": (35.0, 9.5, 0),
    "L1": (42.5, 5.0, 0),
    "R5": (42.5, 11.0, 0),
    "C3": (47.5, 11.0, 90),
    # CN3791 and its support parts
    "U1": (30.0, 15.5, 0),
    "C2": (28.5, 10.5, 0),
    "R2": (24.5, 16.0, 90),
    "C4": (24.5, 20.0, 90),
    "R3": (35.5, 16.0, 90),
    "R4": (35.5, 19.5, 90),
    "D4": (27.5, 21.5, 0),
    "D3": (31.0, 21.5, 0),
    "R1": (34.6, 23.5, 0),
    # INA219 monitor; selector switch under the controller; I2C header in the free bottom-left corner
    "U2": (43.5, 17.0, 0),
    "C6": (43.5, 21.5, 0),
    "R8": (39.5, 21.5, 0),
    "R9": (39.5, 23.5, 0),
    "R6": (49.0, 19.5, 90),
    "SW3": (24.79, 23.8, 0),
    "J9": (2.35, 26.4, 90),
    # Right edge: switch leads (XH) and battery/load (PH)
    "J7": (54.0, 3.4, 0),
    "J8": (54.0, 11.3, 0),
    "J5": (55.0, 19.0, 0),
    "J6": (55.0, 25.0, 0),
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
