# Routes the placed board: a small grid A* router (two layers, 8-way moves, vias) written for
# this design, plus GND stitching vias and GND pours. Needs an unrouted board, so run it
# right after tools/place-pcb.py (re-run both to re-route). With KiCad's Python:
#   "C:\Program Files\KiCad\10.0\bin\python.exe" tools/route-pcb.py SolarNodeChargeController
# Then verify with: kicad-cli pcb drc --schematic-parity --severity-all ...
import heapq
import math
import os
import sys

import numpy as np
import pcbnew

NAME = "SolarNodeChargeController"
ORIGIN = (100.0, 100.0)  # must match place-pcb.py
W, H, CHAMFER = 56.5, 29.0, 2.0  # must match place-pcb.py
RES = 0.05  # routing grid, mm
CLEAR = 0.2  # copper-to-copper clearance, mm (board default)
EDGE = 0.5  # copper-to-edge clearance, mm (board default)
HOLE_KEEPOUT = 3.0  # radius around M3 holes kept free of tracks (screw head), mm
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
LAYER_COST = (1.0, 4.0)  # strongly prefer F.Cu so the B.Cu GND plane stays whole
VIA_COST = 200.0  # in grid steps (10 mm of track): stay on F.Cu unless really boxed in

POWER_W, POWER_NECK, SIGNAL_W = 0.8, 0.4, 0.25
POWER_VIA, SIGNAL_VIA = (0.8, 0.4), (0.6, 0.3)  # (diameter, drill)
POWER_NETS = {"/PV", "/VIN", "Net-(D2-K)", "/CSP", "/VBAT", "/BATT+", "/BAT_CELL", "/VOUT",
              "Net-(D5-A)", "Net-(D6-A)", "Net-(D7-A)", "Net-(D8-A)"}
# Pads tied straight to a partner pad instead of the nearest copper: Kelvin connections to
# the current-sense resistors (CN3791 CSP/BAT on R5, INA219 selector throws on R7/R6).
KELVIN = {("U1", "8"): ("R5", "1"), ("U1", "7"): ("R5", "2"),
          ("SW3", "1"): ("R7", "1"), ("SW3", "6"): ("R7", "2"),
          ("SW3", "3"): ("R6", "1"), ("SW3", "4"): ("R6", "2")}
SMALL_PARTS = {"U1", "U2"}  # fine-pitch ICs: never used as a stop on a power path
# Power-stage nets first so the hot loop gets the shortest paths.
NET_ORDER = ["Net-(D2-K)", "/VIN", "/CSP", "/VBAT", "/PV", "/BATT+", "/BAT_CELL", "/VOUT"]

NX, NY = int(round(W / RES)) + 1, int(round(H / RES)) + 1


def mm(v):
    return pcbnew.FromMM(v)


def to_mm(p):
    return pcbnew.ToMM(p.x) - ORIGIN[0], pcbnew.ToMM(p.y) - ORIGIN[1]


def cell(x, y):
    return int(round(x / RES)), int(round(y / RES))


# Distance from each cell centre to the board edge (chamfered rectangle) and to the M3 holes.
YY, XX = np.mgrid[0:NY, 0:NX] * RES
EDGE_DIST = np.minimum.reduce([XX, W - XX, YY, H - YY,
                               (XX + YY - CHAMFER) / math.sqrt(2),
                               (W - XX + YY - CHAMFER) / math.sqrt(2),
                               (XX + H - YY - CHAMFER) / math.sqrt(2),
                               (W - XX + H - YY - CHAMFER) / math.sqrt(2)])


