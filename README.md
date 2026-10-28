# Solar Node Charge Controller

A small solar charger board for a single-cell (1S) Li-ion/LiPo battery. It is meant to keep a low-power node (a LoRa/mesh radio, sensor or similar module) running off solar. Up to four 5V panels feed a CN3791 MPPT buck charger. A switched output powers the module, and an INA219 reports voltage and current to an external MCU over I2C.

Designed in KiCad 10.

> **Status:** the schematic is complete and passes ERC. The PCB is a **placement draft** (60 × 29 mm, two layers, not routed). Nothing has been built or tested yet.

<p align="center">
  <img src="docs/images/pcb-iso.png" alt="3D render of the board, placement draft" width="720">
</p>

## Features

- **Solar input:** up to four 5V panels in parallel (JST-PH), each isolated by its own 1N5819 Schottky so a shaded or unplugged panel doesn't drag the others down.
- **MPPT charging:** [CN3791](https://naylampmechatronics.com/img/cms/001216/CN3791.PDF) PWM buck charger with constant-voltage MPPT set to 4.58V input. Charges at 1.0A to 4.2V (CC/CV, trickle charge for deeply discharged cells, automatic recharge).
- **Battery and load switching:** connectors for two panel-mount switches. **SW_BATT** disconnects the battery from everything. **SW_LOAD** cuts only the output, so the battery keeps charging.
- **Output:** VOUT connector (JST-PH) that powers the module from the battery.
- **Power monitoring:** [INA219](https://www.ti.com/lit/ds/symlink/ina219.pdf) at I2C address 0x40. A slide switch selects whether it measures the solar input or the battery (bidirectional current plus voltage).
- **Status LEDs:** red while charging, green when charging is done.

## Schematic

[![Schematic](docs/images/schematic.svg)](docs/images/schematic.svg)

The schematic follows the CN3791 datasheet's typical application circuit (Figure 1), with these changes:

| Item | Value | Why |
|---|---|---|
| Charge current | 1.0A (R5 = 0.12Ω) | I<sub>CH</sub> = 120mV / R5. Use 0.24Ω for 0.5A with small cells. |
| MPPT setpoint | 4.58V at VIN (R3/R4 = 28.0k/10k) | V<sub>MPPT</sub> = 1.205V × (1 + R3/R4). The panels sit one diode drop higher (~4.9–5.0V), about the max-power voltage of a typical 5V panel. |
| Blocking diode D1 | omitted | The input diodes already stop the battery feeding back into the panels. Leaving D1 out saves ~0.4V of headroom; the trade-off is ~21µA of battery drain in the dark. |
| Inductor | 22µH, Bourns SRN6045TA | Meets the datasheet's L > 5 × (VCC − VBAT) µH, with ~0.2A ripple. |
| Input diodes | 1N5819 (40V/1A) | A single panel at full charge current carries ~0.9A through its diode. |

## PCB

<p align="center">
  <img src="docs/images/pcb-top.png" alt="Top view of the board placement draft" width="720">
</p>

| Area | Parts |
|---|---|
| Left edge | Solar inputs J1–J4, each with its 1N5819 (D5–D8). I2C header J9 in the bottom-left corner. |
| Top middle | Buck power stage in current-flow order: R7, C1/C5, Q1, D2, L1, R5, C3 |
| Middle | CN3791 (U1) with its support parts, status LEDs, SOLAR/BATT selector SW3 |
| Right middle | INA219 (U2), I2C pull-ups, battery shunt R6 |
| Right edge | SW_BATT/SW_LOAD switch leads (J7/J8, JST-XH), battery J5 and VOUT J6 (JST-PH) |

Still to do: routing with a ground pour, mounting holes, silkscreen cleanup, then fabrication outputs.

## Connectors

| Ref | Connector | Pin 1 | Pin 2 | Notes |
|---|---|---|---|---|
| J1–J4 | JST-PH 2.0mm | Panel + | GND | 5V solar panels, any combination of 1–4 |
| J5 | JST-PH 2.0mm | Battery + | GND | 1S Li-ion/LiPo, 4.2V |
| J6 | JST-PH 2.0mm | VOUT | GND | Battery voltage out to the powered module, through SW_LOAD |
| J7 | JST-XH 2.5mm | VBAT (charger) | BATT+ (battery) | SW_BATT: panel-mount SPST switch, rated ≥1A or the module's peak current |
| J8 | JST-XH 2.5mm | VBAT | VOUT | SW_LOAD: panel-mount SPST switch, same rating |
| J9 | 2.54mm header, 1×4 | VCC (3.3–5V) | SDA | Pin 3 = SCL, pin 4 = GND. VCC comes from the MCU and powers the INA219. |

The switch leads use JST-XH, a different series from the PH power connectors, so a switch lead can't be plugged into a power socket by mistake.

**Operating note:** if SW_BATT is off while the panels are in sun, the charger sees no battery and VBAT pulses around 4.2V. Keep SW_LOAD off in that state.

## Power monitor (INA219)

- **Address:** 0x40 (A0 = A1 = GND).
- **Shunts:** both are 0.1Ω, the same as common INA219 breakout boards, so the default 32V/2A calibration in the usual libraries (e.g. Adafruit_INA219) works unchanged: about ±3.2A full scale, 0.8mA resolution.
- **Pull-ups:** R8/R9 are 10k I2C pull-ups to the MCU's VCC. Leave them off if the MCU board already has pull-ups.

| SW3 position | Shunt | Current | Bus voltage |
|---|---|---|---|
| SOLAR | R7, between the PV bus and VIN | Panel current, always ≥ 0 | VIN (panel voltage minus the diode drop) |
| BATT | R6, between BATT+ and the cell | Positive while charging, negative while discharging | Cell voltage, readable even with SW_BATT off |

The MCU can't sense SW3's position. Firmware has to know which position is set, or infer it from the readings.

## Repository layout

```
SolarNodeChargeController/      KiCad project: .kicad_pro, .kicad_sch, .kicad_pcb
  SolarNode.kicad_sym           project symbol library (CN3791)
  sym-lib-table
tools/
  gen-schematic.js              generates the schematic (Node)
  place-pcb.py                  builds the placement draft (KiCad Python / pcbnew)
docs/images/                    images used in this README
CLAUDE.md                       design decisions and working notes
```

The schematic and the placement draft are generated by scripts in `tools/`, and checked with `kicad-cli` ERC/DRC (including schematic parity). See [CLAUDE.md](CLAUDE.md) for the full design rationale and workflow. Generated outputs (`output/`: BOM, reports, fab files) are not tracked.

Regenerating the images in `docs/images/`:

```bash
kicad-cli sch export svg -o docs/images SolarNodeChargeController/SolarNodeChargeController.kicad_sch
kicad-cli pcb render --side top --width 1600 --height 800 --quality high --zoom 1.75 -o docs/images/pcb-top.png SolarNodeChargeController/SolarNodeChargeController.kicad_pcb
kicad-cli pcb render --width 1600 --height 1000 --quality high --perspective --rotate "-40,0,-25" -o docs/images/pcb-iso.png SolarNodeChargeController/SolarNodeChargeController.kicad_pcb
```

(The schematic export is named `SolarNodeChargeController.svg`; rename it to `schematic.svg`.)
