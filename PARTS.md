# Parts checklist

What's needed to build the solenoid circuit in [`HARDWARE.md`](HARDWARE.md), for a
12V 1.7A solenoid.

## Needed

- [ ] **IRLZ44N MOSFET:** through-hole TO-220. Buy 3 or more so you have spares.
  - [DigiKey](https://www.digikey.com/en/products/detail/infineon-technologies/IRLZ44NPBF/811808)
  - [Newark](https://www.newark.com/infineon/irlz44npbf/n-channel-mosfet-55v-47a-to-220ab/dp/63J7709)
- [x] **Flyback diode:** 1N4007 is acceptable, 1N5408 is preferred.
- [ ] **Barrel jack adapters:** two with screw terminals, one per supply. Check that
  they fit your plugs, commonly 5.5 × 2.1mm.
- [ ] **12V supply:** 3A or more, for the solenoid.
- [ ] **5V supply:** 2A or more for SG90s, or 4A or more for MG996Rs, for the servos.
- [ ] **Resistors:** one 220Ω (100Ω is fine too) and one 10kΩ.
- [ ] **18–20 AWG wire:** for the solenoid's power loop.
- [ ] **Project basics:** Arduino, USB data cable, two servos, breadboard and jumper
  wires.
- [ ] **Multimeter:** for checking the 12V supply's polarity, looking for shorts and
  finding out why something isn't working.

## Strongly recommended

- [ ] **Inline fuse for the 12V line:** 3A fast-blow with a holder, placed close to
  the supply's + output.
- [ ] **470–1000µF capacitor, rated 10V or higher:** goes across the 5V servo rail.
  It's polarized: the stripe marks the − leg, which goes to ground.

## Depending on how you build it

- [ ] **If you solder:** soldering iron, solder, perfboard and heat-shrink tubing.
- [ ] **If you'd rather not solder:** screw terminal blocks or lever connectors, such
  as Wago, for the heavy wires.
- [ ] **If it goes outdoors:** a weatherproof enclosure and a cable gland to seal
  where the wires enter it.
- [ ] **If the solenoid is a water valve:** hose fittings that match its threads, and
  thread seal tape. Keep the electronics well away from any leaks.

## For future projects

- [ ] **MOSFET kit:** the
  [EEEEE 70-piece kit](https://www.amazon.com/EEEEE-Transistor-Assortment-Channel-RFP30N06LE/dp/B09K3T5LSN)
  has logic-level RFP30N06LE and 2N7000 parts. It doesn't include the IRLZ44N, and
  its IRFZ44N isn't a substitute.
- [ ] **Resistor assortment**

## Before first power-up

Use the multimeter in continuity mode to check that 12V + and ground aren't shorted
together. Then follow the test in Stage 4b of [`HARDWARE.md`](HARDWARE.md).