class Grid:
    def __init__(self):
        self.occ = np.zeros((2, NY, NX), dtype=np.int32)  # net code per copper cell, 0 = empty
        self.hole_dist = np.full((NY, NX), np.inf)

    def mark_rect(self, layer_idx, x0, y0, x1, y1, net):
        i0, j0 = max(0, int(math.floor(x0 / RES))), max(0, int(math.floor(y0 / RES)))
        i1, j1 = min(NX - 1, int(math.ceil(x1 / RES))), min(NY - 1, int(math.ceil(y1 / RES)))
        sub = self.occ[layer_idx, j0:j1 + 1, i0:i1 + 1]
        xs, ys = XX[j0:j1 + 1, i0:i1 + 1], YY[j0:j1 + 1, i0:i1 + 1]
        inside = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
        sub[inside] = net

    def mark_segment(self, layer_idx, a, b, width, net):
        (ax, ay), (bx, by) = a, b
        r = width / 2
        i0, i1 = max(0, int((min(ax, bx) - r) / RES) - 1), min(NX - 1, int((max(ax, bx) + r) / RES) + 1)
        j0, j1 = max(0, int((min(ay, by) - r) / RES) - 1), min(NY - 1, int((max(ay, by) + r) / RES) + 1)
        xs, ys = XX[j0:j1 + 1, i0:i1 + 1], YY[j0:j1 + 1, i0:i1 + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / L2, 0, 1) if L2 else 0
        d = np.hypot(xs - (ax + t * dx), ys - (ay + t * dy))
        self.occ[layer_idx, j0:j1 + 1, i0:i1 + 1][d <= r] = net

    def mark_disc(self, layer_idx, c, radius, net):
        self.mark_segment(layer_idx, c, c, 2 * radius, net)


