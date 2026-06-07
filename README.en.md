[Русский](README.md) · **English** · [Deutsch](README.de.md) · [Español](README.es.md) · [中文](README.zh.md)

# Creality Space Pi X4 Lite - firmware flasher (90 °C mod)

Cross-platform (Windows / macOS / Linux) flasher for the **Creality Space Pi X4 Lite**
filament dryer. It can:

- **raise the maximum temperature from 75 to 90 °C** (167 → 194 °F, minimum drops to 1 °C / 33.8 °F),
- **calibrate** the sensor reading to your unit,
- **revert to factory firmware** at any time.

It is **a single self-contained file `flash.py`** - all firmware images are embedded in
it, nothing else to download. The UI is in **5 languages** (RU / EN / DE / ES / 中文),
driven by digits only, after writing, the flasher **reads the firmware back and verifies
it byte-for-byte**, and prints the ST-Link wiring in the console. Flashing goes over SWD
via [pyOCD](https://pyocd.io/) (`pip install pyocd`, default) or
[OpenOCD](https://openocd.org/). The board MCU is **GD32F303CBT6** (Cortex-M4, software
compatible with STM32F303).

<p align="center">
  <img src="images/proof.JPG" alt="Dryer display showing 90 °C" width="380">
  <img src="images/proof2.JPG" alt="Thermometer at the heater outlet - 102 °C" width="380"><br>
  <em>The display shows the working 90 °C (chamber front). Right at the heater outlet it's 102 °C, the PTC heaters output about 120 °C max (depending on the calibration offset), then start clicking off.</em>
</p>

---

## ⚠️ SAFETY - read before connecting

> **The simplest and safest way is to power the board from the ST-Link 3.3 V pin, with no
> 220 V and no separate 5 V supply.** Then there is no mains at all. The current board
> revision has galvanic isolation, so the ST-Link can be connected even with 220 V applied
> (see [“Flashing under 220 V”](#flashing-under-220-v-advanced-at-your-own-risk)), but for
> ordinary flashing that isn't needed.

**How to open and wire (recommended way, no 220 V):**

1. Remove the adhesive feet on the bottom to reach the case screws. **Use a hairdryer and alcohol** to peel the adhesive off cleanly, and stick the feet onto tape so dust doesn't settle on them.
2. Four wires ST-Link → board: **SWDIO, SWCLK, GND** and **3.3V → the board's 3.3 V rail (MCU VDD)**.
3. **RST** is not needed (it would cause an endless reboot) - reset is done in software.
4. **Do not apply 220 V.** With 3.3 V only the **display stays dark - that's normal**
   (its power/backlight is not on the 3.3 V rail), it is not needed for SWD flashing.

**Important about 3.3 V:**

- the `3.3V` pin on the ST-Link must be an **output** - on cheap clones it is, on a genuine
  ST-Link the same pin is `VTREF` (a sense input) and does not supply power,
- feed it strictly to the **3.3 V rail (MCU VDD)** - **5 V there will kill the chip** (max ~3.6 V),
- if the board is not detected or the voltage sags, the clone can't supply enough current,
  then power **5 V into the board's 5 V input** (it feeds the on-board 3.3 V regulator).

The mod removes the factory temperature limit, use at your own risk. **The manufacturer/seller
warranty is definitely voided.** The dryer's plastic housing handles this temperature easily,
it's built for it. Don't leave the dryer unattended during the first runs.

### Flashing under 220 V (advanced, at your own risk)

Sometimes it's convenient to flash/debug **without disconnecting 220 V** (e.g. to read
the temperature live while heating). This is safe **only if the digital side is
galvanically isolated from the mains**.

**This board has galvanic isolation:**

- power comes from an **isolated AC-DC module with a transformer** (35 V secondary caps),
- the heaters are switched through **optocouplers** (EL3063 → triac) - an optocoupler
  exists precisely to break the “mains ↔ MCU” link,
- there is a **Y-capacitor** across the isolation barrier near the module.

So the ST-Link can be connected directly under 220 V. If your board is a different revision,
the isolation is easy to re-check with a multimeter:

1. **Mains off:** continuity between **GND (at SWD)** and both mains-input pins (L and N) →
   should read **open / megohms** (no low-ohm path = isolated).
2. **(carefully) mains on:** AC voltage between the board GND and the wall earth → an isolated
   board shows **~0 to a few volts** (Y-cap leakage), a non-isolated one shows tens/hundreds of volts.

Live flashing under 220 V is possible. Extra safety margin: a **laptop on battery** (charger
unplugged). If your revision happens to lack isolation, the cost of a mistake is a dead
laptop/board or an electric shock, so when in doubt power **3.3 V from the ST-Link** (or 5 V
into the 5 V input to light the display) **without 220 V** - as described at the top of the safety section.

---

## What you need

- **SWD debugger:** ST-Link V2 (cheapest and most common), or CMSIS-DAP, or J-Link.
- **Wires** to the SWD pads on the board (look for the `J25`/SWD pad: SWDIO, SWCLK, GND).
- **Python 3.7+** and a flashing tool - **pyOCD** (recommended) or OpenOCD.

### Installing the flashing tool

**Recommended - pyOCD** (one command, no separate binary):

```bash
pip install pyocd
```

That's it. The CMSIS pack for the GD32F303 chip is **installed automatically** on first
flash (needs internet once). Nothing else to download or add to PATH.

**Alternative - OpenOCD** (if already installed): pass `--backend openocd`. Install:
macOS `brew install open-ocd`, Linux `sudo apt install openocd`,
Windows - [xpack-openocd](https://github.com/xpack-dev-tools/openocd-xpack/releases) on PATH
(or `--openocd C:\path\openocd.exe`).

> **Windows + ST-Link:** both pyOCD and OpenOCD talk to the ST-Link via libusb - if the probe
> isn't visible, it needs the WinUSB driver (via [Zadig](https://zadig.akeo.ie/)).

By default the flasher picks the backend itself: pyOCD if present, otherwise OpenOCD. If
neither is found, the flasher **offers to install pyOCD** with one command
(`pip install pyocd`) right from the menu.

---

## Wiring (photos)

Recommended way - power the board from **3.3 V on the ST-Link pin** (no 220 V). Four wires:
**SWDIO, SWCLK, GND** and **3.3V → the board's 3.3 V rail (MCU VDD)**, RST not needed.

<p align="center">
  <img src="images/board.JPG" alt="ST-Link connected to the board over SWD" width="520"><br>
  <em>ST-Link V2 → SWD (SWDIO / SWCLK / GND) and 3.3 V to the board's 3.3 V rail.</em>
</p>

**External 5 V USB is NOT needed for flashing** - the chip is flashed from the ST-Link's
3.3 V. The display stays dark with that power, and that's fine: it isn't needed to write
firmware over SWD.

5 V is needed **only if you are developing the firmware** and want the **display to light up**
(to see the UI live). In that case additionally supply 5 V, as in the photo:

<p align="center">
  <img src="images/board-5v.JPG" alt="Applying external 5 V to light the display" width="520"><br>
  <em>Optional: external 5 V USB - to bring the display to life (only needed for firmware development).</em>
</p>

---

## Usage

The firmware images are **embedded inside `flash.py`** - it's a single self-contained file,
the `firmware/` folder isn't required to run (it's in the repo only for verification/transparency).

Simple mode - run and press digits:

```bash
python3 flash.py        # or ./flash.py (the file is executable)
```

Steps (all digits):

```
1. Language:  1) Русский  2) English  3) Deutsch  4) Español  5) 中文

2. What to flash?
     1) 90 °C / 194 °F (raise the maximum)
     2) Revert to factory (75 °C / 167 °F)
     0) exit

3. Calibration (asked ONLY for 90 °C, not for the revert):
     Offset, °C [Enter=+11 / 0 / e.g. 9.5]      (+11 °C ≈ +20 °F)

4. Safety:  1=yes (flash)  0=cancel
```

Sequence `Enter, Enter, Enter, 1` (language → 90 °C → calibration +11 → confirm) - and done.

Without the menu (CLI):

```bash
python3 flash.py --lang en                 # UI language (ru|en|de|es|zh)
python3 flash.py --firmware mod90c --calibrate 11   # 90 °C mod
python3 flash.py --firmware stock          # revert to factory 75 °C
python3 flash.py --firmware my_dump.bin    # an arbitrary firmware by path
```

Handy options:

```bash
python3 flash.py --list                    # show available firmware
python3 flash.py --speed 300               # lower SWD speed on link errors
python3 flash.py --dump backup.bin         # FIRST back up the current firmware!
python3 flash.py --build-only out.bin      # build the .bin without flashing (test without the board)
python3 flash.py --backend openocd         # use OpenOCD instead of pyOCD
```

**Tip:** before the first flash it's worth backing up the factory firmware of your specific
board: `python3 flash.py --dump my_factory_backup.bin`. Board revisions differ - your own
backup always restores everything.

### Testing the flasher without a board

You can confirm everything works without connecting anything:

```bash
python3 flash.py --list                                  # does it see the firmware
python3 flash.py --help                                  # all options
# build a calibrated .bin and check that exactly 1 byte changes:
python3 flash.py --firmware mod90c --calibrate 11 --build-only /tmp/t.bin
cmp -l firmware/mod_90c.bin /tmp/t.bin                   # should be 1 line (the C1 address)
```

`--build-only` doesn't touch the board. Real flashing is only possible with a connected
debugger and **220 V removed** (see the safety section).

---

## Temperature calibration

The sensor is **non-linear**: when cold it reads nearly right, but **under heating it reads
low** - the hotter, the more. Calibration adds a constant offset that should be tuned to the
**working point (~90 °C)**.

**Recommended offset `+11 °C` (≈ +20 °F)** - here's why:

| | without calibration | with `+11 °C` |
|---|---|---|
| cold (room ~23 °C) | display ~23 °C (correct) | display ~34 °C (reads high) |
| heating to a real 90 °C | display only ~79 °C | display ~90 °C (correct) |

Without the offset the display sticks at ~79 °C, the regulator thinks it's “under-heating”
and keeps driving the PTC heaters → the thermal cutoff trips, causing **constant clicking**
and low/false readings. With `+11` a real 90 °C is shown and regulated correctly - `90 = 90`
(at the cost of accuracy when cold, which doesn't matter - you dry hot).

In the interactive menu just press **Enter** (applies +11). You can enter your own number -
but around **+11** is usually what's needed for 90 °C. The offset accepts **fractional**
values (e.g. `10.5` or `11.3`) and **negative** ones - if the display reads high instead
(e.g. `-3`, limit ±30 °C).

> The offset is in **°C** (the firmware's internal unit). For a thermometer in °F: convert the
> difference to °C (divide by 1.8). E.g. display 174 °F, thermometer 194 °F → 20 °F difference
> → `20 / 1.8 ≈ 11` → offset **11**.

**If you hear clicking around ~90 °C** - increase the offset by a couple of degrees (e.g. to
`+12…+13`). The higher the offset, the earlier the regulator cuts the heater, so the heater
outlet doesn't reach the actual ~120 °C and the bimetal cutoff stops clicking. The cost is
the real chamber temperature being a couple of degrees below the setpoint (usually acceptable).

**How to measure the offset for your unit:**

1. Insert a thermometer (thermocouple) into the **front PTFE-tube hole**.
2. Heat the chamber and let the temperature settle.
3. Compare what the **dryer** shows and what the **thermometer** shows.
4. Offset = `thermometer − display`. Example: display 79, thermometer 90 → offset **+11**.

**How to apply:**

```bash
python3 flash.py --firmware mod90c --calibrate 11    # +11 °C (recommended)
python3 flash.py --firmware mod90c --calibrate 0     # no calibration (factory)
```

or just `python3 flash.py` - the interactive menu asks for the offset separately
(Enter = recommended +11, `0` = no calibration, or your own number).

The offset is shared by **both chambers** (one common sensor constant is used). After
flashing it's worth checking with a thermometer again and reflashing with a refined value if needed.

> Technically the calibration changes one float constant `C1` (`T = ADC·K − C1`, factory
> `C1 = 50.0`) to `50.0 − offset`. Details - in [`docs/PATCHES.md`](docs/PATCHES.md) (Russian).

---

## Clicking and the temperature gradient - this is normal

While drying you'll hear **clicking** near the heater, and the temperature at the back wall
and at the front will differ noticeably. This is **normal behavior**, not a fault:

- **Back wall (hot-air outlet):** ~**120 °C / 248 °F**. This is the heater's own thermal limit -
  reaching ~120 °C (248 °F) it switches off, cools to ~115 °C (239 °F) and turns back on.
  Hence the clicking (a 120 ↔ 115 cycle) - the heater's thermal protection, not a firmware bug.
- **Chamber front (where the thermometer / filament is):** ~**90 °C / 194 °F**. This is the
  working temperature, the regulation goes by it - and it's what the display shows (correct after calibration).
- **Front/back difference:** about **30 °C (54 °F)**, i.e. the air at the back wall is roughly
  **~33 % hotter** than at the front (equivalently: the front is ~25 % cooler than the outlet).
  This is a normal temperature gradient of a flow-through chamber.

In other words: it's not a “firmware glitch” that clicks, but the heater at its limit near the
outlet, while the front holds the set 90 °C (194 °F).

**If the clicking bothers you** - it can be removed by **increasing the calibration offset**
(e.g. `+12…+13` instead of `+11`): the regulator cuts the heater a bit earlier, the outlet
won't reach ~120 °C, and the bimetal cutoff won't trip. The real temperature will then be a
couple of degrees below the setpoint. See [“Temperature calibration”](#temperature-calibration).

---

## Two firmware images - the difference

| File | Max t | For whom |
|------|:------:|------|
| `firmware/mod_90c.bin` | 90 °C / 194 °F | raise the limit to 90 °C |
| `firmware/stock_factory_75c.bin` | 75 °C / 167 °F | revert to factory |

### About E4 and safety

**E4** is a sensor/heater fault code. The mod **does not strip E4 protection entirely**: if you
actually disconnect/short the temperature sensor - **E4 still triggers** and heating is cut
(verified: disconnect the sensor → the error appears).

What the mod does relax is the **under-heat watchdog**: the factory firmware raised E4 if the
temperature didn't reach **85 % of the setpoint** (`0.85 × 90 = 76.5 °C`), and heating clamped
at 75 °C never reached that threshold → **permanent E4**. The mod removes exactly this false
trigger so that 90 °C can be reached. The hardware protection also remains - the PTC heaters
are self-limiting by their construction temperature.

---

## What exactly the mod changes (for the curious)

The mod is byte patches of the factory firmware (128 KB, loaded at `0x08000000`). The full
map is in [`docs/PATCHES.md`](docs/PATCHES.md) (Russian). In short:

- target-temperature clamps `75 → 90 °C` and `45 → 1 °C` (zones 1 and 2),
- widening the setpoint range in the menu to 90,
- removing the displayed/regulated temperature clamp at 80.0 °C,
- redirecting the under-heat watchdog away from the E4 handler (sensor-fault E4 stays intact).

The sensor function and setpoint regulation are **untouched** - heating switches off on reaching
the target as usual.

> Want to dig deeper / develop the firmware (custom calibration, fan speed, UI)? Notes on the
> board and the reverse engineering are in [`docs/REVERSE.md`](docs/REVERSE.md) (Russian).

---

## If something goes wrong

- **Probe not visible / `No available debug probes`** → check the cable and driver
  (Windows: WinUSB via [Zadig](https://zadig.akeo.ie/)), lower `--speed` to `300` or `200`.
- **`unable to connect` / `init mode failed`** → the board isn't powered from 5 V/3.3 V,
  poor SWDIO/SWCLK/GND contact, or the speed is too high.
- **pyOCD: `Target type ... not found`** → the pack didn't install in time, run manually
  `pyocd pack install gd32f303cb` (needs internet), then retry.
- **pyOCD misbehaves on a particular board** → switch to OpenOCD: `--backend openocd`.
- **Wrong firmware flashed / board acts weird** → flash `stock` (or your backup). Flashing
  won't brick the board - SWD is always available.

---

## Disclaimer

A hobby project, not affiliated with Creality. Removing the temperature limit and any
modifications are **at your own risk**. The authors are not responsible for damage to
equipment, property or injury. Follow the electrical-safety rules in the section above.

---

## License

The flasher is distributed under the **[GNU GPL v3](LICENSE)** © 2026 Alexey Verhogladov.
The firmware images are byte modifications of the factory Creality image, provided “as is”
for repair/research, responsibility for their use is on the user.

---

## 💚 Support

The project is free and made out of enthusiasm. If it helped - thanks for the support (USDT):

| Network | Address |
|------|-------|
| USDT · **TRC20** | `TYLmBvdxL8t9ziyZiFp3jcHwQbAsZR5haZ` |
| USDT · **TON** | `UQCnVND-uBgkWIAD1UP14tsN8239KE5BTOfKSJmg-0XqrN-k` |
| USDT · **ERC20** | `0xa61dcA98A86D84883Ddb3d62aA7F008f157c8eFF` |
