# Changelog

Changes to the Solar Charge Module that matter to someone building or using the board. Versions match the release tags and the label on the back of the board.

## Unreleased

Changes on `main` since the v1.1 release files. The solar input column and the back silkscreen differ; don't mix these files with the released Gerbers, BOM or placement file.

- The input diodes D5–D8 are 1N5819W in SOD-123 (was 1N5819WS in SOD-323), so each solar input is good for 0.5 A instead of about 0.3 A. To fit them, J1, J2 and J4 move 0.45 mm left and J3 0.3 mm; J2 is also 0.2 mm lower. The mounting holes and the other connectors don't move.

- The back label reads "SNAP Power Controller v1.1 / by JaisorGadgets - Nov. 14, 2026", the project's new name.
- Printed under it: check polarity; battery 1S Li-ion 4.2 V only; solar 5–6 V panels, 20 V max, 0.5 A max per input; load 1 A max; and a notice that the board is provided as is, with no warranty, and liability limited to the purchase price.
- The README lists the same limits under Safety, and gives the board's dimensions.

## v1.1 (2026-11-09)

Not built or tested yet. ERC reports 0 violations; DRC reports 0 violations, 0 unconnected items and 0 schematic parity issues. The test results in the README are from v1.0 boards.

v1.1 is not a drop-in replacement for v1.0. The board outline, the mounting holes, the I2C connector pinout and the power monitor's type and address all change; see **Upgrading from v1.0**.

### Power monitor

- A three-channel INA3221 (U2, VQFN-16) replaces the INA219. It reads the battery (CH1, shunt R6), all panels together (CH2, shunt R7) and panel 1 alone (CH3, new 0.1 Ω shunt R10 between J1 and D5) at the same time.
- The SOLAR/BATT slide switch SW3 is removed. The INA219 could only measure the shunt SW3 selected, and firmware couldn't tell which one that was.
- The I2C address is 0x42 (was 0x40), the INA3221 default in Meshtastic and MeshCore.

### Protection and charging

- Q2, an AO3401A P-channel FET at the battery connector, blocks a reversed cell. With the cell the right way round it costs about 60 mV at 0.8 A.
- The MPPT set point is 4.42 V (R3 = 26.7k), down from 4.58 V (28.0k), so hot panels keep more of their output. Modeled for a 5 V panel: 99% of maximum power at 25 °C and 84% at 65 °C, against 100% and 71% before. 4.42 V is below the CN3791's specified 4.5 V minimum input; the README explains why it is kept and gives the in-spec value for 6 V panels (R3 = 30.1k, 4.83 V).
- JP1, an open solder jumper on the top, sits in the status LEDs' supply. The LEDs stay off and draw nothing until it is bridged.

### Connectors

- J7 (SW_BATT) and J8 (SW_LOAD) are 2.54 mm pin headers instead of Micro JST 1.25. An unused switch position can take a jumper cap, and a switch plug can't be mistaken for a power connector.
- J9 (I2C) is now 1 VCC, 2 GND, 3 SCL, 4 SDA, the order of the common red/black/yellow/white cable. v1.0 has SDA on pin 2 and GND on pin 4.
- J9 moves to the left end of the board. The battery and VOUT connectors (J5, J6) sit under the inductor, and J7 and J8 are at the right end.

### Board

- The outline is 52 × 29 mm (was 56.5 × 29 mm), with the same 2 mm corner chamfers.
- The four M3 holes are still 4 mm in from each edge, so the hole pattern is 44 × 21 mm (was 48.5 × 21 mm).
- The copper is drawn by hand from fixed coordinates (`tools/draw-routes.py`) instead of auto-routed, so the tools reproduce the board exactly. Only 25 mm of track is left on the bottom layer, which is one ground plane over about 87% of the board, with ground stitching vias on a 3 mm grid.
- Minimum track width is 0.2 mm (was 0.25 mm) on a few sense lines that pass between pads.

### Silkscreen

- `+` and `-` marks at the solar (J1–J4), battery (J5) and VOUT (J6) connectors.
- `SW_BATT` and `SW_LOAD` printed above the switch headers, pin names beside J9 on the back, and "Solar Charge Module v1.1" on the back.
- J9 has no reference designator, only the `I2C` label.

### Documentation and licence

- The hardware design is licensed under CERN-OHL-P-2.0 and the scripts in `tools/` under MIT.
- The README gains a Safety section, the first test results (from v1.0 boards) and corrected XIAO I2C pins (D6 and D7).

### Upgrading from v1.0

- **Enclosure:** the board is 4.5 mm narrower and the two hole columns are 4.5 mm closer together. Mounts made for v1.0 won't fit.
- **I2C cable:** a cable wired for v1.0's J9 puts SDA and GND on the wrong pins. Don't move cables between v1.0 and v1.1 boards without checking.
- **Firmware:** set it up for an INA3221 at 0x42 instead of an INA219 at 0x40. Anything else at 0x42 on the bus will clash.
- **Switch plugs:** J7 and J8 need 2.54 mm plugs or jumper caps.

### Earlier v1.1 files

A v1.1 release was published on Nov. 5, 2026 and withdrawn. It was the v1.0 board with polarity marks added, and one early set of its files had J5 and J6 swapped by mistake. Discard any v1.1 files downloaded before Nov. 9, 2026.

## v1.0 (2026-11-05)

First release: a CN3791 MPPT Li-ion charger with an INA219 power monitor, for solar mesh nodes.

- 56.5 × 29 mm, 2 layers, four M3 holes
- Up to four 5 V panels, 0.8 A charge current, 4.58 V MPPT set point