def dilate(mask, r_cells):
    """Binary dilation by a disc, with numpy shifts (no scipy in KiCad's Python)."""
    out = mask.copy()
    rc = int(math.ceil(r_cells))
    h, w = mask.shape
    for dy in range(-rc, rc + 1):
        for dx in range(-rc, rc + 1):
            if dx * dx + dy * dy > r_cells * r_cells or (dx == 0 and dy == 0):
                continue
            ys0, ys1 = max(0, dy), min(h, h + dy)
            xs0, xs1 = max(0, dx), min(w, w + dx)
            out[ys0:ys1, xs0:xs1] |= mask[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def blocked_masks(grid, net, width, via, win):
    """Per-layer 'track centre not allowed' masks and a 'via not allowed' mask in a window."""
    j0, j1, i0, i1 = win
    occ = grid.occ[:, j0:j1, i0:i1]
    others = (occ != 0) & (occ != net)
    r = (width / 2 + CLEAR) / RES + 1.0  # +1 cell: rasterisation margin
    rv = (via[0] / 2 + CLEAR) / RES + 1.0
    edge = EDGE_DIST[j0:j1, i0:i1]
    hole = grid.hole_dist[j0:j1, i0:i1]
    tr = np.stack([dilate(others[k], r) for k in range(2)])
    tr |= (edge < EDGE + width / 2 + RES)[None] | (hole < HOLE_KEEPOUT + width / 2)[None]
    vb = dilate(others[0], rv) | dilate(others[1], rv) | (edge < EDGE + via[0] / 2 + RES) | (hole < HOLE_KEEPOUT + via[0] / 2)
    return tr, vb


DIRS = [(1, 0, 1.0), (1, 1, math.sqrt(2)), (0, 1, 1.0), (-1, 1, math.sqrt(2)),
        (-1, 0, 1.0), (-1, -1, math.sqrt(2)), (0, -1, 1.0), (1, -1, math.sqrt(2))]  # 45-degree steps
TURN_COST = {0: 0.0, 1: 3.0, 2: 6.0}  # by number of 45-degree steps; sharper turns are not allowed
NO_DIR = 8


def octile(dx, dy):
    dx, dy = abs(dx), abs(dy)
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def astar(tr, vb, starts, goals, offset):
    """starts/goals: lists of (layer_idx, i, j) in board cells. Returns a cell path or None.
    The state carries the arrival direction so bends cost extra: routes come out as a few
    straight/45-degree runs instead of grid staircases."""
    j0, i0 = offset
    h, w = tr.shape[1:]
    goal_set = {(l, i - i0, j - j0) for l, i, j in goals}
    gx = sum(i - i0 for _, i, _ in goals) / len(goals)
    gy = sum(j - j0 for _, _, j in goals) / len(goals)
    g = np.full((2, NO_DIR + 1, h, w), np.inf)
    came = {}
    heap = []
    for l, i, j in starts:
        s = (l, i - i0, j - j0, NO_DIR)
        g[l, NO_DIR, s[2], s[1]] = 0
        heapq.heappush(heap, (octile(s[1] - gx, s[2] - gy), 0.0, s))
    while heap:
        f, gc, (l, x, y, d) = heapq.heappop(heap)
        if gc > g[l, d, y, x]:
            continue
        if (l, x, y) in goal_set:
            path, node = [], (l, x, y, d)
            while node is not None:
                path.append((node[0], node[1] + i0, node[2] + j0))
                node = came.get(node)
            return path[::-1]
        moves = []
        for nd, (dx, dy, c) in enumerate(DIRS):
            if d != NO_DIR:
                turn = min((nd - d) % 8, (d - nd) % 8)
                if turn > 2:
                    continue
                c = c + TURN_COST[turn]
            moves.append((l, x + dx, y + dy, nd, c * LAYER_COST[l]))
        if d != NO_DIR and not vb[y, x]:
            moves.append((1 - l, x, y, NO_DIR, VIA_COST))
        for nl, nx, ny, nd, c in moves:
            if not (0 <= nx < w and 0 <= ny < h) or tr[nl, ny, nx]:
                continue
            ng = gc + c
            if ng < g[nl, nd, ny, nx]:
                g[nl, nd, ny, nx] = ng
                came[(nl, nx, ny, nd)] = (l, x, y, d)
                heapq.heappush(heap, (ng + octile(nx - gx, ny - gy), ng, (nl, nx, ny, nd)))
    return None


def simplify(path):
    """Cell path -> list of (layer_idx, [points mm]) runs, one per layer, collinear points merged."""
    runs, cur = [], None
    for l, i, j in path:
        p = (i * RES, j * RES)
        if cur is None or cur[0] != l:
            if cur is not None:
                runs.append(cur)
            cur = (l, [p])  # a layer change happens in place, so this point is the via
        else:
            cur[1].append(p)
    runs.append(cur)
    out = []
    for l, pts in runs:
        keep = [pts[0]]
        for k in range(1, len(pts) - 1):
            a, b, c = keep[-1], pts[k], pts[k + 1]
            d1 = (round((b[0] - a[0]) / RES), round((b[1] - a[1]) / RES))
            d2 = (round((c[0] - b[0]) / RES), round((c[1] - b[1]) / RES))
            if d1[0] * d2[1] != d1[1] * d2[0] or d1[0] * d2[0] + d1[1] * d2[1] < 0:
                keep.append(b)
        if len(pts) > 1:
            keep.append(pts[-1])
        out.append((l, keep))
    return out


class Router:
    def __init__(self, board):
        self.board = board
        self.grid = Grid()
        self.pads = {}  # (ref, num) -> dict
        self.failures = []
        self.track_count = self.via_count = 0
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            for p in fp.Pads():
                x, y = to_mm(p.GetPosition())
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    yy, xx = np.mgrid[0:NY, 0:NX] * RES
                    self.grid.hole_dist = np.minimum(self.grid.hole_dist, np.hypot(xx - x, yy - y))
                    continue
                bb = p.GetBoundingBox()
                x0, y0 = to_mm(bb.GetOrigin())
                x1, y1 = to_mm(bb.GetEnd())
                layers = [k for k, L in enumerate(LAYERS) if p.IsOnLayer(L)]
                for k in layers:
                    self.grid.mark_rect(k, x0, y0, x1, y1, p.GetNetCode())
                area = (x1 - x0) * (y1 - y0)
                self.pads[(ref, p.GetNumber())] = dict(
                    ref=ref, num=p.GetNumber(), x=x, y=y, layers=layers, net=p.GetNetCode(),
                    netname=p.GetNetname(), small=ref in SMALL_PARTS or area < 1.0,
                    tht=p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH)

    def net_pads(self, netname):
        return [p for p in self.pads.values() if p["netname"] == netname]

    def add_track(self, layer_idx, a, b, width, net):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(pcbnew.VECTOR2I(mm(ORIGIN[0] + a[0]), mm(ORIGIN[1] + a[1])))
        t.SetEnd(pcbnew.VECTOR2I(mm(ORIGIN[0] + b[0]), mm(ORIGIN[1] + b[1])))
        t.SetWidth(mm(width))
        t.SetLayer(LAYERS[layer_idx])
        t.SetNetCode(net)
        self.board.Add(t)
        self.grid.mark_segment(layer_idx, a, b, width, net)
        self.track_count += 1

    def add_via(self, c, via, net):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(pcbnew.VECTOR2I(mm(ORIGIN[0] + c[0]), mm(ORIGIN[1] + c[1])))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetWidth(mm(via[0]))
        v.SetDrill(mm(via[1]))
        v.SetNetCode(net)
        self.board.Add(v)
        for k in range(2):
            self.grid.mark_disc(k, c, via[0] / 2, net)
        self.via_count += 1

    def connect(self, a, b, width, via):
        """Route pad a -> pad b. Tries a growing search window. Returns True on success."""
        net = a["net"]
        starts_c = [(k,) + cell(a["x"], a["y"]) for k in a["layers"]]
        goals_c = [(k,) + cell(b["x"], b["y"]) for k in b["layers"]]
        for margin in (4.0, 10.0, 60.0):
            x0, x1 = min(a["x"], b["x"]) - margin, max(a["x"], b["x"]) + margin
            y0, y1 = min(a["y"], b["y"]) - margin, max(a["y"], b["y"]) + margin
            i0, i1 = max(0, int(x0 / RES)), min(NX, int(x1 / RES) + 1)
            j0, j1 = max(0, int(y0 / RES)), min(NY, int(y1 / RES) + 1)
            tr, vb = blocked_masks(self.grid, net, width, via, (j0, j1, i0, i1))
            path = astar(tr, vb, starts_c, goals_c, (j0, i0))
            if path:
                break
        else:
            return False
        runs = simplify(path)
        for n, (l, pts) in enumerate(runs):
            pts = list(pts)
            if n == 0:
                pts[0] = (a["x"], a["y"])
            if n == len(runs) - 1:
                pts[-1] = (b["x"], b["y"])
            for p, q in zip(pts, pts[1:]):
                if p != q:
                    self.add_track(l, p, q, width, net)
            if n < len(runs) - 1:
                self.add_via(pts[-1], via, net)
        return True

    def route_net(self, netname):
        pads = self.net_pads(netname)
        if len(pads) < 2:
            return
        power = netname in POWER_NETS
        kelvin = {id(p): self.pads[KELVIN[(p["ref"], p["num"])]] for p in pads if (p["ref"], p["num"]) in KELVIN}
        big = [p for p in pads if not p["small"] and id(p) not in kelvin] or [p for p in pads if id(p) not in kelvin][:1]
        # Prim's MST over the big pads first, then attach small pads to the nearest connected pad.
        done, edges = [big[0]], []
        todo = [p for p in big[1:]]
        for group in (todo, [p for p in pads if p not in big and id(p) not in kelvin]):
            while group:
                a, b = min(((a, b) for a in done for b in group), key=lambda e: math.hypot(e[0]["x"] - e[1]["x"], e[0]["y"] - e[1]["y"]))
                edges.append((a, b))
                done.append(b)
                group.remove(b)
        edges += [(kelvin[id(p)], p) for p in pads if id(p) in kelvin]
        edges.sort(key=lambda e: math.hypot(e[0]["x"] - e[1]["x"], e[0]["y"] - e[1]["y"]))
        for a, b in edges:
            both_big = not a["small"] and not b["small"] and id(a) not in kelvin and id(b) not in kelvin
            widths = ([POWER_W] if both_big else []) + [POWER_NECK] if power else [SIGNAL_W]
            widths = widths + [SIGNAL_W, 0.2] if widths[-1] > SIGNAL_W else widths + [0.2]
            via = POWER_VIA if power else SIGNAL_VIA
            if not any(self.connect(a, b, w, via if w >= POWER_NECK else SIGNAL_VIA) for w in widths):
                self.failures.append(f"{netname}: {a['ref']}.{a['num']} -> {b['ref']}.{b['num']}")

    def stitch_gnd(self, gnd):
        """Give every surface-mount GND pad its own via to the B.Cu plane."""
        stitched = []
        for p in self.net_pads("GND"):
            if p["tht"]:
                continue
            if self.stitch_pad(p, gnd):
                stitched.append(p)
                continue
            # Boxed in: tie it to the nearest GND pad that already has its via.
            others = sorted(stitched, key=lambda q: math.hypot(q["x"] - p["x"], q["y"] - p["y"]))
            if not any(self.connect(q, p, SIGNAL_W, SIGNAL_VIA) for q in others[:3]):
                self.failures.append(f"GND stitch {p['ref']}.{p['num']}")

    def stitch_pad(self, p, gnd):
        """Short F.Cu track from a GND pad to a new via within 4 mm. Returns True on success."""
        pi, pj = cell(p["x"], p["y"])
        win = (max(0, pj - 100), min(NY, pj + 101), max(0, pi - 100), min(NX, pi + 101))
        for width in (0.4, SIGNAL_W):
            tr, vb = blocked_masks(self.grid, gnd, width, SIGNAL_VIA, win)
            no_via = np.ones_like(vb)  # the stitch track itself stays on F.Cu
            for r in np.arange(0.9, 4.01, 0.15):
                for ang in range(0, 360, 15):
                    cx, cy = p["x"] + r * math.cos(math.radians(ang)), p["y"] + r * math.sin(math.radians(ang))
                    ci, cj = cell(cx, cy)
                    if not (win[2] <= ci < win[3] and win[0] <= cj < win[1]) or vb[cj - win[0], ci - win[2]]:
                        continue
                    path = astar(tr, no_via, [(0, pi, pj)], [(0, ci, cj)], (win[0], win[2]))
                    if not path:
                        continue
                    for _, pts in simplify(path):
                        pts = list(pts)
                        pts[0] = (p["x"], p["y"])
                        for a, b in zip(pts, pts[1:]):
                            if a != b:
                                self.add_track(0, a, b, width, gnd)
                    self.add_via((ci * RES, cj * RES), SIGNAL_VIA, gnd)
                    return True
        return False


def add_gnd_zone(board, layer, gnd, connection):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNetCode(gnd)
    c = CHAMFER
    for x, y in [(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)]:
        z.AppendCorner(pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y)), -1)
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.25))
    z.SetPadConnection(connection)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(0)
    board.Add(z)
    return z


