// Generates the CN3791 solar charger schematic (datasheet Figure 1) for KiCad 10.
// Usage: node tools/gen-schematic.js SolarNodeChargeController   (run from this folder)
const fs = require("fs");
const crypto = require("crypto");
const path = require("path");

const LIBDIR = "C:/Program Files/KiCad/10.0/share/kicad/symbols";
const PROJ = process.argv[2];
const NAME = "SolarNodeChargeController";
const SCH = path.join(PROJ, NAME + ".kicad_sch");
// Deterministic UUIDs keyed by what an item is (symbol ref, wire endpoints, ...), so
// regenerating keeps symbol identities stable for the PCB links and keeps git diffs small.
function uuid(key) {
  const h = crypto.createHash("sha1").update(`${NAME}/${key}`).digest("hex");
  const variant = (8 | (parseInt(h[16], 16) & 3)).toString(16);
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-${variant}${h.slice(17, 20)}-${h.slice(20, 32)}`;
}
const r = (v) => Math.round(v * 1e4) / 1e4;

// ---------- s-expression helpers ----------
function block(text, i) {
  let d = 0;
  for (let j = i; j < text.length; j++) {
    if (text[j] === "(") d++;
    else if (text[j] === ")" && --d === 0) return text.slice(i, j + 1);
  }
  throw new Error("unbalanced at " + i);
}
function findSym(text, name) {
  const k = text.indexOf(`\n\t(symbol "${name}"\n`);
  if (k < 0) throw new Error("symbol not found: " + name);
  return block(text, k + 2);
}
// Returns a library symbol with derived ("extends") symbols flattened, renamed to lib:name.
function libSymbol(lib, name) {
  const text = fs.readFileSync(`${LIBDIR}/${lib}.kicad_sym`, "utf8").replace(/\r\n/g, "\n");
  let s = findSym(text, name);
  const ext = s.match(/\(extends "([^"]+)"\)/);
  if (ext) {
    let base = findSym(text, ext[1]);
    for (const m of s.matchAll(/\(property "([^"]+)"/g)) {
      const dprop = block(s, m.index);
      const bi = base.indexOf(`(property "${m[1]}"`);
      if (bi >= 0) base = base.replace(block(base, bi), () => dprop);
      else base = base.replace(/\n\t\t\(symbol "/, () => `\n\t\t${dprop}\n\t\t(symbol "`);
    }
    base = base
      .replace(`(symbol "${ext[1]}"`, `(symbol "${name}"`)
      .split(`(symbol "${ext[1]}_`).join(`(symbol "${name}_`);
    s = base;
  }
  return s.replace(`(symbol "${name}"`, `(symbol "${lib}:${name}"`);
}
function pinsOf(symText) {
  const out = {};
  for (const m of symText.matchAll(/\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)[\s\S]*?\(number "([^"]*)"/g))
    out[m[4]] = { x: +m[1], y: +m[2] };
  return out;
}

// ---------- CN3791 symbol (pinout from datasheet p.1/p.3) ----------
const fx = (s) => `(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)`;
function libProp(name, value, x, y, hide, justify) {
  return `\t\t(property "${name}" "${value}"
			(at ${x} ${y} 0)
			${hide ? "(hide yes)\n\t\t\t" : ""}(effects
				(font
					(size 1.27 1.27)
				)${justify ? `\n\t\t\t\t(justify ${justify})` : ""}
			)
		)`;
}
function libPin(type, x, y, ang, name, num) {
  return `\t\t\t(pin ${type} line
				(at ${x} ${y} ${ang})
				(length 2.54)
				(name "${name}"
					${fx().replace(/\n\t/g, "\n\t\t\t")}
				)
				(number "${num}"
					${fx().replace(/\n\t/g, "\n\t\t\t")}
				)
			)`;
}
const CN3791 = `\t(symbol "CN3791"
		(pin_names
			(offset 1.016)
		)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
${libProp("Reference", "U", -7.62, 11.43, false, "left")}
${libProp("Value", "CN3791", 7.62, 11.43, false, "right")}
${libProp("Footprint", "Package_SO:SSOP-10_3.9x4.9mm_P1.00mm", 0, -16.51, true)}
${libProp("Datasheet", "https://naylampmechatronics.com/img/cms/001216/CN3791.PDF", 0, -19.05, true)}
${libProp("Description", "4A standalone Li-ion charger controller with photovoltaic MPPT, 4.2V, SSOP-10", 0, 0, true)}
${libProp("ki_keywords", "solar MPPT lithium Li-ion charger buck PWM", 0, 0, true)}
${libProp("ki_fp_filters", "SSOP*3.9x4.9mm*P1.00mm*", 0, 0, true)}
		(symbol "CN3791_0_1"
			(rectangle
				(start -7.62 10.16)
				(end 7.62 -10.16)
				(stroke
					(width 0.254)
					(type default)
				)
				(fill
					(type background)
				)
			)
		)
		(symbol "CN3791_1_1"
${[
  libPin("power_in", -10.16, 7.62, 0, "VCC", "9"),
  libPin("input", -10.16, 2.54, 0, "MPPT", "6"),
  libPin("open_collector", -10.16, -2.54, 0, "~{CHRG}", "3"),
  libPin("open_collector", -10.16, -5.08, 0, "~{DONE}", "4"),
  libPin("passive", 10.16, 7.62, 180, "VG", "1"),
  libPin("output", 10.16, 5.08, 180, "DRV", "10"),
  libPin("input", 10.16, 0, 180, "CSP", "8"),
  libPin("input", 10.16, -2.54, 180, "BAT", "7"),
  libPin("passive", 10.16, -7.62, 180, "COM", "5"),
  libPin("power_in", 0, -12.7, 90, "GND", "2"),
].join("\n")}
		)
		(embedded_fonts no)
	)`;

// ---------- symbol registry ----------
const SYMS = {};
function useSym(libId) {
  if (SYMS[libId]) return SYMS[libId];
  const [lib, name] = libId.split(":");
  const text = lib === "SolarNode" ? CN3791.replace('(symbol "CN3791"', '(symbol "SolarNode:CN3791"') : libSymbol(lib, name);
  return (SYMS[libId] = { text, pins: pinsOf(text) });
}

// ---------- placement ----------
// Library coords are Y-up; schematic is Y-down. Angle rotates counter-clockwise on screen.
function xf(p, rot, mirror) {
  let x = p.x, y = -p.y;
  for (let i = 0; i < ((rot / 90) % 4); i++) [x, y] = [y, -x];
  if (mirror === "y") x = -x;
  return { x, y };
}
const PARTS = [];
let pwrN = 0, flgN = 0;
function place(ref, libId, x, y, o = {}) {
  const sym = useSym(libId);
  const part = { ref, libId, x: r(x), y: r(y), rot: o.rot || 0, mirror: o.mirror, o, sym };
  part.pin = (n) => {
    const p = xf(sym.pins[n], part.rot, part.mirror);
    if (!p) throw new Error(`${ref} has no pin ${n}`);
    return { x: r(part.x + p.x), y: r(part.y + p.y) };
  };
  PARTS.push(part);
  return part;
}
function placeByPin(ref, libId, pinNum, at, o = {}) {
  const sym = useSym(libId);
  const p = xf(sym.pins[pinNum], o.rot || 0, o.mirror);
  return place(ref, libId, at.x - p.x, at.y - p.y, o);
}

const WIRES = [], LABELS = [], JUNCTIONS = [], TEXTS = [];
const P = (x, y) => ({ x: r(x), y: r(y) });
function wire(...pts) {
  for (let i = 0; i < pts.length - 1; i++) WIRES.push([pts[i], pts[i + 1]]);
  return pts[pts.length - 1];
}
const junction = (p) => JUNCTIONS.push(p);
const NOCONNECTS = [];
const noConnect = (p) => NOCONNECTS.push(p);
const DIRS = { right: [1, 0, 0], left: [-1, 0, 180], up: [0, -1, 90], down: [0, 1, 270] };
function stub(from, dir, name, len = 2.54) {
  const [dx, dy, ang] = DIRS[dir];
  const end = P(from.x + dx * len, from.y + dy * len);
  wire(from, end);
  LABELS.push({ name, at: end, ang });
  return end;
}
function gnd(at) {
  pwrN++;
  return place(`#PWR0${String(pwrN).padStart(2, "0")}`, "power:GND", at.x, at.y, { value: "GND", power: true });
}
function flag(at, rot) {
  flgN++;
  return place(`#FLG0${String(flgN).padStart(2, "0")}`, "power:PWR_FLAG", at.x, at.y, { value: "PWR_FLAG", power: true, rot });
}

const FP = {
  r0603: "Resistor_SMD:R_0603_1608Metric",
  r1206: "Resistor_SMD:R_1206_3216Metric",
  c0603: "Capacitor_SMD:C_0603_1608Metric",
  c1206: "Capacitor_SMD:C_1206_3216Metric",
  led: "LED_SMD:LED_0603_1608Metric",
  // Micro JST 1.25 (Molex PicoBlade-compatible) headers; mate with 51021 female cable housings.
  pico2: "Connector_Molex:Molex_PicoBlade_53047-0210_1x02_P1.25mm_Vertical",
  pico4: "Connector_Molex:Molex_PicoBlade_53047-0410_1x04_P1.25mm_Vertical",
};

// ---------- circuit ----------
const RAIL = 50.8;

// Up to four solar panels in parallel, each OR-ed onto VIN through its own Schottky
// so a shaded or disconnected panel can't sink current from the others.
const BUS_X = 50.8;
const taps = [];
for (let i = 0; i < 4; i++) {
  const y = 60.96 + i * 12.7;
  const J = place(`J${i + 1}`, "Connector_Generic:Conn_01x02", 25.4, y, { mirror: "y", value: "Solar_5V", fp: FP.pico2 });
  const D = placeByPin(`D${i + 5}`, "Diode:1N5819WS", "2", P(35.56, y), { rot: 180, value: "1N5819WS" });
  wire(J.pin("1"), D.pin("2"));
  wire(D.pin("1"), P(BUS_X, y));
  gnd(wire(J.pin("2"), P(33.02, J.pin("2").y), P(33.02, y + 5.08)));
  taps.push(P(BUS_X, y));
}
wire(P(BUS_X, RAIL), ...taps);
taps.slice(0, -1).forEach(junction);
LABELS.push({ name: "PV", at: taps[0], ang: 0 });
// GND needs a driver for ERC; tie a flag to a stand-alone ground symbol.
wire(P(40.64, 38.1), P(40.64, 40.64));
flag(P(40.64, 38.1));
gnd(P(40.64, 40.64));

// Solar current shunt (INA219 "SOLAR" position): PV bus -> R7 -> VIN
const R7 = placeByPin("R7", "Device:R", "1", P(BUS_X, RAIL), { rot: 90, value: "0.1R 1%", fp: FP.r1206, textAbove: true });
const vinFlag = P(63.5, RAIL);
flag(vinFlag);

const C1 = placeByPin("C1", "Device:C", "1", P(68.58, RAIL), { value: "10uF/25V", fp: FP.c1206 });
gnd(C1.pin("2"));
const C5 = placeByPin("C5", "Device:C", "1", P(83.82, RAIL), { value: "100nF/25V", fp: FP.c0603 });
gnd(C5.pin("2"));
const R3 = placeByPin("R3", "Device:R", "1", P(99.06, RAIL), { value: "28.0k 1%", fp: FP.r0603 });
const R4 = placeByPin("R4", "Device:R", "1", R3.pin("2"), { value: "10k 1%", fp: FP.r0603 });
gnd(R4.pin("2"));
stub(R3.pin("2"), "right", "MPPT", 12.7);
junction(R3.pin("2"));

// Power path: Q1 -> SW -> L1 -> CSP -> R5 (RCS) -> VBAT
const Q1 = placeByPin("Q1", "Transistor_FET:AO3401A", "2", P(116.84, RAIL), { rot: 270, value: "AO3401A" });
wire(R7.pin("2"), vinFlag, P(68.58, RAIL), P(83.82, RAIL), P(99.06, RAIL), P(109.22, RAIL), Q1.pin("2"));
[63.5, 68.58, 83.82, 99.06].forEach((x) => junction(P(x, RAIL)));
LABELS.push({ name: "VIN", at: P(109.22, RAIL), ang: 0 });
stub(Q1.pin("1"), "up", "DRV");

// Datasheet D1 (blocking diode) omitted: D5-D8 already keep the battery out of the panels.
const SW = P(144.78, RAIL);
wire(Q1.pin("3"), SW);
const D2 = placeByPin("D2", "Diode:SS34", "1", SW, { rot: 270, value: "SS34" });
gnd(D2.pin("2"));
const L1 = placeByPin("L1", "Device:L", "1", P(154.94, RAIL), { rot: 90, value: "22uH", fp: "Inductor_SMD:L_Bourns_SRN6045TA" });
wire(SW, L1.pin("1"));
junction(SW);
const CSP = P(167.64, RAIL);
wire(L1.pin("2"), CSP);
stub(CSP, "up", "CSP", 5.08);
const R5 = placeByPin("R5", "Device:R", "1", P(172.72, RAIL), { rot: 90, value: "0.15R 1%", fp: FP.r1206 });
wire(CSP, R5.pin("1"));
junction(CSP);
const VB = P(185.42, RAIL);
wire(R5.pin("2"), VB);
stub(VB, "up", "VBAT", 5.08);
junction(VB);
const C3 = placeByPin("C3", "Device:C", "1", P(193.04, RAIL), { value: "22uF/10V", fp: FP.c1206 });
gnd(C3.pin("2"));
wire(VB, C3.pin("1"));
junction(C3.pin("1"));
// Off-board panel switches: J7 cuts the cell off from charger and load,
// J8 switches only the load output so charging continues with it off.
const J7 = placeByPin("J7", "Connector_Generic:Conn_01x02", "1", P(220.98, RAIL), { value: "SW_BATT", fp: FP.pico2 });
wire(C3.pin("1"), J7.pin("1"));
stub(J7.pin("2"), "left", "BATT+", 5.08);

// Battery current shunt (INA219 "BATT" position): BATT+ -> R6 -> cell. Sits after
// SW_BATT so the cell voltage still reads with the switch open.
const R6 = placeByPin("R6", "Device:R", "1", P(200.66, 68.58), { rot: 90, value: "0.1R 1%", fp: FP.r1206, textAbove: true });
stub(R6.pin("1"), "left", "BATT+", 2.54);
const cell = P(213.36, 68.58);
wire(R6.pin("2"), cell);
stub(cell, "up", "BAT_CELL", 5.08);
junction(cell);
const J5 = placeByPin("J5", "Connector_Generic:Conn_01x02", "1", P(220.98, 68.58), { value: "LiPo_1S_4.2V", fp: FP.pico2 });
wire(cell, J5.pin("1"));
gnd(wire(J5.pin("2"), P(218.44, J5.pin("2").y), P(218.44, 76.2)));

const J8 = placeByPin("J8", "Connector_Generic:Conn_01x02", "1", P(220.98, 86.36), { value: "SW_LOAD", fp: FP.pico2 });
stub(J8.pin("1"), "left", "VBAT", 5.08);
stub(J8.pin("2"), "left", "VOUT", 5.08);

const J6 = placeByPin("J6", "Connector_Generic:Conn_01x02", "1", P(246.38, 86.36), { value: "VOUT", fp: FP.pico2 });
stub(J6.pin("1"), "left", "VOUT", 5.08);
gnd(wire(J6.pin("2"), P(243.84, J6.pin("2").y), P(243.84, 93.98)));

// ---------- INA219 power monitor ----------
// SW3 (DPDT) routes the INA219 inputs to one shunt at a time:
//   SOLAR: IN+ = PV, IN- = VIN       -> panel current, bus voltage = VIN
//   BATT:  IN+ = BATT+, IN- = BAT_CELL -> battery current (+ charging / - discharging), bus = cell voltage
const SW3 = place("SW3", "Switch:SW_Slide_DPDT", 274.32, 104.14, { value: "SOLAR / BATT", fp: "Button_Switch_THT:SW_CK_JS202011CQN_DPDT_Straight" });
stub(SW3.pin("1"), "left", "PV", 5.08);
stub(SW3.pin("2"), "left", "SENSE+", 5.08);
stub(SW3.pin("3"), "left", "BATT+", 5.08);
stub(SW3.pin("6"), "right", "VIN", 5.08);
stub(SW3.pin("5"), "right", "SENSE-", 5.08);
stub(SW3.pin("4"), "right", "BAT_CELL", 5.08);

const U2 = place("U2", "Sensor_Energy:INA219AxD", 322.58, 104.14, { value: "INA219AID" });
stub(U2.pin("8"), "left", "SENSE+", 5.08);
stub(U2.pin("7"), "left", "SENSE-", 5.08);
stub(U2.pin("5"), "up", "VCC_MCU", 5.08);
gnd(wire(U2.pin("6"), P(U2.x, U2.pin("6").y + 2.54)));
stub(U2.pin("3"), "right", "SDA", 5.08);
stub(U2.pin("4"), "right", "SCL", 5.08);
// A0 = A1 = GND -> address 0x40
const aX = U2.pin("1").x + 2.54;
wire(U2.pin("1"), P(aX, U2.pin("1").y));
wire(U2.pin("2"), P(aX, U2.pin("2").y));
gnd(wire(P(aX, U2.pin("1").y), P(aX, U2.pin("2").y), P(aX, U2.pin("2").y + 2.54)));
junction(P(aX, U2.pin("2").y));

const C6 = placeByPin("C6", "Device:C", "1", P(345.44, 91.44), { value: "100nF", fp: FP.c0603 });
stub(C6.pin("1"), "up", "VCC_MCU");
gnd(C6.pin("2"));

// I2C pull-ups to the MCU's supply (fit only if the MCU board has none)
const R8 = place("R8", "Device:R", 355.6, 99.06, { value: "10k", fp: FP.r0603 });
stub(R8.pin("1"), "up", "VCC_MCU");
stub(R8.pin("2"), "down", "SDA");
const R9 = place("R9", "Device:R", 365.76, 99.06, { value: "10k", fp: FP.r0603 });
stub(R9.pin("1"), "up", "VCC_MCU");
stub(R9.pin("2"), "down", "SCL");

// I2C header to the external MCU: 1 VCC (3.3-5V), 2 SDA, 3 SCL, 4 GND
const J9 = placeByPin("J9", "Connector_Generic:Conn_01x04", "1", P(388.62, 99.06), { value: "I2C_MCU", fp: FP.pico4 });
stub(J9.pin("1"), "left", "VCC_MCU", 5.08);
stub(J9.pin("2"), "left", "SDA", 5.08);
stub(J9.pin("3"), "left", "SCL", 5.08);
gnd(wire(J9.pin("4"), P(386.08, J9.pin("4").y), P(386.08, J9.pin("4").y + 5.08)));
// M3 mounting holes (non-plated), one per board corner
for (let i = 0; i < 4; i++)
  place(`H${i + 1}`, "Mechanical:MountingHole", 302.26 + i * 12.7, 142.24, { value: "M3", fp: "MountingHole:MountingHole_3.2mm_M3" });

// VCC_MCU only comes from the header; flag it for ERC.
wire(P(375.92, 83.82), P(375.92, 86.36));
flag(P(375.92, 83.82));
LABELS.push({ name: "VCC_MCU", at: P(375.92, 86.36), ang: 0 });

// Controller
const U1 = place("U1", "SolarNode:CN3791", 114.3, 93.98, { value: "CN3791" });
stub(U1.pin("9"), "left", "VIN", 5.08);
stub(U1.pin("6"), "left", "MPPT", 5.08);
stub(U1.pin("3"), "left", "~{CHRG}", 5.08);
stub(U1.pin("4"), "left", "~{DONE}", 5.08);
stub(U1.pin("10"), "right", "DRV");
stub(U1.pin("8"), "right", "CSP", 5.08);
stub(U1.pin("7"), "right", "VBAT", 5.08);
gnd(wire(U1.pin("2"), P(114.3, U1.pin("2").y + 2.54)));

// VG bypass: 100nF between VG and VCC
const vgEnd = P(127, U1.pin("1").y);
wire(U1.pin("1"), vgEnd);
const C2 = placeByPin("C2", "Device:C", "2", vgEnd, { value: "100nF", fp: FP.c0603 });
stub(C2.pin("1"), "up", "VIN");

// Loop compensation: 120R + 220nF from COM to GND
const comEnd = P(129.54, U1.pin("5").y);
wire(U1.pin("5"), comEnd);
const R2 = placeByPin("R2", "Device:R", "1", comEnd, { value: "120R", fp: FP.r0603 });
const C4 = placeByPin("C4", "Device:C", "1", R2.pin("2"), { value: "220nF", fp: FP.c0603 });
gnd(C4.pin("2"));

// Status LEDs: red = charging (~CHRG), green = done (~DONE)
const R1 = place("R1", "Device:R", 160.02, 88.9, { value: "1k", fp: FP.r0603 });
stub(R1.pin("1"), "up", "VIN");
const D4 = placeByPin("D4", "Device:LED", "2", R1.pin("2"), { rot: 90, value: "RED", fp: FP.led });
stub(D4.pin("1"), "down", "~{CHRG}");
const D3 = placeByPin("D3", "Device:LED", "2", P(172.72, R1.pin("2").y), { rot: 90, value: "GREEN", fp: FP.led });
wire(R1.pin("2"), D3.pin("2"));
junction(R1.pin("2"));
stub(D3.pin("1"), "down", "~{DONE}");

TEXTS.push({
  at: P(40.64, 157.48),
  text: [
    "Design notes (CN3791 datasheet, Figure 1):",
    "- Solar inputs J1-J4: up to four 5V panels in parallel, each isolated by a 1N5819WS (SOD-323, 40V/1A). MPPT senses VIN after these diodes,",
    "  so each panel sits ~0.3-0.45V above the 4.6V setpoint (~4.9-5.0V, typical Vmp of a 5V panel). Panels peak at ~200-300mA each.",
    "- Charge current: ICH = 120mV / R5 = 120mV / 0.15R = 0.8A, leaving margin on the 1.0A connector contacts (R5 = 0.24R for 0.5A).",
    "- MPPT setpoint: VMPPT = 1.205V x (1 + R3/R4) = 1.205 x (1 + 28.0k/10k) = 4.58V. Charging starts once MPPT > 1.23V (VIN > 4.68V).",
    "- L1: datasheet requires L > 5 x (VCC - VBAT) uH = 16uH at 6V Voc / 2.8V batt. 22uH gives ~0.2A ripple at 6V in, 3.7V batt.",
    "- Datasheet blocking diode D1 omitted to save ~0.4V headroom: D5-D8 keep the battery out of the panels; the CN3791 then draws ~21uA",
    "  from the battery via L1 and Q1's body diode when dark (datasheet p.9). Reference D1 is intentionally unused.",
    "- Status: D4 red ON = charging, D3 green ON = charge done. Both off = no input or VIN < VBAT.",
    "- All power connectors (J1-J8) are 2-pin Micro JST 1.25 / PicoBlade-compatible (1.0A per contact); J9 I2C is the 4-pin version.",
    "  Panel-mount SPST switches plug into J7/J8. Same connector family everywhere, so check the silkscreen before plugging in.",
    "  J7 SW_BATT isolates the cell from charger and load. J8 SW_LOAD switches only VOUT (J6), so the cell keeps charging with it off.",
    "  Rate both switches >= 1A or the module's peak current, whichever is higher (battery current is charge OR load, not the sum).",
    "  With SW_BATT off in sun the CN3791 sees no battery and VBAT pulses near 4.2V: keep SW_LOAD off then.",
    "- INA219 (U2, I2C 0x40 with A0=A1=GND). SW3 selects the shunt: SOLAR = R7 (PV -> VIN), current from the panels, bus voltage = VIN;",
    "  BATT = R6 (BATT+ -> cell), + charging / - discharging, bus voltage = cell voltage (readable even with SW_BATT open).",
    "  Shunts 0.1R match the common INA219 breakout, so stock library calibration (32V/2A, PGA /8 = +/-320mV = +/-3.2A) works as-is.",
    "  J9 to MCU: 1 VCC_MCU (3.3-5V, powers U2 and pull-ups), 2 SDA, 3 SCL, 4 GND. R8/R9 10k pull-ups: omit if the MCU board has them.",
  ].join("\\n"),
});

// ---------- emit ----------
const sheetUuid = fs.readFileSync(SCH, "utf8").match(/^\t\(uuid "?([0-9a-f-]+)"?\)/m)[1];
const indent = (s) => s.replace(/\n/g, "\n\t");
function prop(name, value, x, y, { hide, justify, ang = 0 } = {}) {
  return `\t\t(property "${name}" "${value}"
			(at ${r(x)} ${r(y)} ${ang})
			${hide ? "(hide yes)\n\t\t\t" : ""}(effects
				(font
					(size 1.27 1.27)
				)${justify ? `\n\t\t\t\t(justify ${justify})` : ""}
			)
		)`;
}
function emitPart(p) {
  const { x, y, o } = p;
  // Property values may contain escaped quotes (e.g. power:GND's description).
  const libVal = (name) => (p.sym.text.match(new RegExp(`\\(property "${name}" "((?:[^"\\\\]|\\\\.)*)"`)) || [])[1];
  const libFp = libVal("Footprint") || "";
  const libDs = libVal("Datasheet") || "~";
  const libDesc = libVal("Description") || "";
  // Field angles are relative to the symbol, so counter-rotate to keep text horizontal.
  // Text is centre-justified; its width is estimated to park it beside the body.
  const w = (s) => s.replace(/~\{|\}/g, "").length * 1.1;
  // (KiCad already keeps text upright on 180-degree symbols.)
  const ang = p.rot % 180 ? (360 - p.rot) % 360 : 0;
  const pinIds = Object.keys(p.sym.pins);
  const looksVertical = pinIds.length === 2 && Math.abs(p.pin(pinIds[0]).x - p.pin(pinIds[1]).x) < 0.01;
  const side = (s, dy) => [x + 2.79 + w(s) / 2, y + dy];
  let refAt, valAt, just, hideVal;
  if (o.power) {
    refAt = [x, y]; valAt = [x, y + 3.81];
    hideVal = p.libId === "power:PWR_FLAG";
  } else if (p.libId === "SolarNode:CN3791") {
    refAt = [x - 7.62, y - 11.43]; valAt = [x + 7.62, y - 11.43];
  } else if (p.libId.startsWith("Connector")) {
    // Value beside the body, on the side away from the pins.
    const dir = p.mirror === "y" ? -1 : 1;
    refAt = [x, y - 3.81]; valAt = [x + dir * (2.54 + w(o.value) / 2), y + 3.81];
  } else if (p.libId.startsWith("Sensor_Energy")) {
    refAt = [x - 6.35, y - 11.43]; valAt = [x + 7.62, y - 11.43];
  } else if (p.libId.startsWith("Switch")) {
    refAt = [x, y - 8.89]; valAt = [x, y + 8.89];
  } else if (p.libId.startsWith("Transistor")) {
    refAt = [x - 3.81 - w(p.ref) / 2, y - 5.08]; valAt = [x - 3.81 - w(o.value) / 2, y - 2.54];
  } else if (looksVertical) {
    refAt = side(p.ref, -1.27); valAt = side(o.value, 1.27);
  } else if (o.textAbove) {
    refAt = [x, y - 5.08]; valAt = [x, y - 2.54];
  } else {
    refAt = [x, y - 3.81]; valAt = [x, y + 3.81];
  }
  const cn = p.libId === "SolarNode:CN3791";
  const props = [
    prop("Reference", p.ref, ...refAt, { hide: o.power, justify: cn ? "left" : just, ang }),
    prop("Value", o.value, ...valAt, { hide: hideVal, justify: cn ? "right" : just, ang }),
    prop("Footprint", o.fp || libFp, x, y, { hide: true }),
    prop("Datasheet", libDs, x, y, { hide: true }),
    prop("Description", libDesc, x, y, { hide: true }),
  ];
  const pins = Object.keys(p.sym.pins).map((n) => `\t\t(pin "${n}"\n\t\t\t(uuid "${uuid(`pin/${p.ref}/${n}`)}")\n\t\t)`);
  return `\t(symbol
		(lib_id "${p.libId}")
		(at ${x} ${y} ${p.rot})
${p.mirror ? `\t\t(mirror ${p.mirror})\n` : ""}		(unit 1)
		(exclude_from_sim no)
		(in_bom ${o.power || /\n\t\t\(in_bom no\)/.test(p.sym.text) ? "no" : "yes"})
		(on_board ${o.power ? "no" : "yes"})
		(dnp no)
		(uuid "${uuid(`sym/${p.ref}`)}")
${props.join("\n")}
${pins.join("\n")}
		(instances
			(project "${NAME}"
				(path "/${sheetUuid}"
					(reference "${p.ref}")
					(unit 1)
				)
			)
		)
	)`;
}
const JUST = { 0: "left bottom", 90: "left bottom", 180: "right bottom", 270: "right bottom" };
const out = [
  `(kicad_sch
	(version 20260306)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "${sheetUuid}")
	(paper "A3")
	(title_block
		(title "Solar Node Charge Controller")
		(date "2026-10-28")
		(rev "0.1")
		(comment 1 "CN3791 MPPT Li-ion charger: up to 4x 5V solar panels (diode OR) -> 1S LiPo (4.2V)")
		(comment 2 "INA219 I2C power monitor (0x40), switchable between solar input and battery")
	)
	(lib_symbols
${Object.values(SYMS).map((s) => "\t\t" + indent(s.text.replace(/^\t/, ""))).join("\n")}
	)`,
  ...NOCONNECTS.map((n) => `\t(no_connect\n\t\t(at ${n.x} ${n.y})\n\t\t(uuid "${uuid(`nc/${n.x},${n.y}`)}")\n\t)`),
  ...JUNCTIONS.map((j) => `\t(junction\n\t\t(at ${j.x} ${j.y})\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "${uuid(`junction/${j.x},${j.y}`)}")\n\t)`),
  ...WIRES.map(([a, b]) => `\t(wire\n\t\t(pts\n\t\t\t(xy ${a.x} ${a.y}) (xy ${b.x} ${b.y})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "${uuid(`wire/${a.x},${a.y}/${b.x},${b.y}`)}")\n\t)`),
  ...TEXTS.map((t) => `\t(text "${t.text}"\n\t\t(exclude_from_sim no)\n\t\t(at ${t.at.x} ${t.at.y} 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "${uuid(`text/${t.at.x},${t.at.y}`)}")\n\t)`),
  ...LABELS.map((l) => `\t(label "${l.name}"\n\t\t(at ${l.at.x} ${l.at.y} ${l.ang})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify ${JUST[l.ang]})\n\t\t)\n\t\t(uuid "${uuid(`label/${l.name}/${l.at.x},${l.at.y}`)}")\n\t)`),
  ...PARTS.map(emitPart),
  `\t(sheet_instances
		(path "/"
			(page "1")
		)
	)
	(embedded_fonts no)
)
`,
];
fs.writeFileSync(SCH, out.join("\n"));

// Project symbol library + table so the CN3791 is reusable from the symbol chooser.
fs.writeFileSync(
  path.join(PROJ, "SolarNode.kicad_sym"),
  `(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "kicad_symbol_editor")\n\t(generator_version "10.0")\n${CN3791}\n)\n`
);
const tbl = path.join(PROJ, "sym-lib-table");
if (!fs.existsSync(tbl))
  fs.writeFileSync(
    tbl,
    `(sym_lib_table\n\t(version 7)\n\t(lib (name "SolarNode")(type "KiCad")(uri "\${KIPRJMOD}/SolarNode.kicad_sym")(options "")(descr "Project-specific symbols"))\n)\n`
  );

for (const p of PARTS.filter((p) => !p.o.power))
  console.log(p.ref.padEnd(4), p.libId.padEnd(34), String(p.o.value).padEnd(14), Object.entries(p.sym.pins).map(([n]) => `${n}@${JSON.stringify(p.pin(n))}`).join(" "));
console.log(`${PARTS.length} symbols, ${WIRES.length} wires, ${LABELS.length} labels, ${JUNCTIONS.length} junctions`);