def main():
    path = os.path.join(sys.argv[1], NAME + ".kicad_pcb")
    board = pcbnew.LoadBoard(path)
    # Removing zones through SWIG crashes in KiCad 10, so start from a freshly placed board.
    if len(board.GetTracks()) or len(board.Zones()):
        sys.exit("board already has tracks/zones: run tools/place-pcb.py first")

    r = Router(board)
    gnd = board.FindNet("GND").GetNetCode()
    names = sorted({p["netname"] for p in r.pads.values() if p["netname"] and p["netname"] != "GND"
                    and not p["netname"].startswith("unconnected")})
    order = [n for n in NET_ORDER if n in names] + sorted(
        (n for n in names if n not in NET_ORDER),
        key=lambda n: sum(math.hypot(a["x"] - b["x"], a["y"] - b["y"]) for a in r.net_pads(n) for b in r.net_pads(n)))
    # GND fan-out first: every SMD GND pad gets its via before signals can box it in
    # (U2 pin 6 sits between IN- and VS and was unreachable when stitched last).
    r.stitch_gnd(gnd)
    for n in order:
        r.route_net(n)

    # Power-connector GND pins carry battery/panel current: connect them solidly to the pours
    # (small PicoBlade pads also leave no room for a second thermal spoke next to pin 1).
    for fp in board.GetFootprints():
        if fp.GetReference() in {f"J{i}" for i in range(1, 9)}:
            for p in fp.Pads():
                if p.GetNetname() == "GND":
                    p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    # B.Cu: thermal reliefs (hand-solderable connectors). F.Cu: solid to SMD pads, which also
    # avoids starved thermals where tracks crowd a pad's spokes.
    zones = [add_gnd_zone(board, pcbnew.B_Cu, gnd, pcbnew.ZONE_CONNECTION_THERMAL),
             add_gnd_zone(board, pcbnew.F_Cu, gnd, pcbnew.ZONE_CONNECTION_THT_THERMAL)]
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print(f"{r.track_count} track segments, {r.via_count} vias, {len(zones)} GND zones")
    for f in r.failures:
        print("FAILED", f)
    print(f"{len(r.failures)} failed connections")


main()
