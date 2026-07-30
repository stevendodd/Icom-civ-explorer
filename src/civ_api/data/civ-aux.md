# ICOM CI-V Auxiliary Data Reference

Unified reference for all supported Icom radios. Shared encoding is documented
once; radio-specific differences are called out in sub-tables.

**Supported radios:** IC-705, IC-7100, IC-7300, IC-7300 MK2, IC-7610, IC-7760, IC-9700.

---

## Operating Frequency

**Commands:** `00`, `03`, `05`, `1C 03`

| Byte | 1 | 2 | 3 | 4 | 5 |
|------|---|---|---|---|---|
| Data | XX | XX | XX | XX | XX |

| Byte | Digit | Range |
|------|-------|-------|
| 1 | 10 Hz | 0 ~ 9 |
| 2 | 1 Hz | 0 ~ 9 |
| 3 | 1 kHz | 0 ~ 9 |
| 4 | 100 Hz | 0 ~ 9 |
| 5 | 100 kHz | 0 ~ 9 |
| 6 | 10 kHz | 0 ~ 9 |
| 7 | 10 MHz | 0 ~ 9 |
| 8 | 1 MHz | 0 ~ 9 |
| 9 | 1 GHz | 0 ~ 1 |
| 10 | 100 MHz | 0 ~ 4 |

> BCD encoding, little-endian (LSB first). Example: 144.000000 MHz -> `00 00 00 44 01`.

**Radio-specific differences:**

| Radio | 1 GHz digit | 100 MHz digit | Notes |
|-------|-------------|---------------|-------|
| IC-9700 | 0 ~ 1 | 0 ~ 4 | VHF/UHF/SHF |
| IC-705 | 0 (fixed) | 0 ~ 4 | HF/VHF/UHF |
| IC-7100 | 0 (fixed) | 0 ~ 4 | HF/VHF/UHF |
| IC-7300 | 0 (fixed) | 0 ~ 3 | HF/50MHz |
| IC-7300 MK2 | 0 (fixed) | 0 ~ 3 | HF/50MHz |
| IC-7610 | 0 (fixed) | 0 ~ 3 | HF/50MHz |
| IC-7760 | 0 (fixed) | 0 ~ 3 | HF/50MHz |

---

## Operating Mode

**Commands:** `01`, `04`, `06`

| Byte | 1 | 2 |
|------|---|---|
| Data | XX | XX |

**Byte 1 -- Operating Mode:**

| Value | IC-9700 | IC-705 | IC-7100 | IC-7300 | IC-7300 MK2 | IC-7610 | IC-7760 |
|-------|---------|--------|---------|---------|-------------|---------|---------|
| `00` | LSB | LSB | LSB | LSB | LSB | LSB | LSB |
| `01` | USB | USB | USB | USB | USB | USB | USB |
| `02` | AM | AM | AM | AM | AM | AM | AM |
| `03` | CW | CW | CW | CW | CW | CW | CW |
| `04` | RTTY | RTTY | RTTY | RTTY | RTTY | RTTY | RTTY |
| `05` | FM | FM | FM | FM | FM | FM | FM |
| `06` | -- | WFM | WFM | -- | -- | -- | -- |
| `07` | CW-R | CW-R | CW-R | CW-R | CW-R | CW-R | CW-R |
| `08` | RTTY-R | RTTY-R | RTTY-R | RTTY-R | RTTY-R | RTTY-R | RTTY-R |
| `17` | DV | DV | DV | -- | -- | -- | -- |
| `22` | DD | -- | -- | -- | -- | -- | -- |

**Byte 2 -- Filter Setting:**

| Value | Filter |
|-------|--------|
| `01` | FIL1 |
| `02` | FIL2 |
| `03` | FIL3 |

> Filter setting (byte 2) can be skipped with commands `01` and `06`. When skipped,
> `FIL1` is selected with command `01` and the default filter setting of the operating
> mode is automatically selected with command `06`.
>
> *\*IC-9700: Command `22` (DD) can be selected when setting the 1200 MHz band to
> other than satellite mode.*

---

## Duplex Offset Frequency

**Commands:** `0C`, `0D`

| Byte | 1 | 2 | 3 |
|------|---|---|---|
| Data | XX | XX | XX |

| Byte | Digit | Range |
|------|-------|-------|
| 1 | 1 kHz | 0 ~ 9 |
| 2 | 100 Hz | 0 ~ 9 |
| 3 | 100 kHz | 0 ~ 9 |
| 4 | 10 kHz | 0 ~ 9 |
| 5 | 10 MHz | 0 ~ 9 |
| 6 | 1 MHz | 0 ~ 9 |

> Only the IC-9700 1200 MHz band can input 10 MHz digits.
>
> **Radio availability:** `0C`/`0D` commands exist on the IC-9700, IC-705, and IC-7100.
> The IC-7610 and IC-7760 do NOT have `0C`/`0D` -- they use `21 02` (dTX) for offset.

---

## Band Edge Frequency Settings

**Commands:** `02*`, `1E 01`, `1E 03`

| Byte | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|------|---|---|---|---|---|---|---|---|---|----|----|----|
| Data | XX | XX | XX | XX | XX | XX | `2D` | XX | XX | XX | XX | XX |

| Byte | Description | Range |
|------|-------------|-------|
| 1 | Edge number | `01` ~ `1E` (1 ~ 30) |
| 2-6 | Lower edge frequency | BCD (see frequency encoding) |
| 7 | Separator | `2D` (fixed) |
| 8-12 | Higher edge frequency | BCD (see frequency encoding) |

> When obtaining the edge number (by command `02`), the edge number (byte 1) is not returned.

---

## CW Message Character Codes

**Command:** `17` (up to 30 characters)

| Character | ASCII Code |
|-----------|------------|
| `0` ~ `9` | `30` ~ `39` |
| `A` ~ `Z` | `41` ~ `5A` |
| `a` ~ `z` | `61` ~ `7A` |
| `/` | `2F` |
| `?` | `3F` |
| `.` | `2E` |
| `-` | `2D` |
| `,` | `2C` |
| `:` | `3A` |
| `'` | `27` |
| `(` | `28` |
| `)` | `29` |
| `=` | `3D` |
| `+` | `2B` |
| `"` | `22` |
| `@` | `40` |
| Space | `20` |

- `FF` stops sending CW messages.
- `^` is used to transmit a string of characters with no inter-character space.

**Radio-specific additional characters (IC-7610/7760):**

| Character | ASCII Code |
|-----------|------------|
| `!` | `21` |
| `#` | `23` |
| `$` | `24` |
| `%` | `25` |
| `&` | `26` |
| `\` | `5C` |
| `` ` `` | `60` |
| `^` | `5E` |
| `*` | `2A` |
| `;` | `3B` |
| `<` | `3C` |
| `>` | `3E` |
| `[` | `5B` |
| `]` | `5D` |
| `{` | `7B` |
| `}` | `7D` |
| `\|` | `7C` |
| `_` | `5F` |
| `~` | `7E` |

---

## IF Filter Width Settings

**Command:** `1A 03`

| Mode | Data Range | Steps |
|------|------------|-------|
| SSB/CW/RTTY | 0 ~ 9 | 50 ~ 500 Hz (50 Hz) |
| SSB/CW | 10 ~ 40 | 600 Hz ~ 3.6 kHz (100 Hz) |
| RTTY | 10 ~ 31 | 600 ~ 2.7 kHz (100 Hz) |
| AM | 0 ~ 49 | 200 Hz ~ 10.0 kHz (200 Hz) |

> The IC-7300 MK2 uses `1A 03` with the same ranges but adds PSK mode (same as RTTY).

---

## AGC Time Constant Settings

**Command:** `1A 04` (IC-9700/705/7100), `16 12` (IC-7300/7300 MK2/7610/7760)

| Data | SSB/CW/RTTY (sec.) | AM (sec.) |
|------|---------------------|-----------|
| `00` | OFF | OFF |
| `01` | 0.1 | 0.3 |
| `02` | 0.2 | 0.5 |
| `03` | 0.3 | 0.8 |
| `04` | 0.5 | 1.2 |
| `05` | 0.8 | 1.6 |
| `06` | 1.2 | 2.0 |
| `07` | 1.6 | 2.5 |
| `08` | 2.0 | 3.0 |
| `09` | 2.5 | 4.0 |
| `10` | 3.0 | 5.0 |
| `11` | 4.0 | 6.0 |
| `12` | 5.0 | 7.0 |
| `13` | 6.0 | 8.0 |

> **IC-7300/7300 MK2/7610/7760:** AGC is sent via `16 12` (sub-command of `16*`),
> with values `01`=FAST, `02`=MID, `03`=SLOW (simplified 3-value enum, not the full table).
> The full 14-value table above applies to the IC-9700, IC-705, and IC-7100 via `1A 04`.

---

## SSB/SSB-DATA Transmission Passband Width Settings

**Command:** `1A 05 0017` ~ `1A 05 0020`

**Higher Edge:**

| Value | Frequency |
|-------|-----------|
| `00` | 2500 Hz |
| `01` | 2700 Hz |
| `02` | 2800 Hz |
| `03` | 2900 Hz |

**Lower Edge:**

| Value | Frequency |
|-------|-----------|
| `00` | 100 Hz |
| `01` | 200 Hz |
| `02` | 300 Hz |
| `03` | 500 Hz |

---

## RX HPF/LPF Settings (Per Operating Mode)

**IC-9700/705/7100:** `1A 05 0001`, `0004`, `0007`, `0010`, `0013`, `0014`
**IC-7300 MK2/7610/7760:** `1A 05 00 01`, `00 04`, `00 07`, `00 10`, `00 11` (space-separated pairs)

| Byte | 1 | 2 | 3 | 4 |
|------|---|---|---|---|
| Data | X | X | X | X |

> The HPF value must be smaller than the LPF value.

**HPF (Lower Edge):**

| Value | Frequency |
|-------|-----------|
| `00` | Through |
| `01` ~ `20` | 100 ~ 2000 Hz |

**LPF (Upper Edge):**

| Value | Frequency |
|-------|-----------|
| `05` ~ `24` | 500 ~ 2400 Hz |
| `25` | Through |

---

## Color Settings

**Command:** `1A 05 0194`, `0195`, `0196`, `0212`, `0214`, `0230`, `0235`, `0236` (IC-9700)

| Byte | 1 | 2 | 3 | 4 | 5 | 6 |
|------|---|---|---|---|---|---|
| Data | `0X` | `XX` | `0X` | `XX` | `0X` | `XX` |

| Channel | Range |
|---------|-------|
| R (Red) | `0000` ~ `0255` |
| G (Green) | `0000` ~ `0255` |
| B (Blue) | `0000` ~ `0255` |

> Sub-command numbers differ between radios. The IC-7610 uses `01 72`/`01 73`/`01 74`
> for waveform colors. The IC-7300 MK2 uses `01 44`/`01 45`/`01 46`.

---

## Memory Keyer Content

**Command:** `1A 02`

| Byte | 1 | 2 | ... | 71 |
|------|---|---|-----|----|
| Data | XX | XX | ... | XX |

**Byte 1 -- Channel Data:**

| Value | Channel |
|-------|---------|
| `01` | M1 |
| `02` | M2 |
| `03` | M3 |
| `04` | M4 |
| `05` | M5 |
| `06` | M6 |
| `07` | M7 |
| `08` | M8 |

Bytes 2-71: Text data.

---

## UTC Offset Setting

**IC-9700:** `1A 05 0184`
**IC-7610:** `1A 05 01 62`
**IC-7760:** `1A 05 02 04`
**IC-7300 MK2:** `1A 05 01 36`

| Byte | 1 | 2 | 3 |
|------|---|---|---|
| Data | XX | XX | XX |

**Shift Direction:**

| Value | Direction |
|-------|-----------|
| `00` | + (plus) |
| `01` | - (minus) |

**Offset Time:** `0000` ~ `1400`

---

## Split Offset Frequency Setting

**Command:** `1A 05 0044` (IC-9700)

| Byte | 1 | 2 | 3 | 4 |
|------|---|---|---|---|
| Data | X`0` | XX | `0`X | XX |

| Byte | Digit | Range |
|------|-------|-------|
| 1 (high nibble) | 1 kHz | 0 ~ 9 |
| 1 (low nibble) | 100 Hz | `0` (fixed) |
| 2 | 100 kHz | 0 ~ 9 |
| 3 (high nibble) | 10 kHz | 0 ~ 9 |
| 3 (low nibble) | 10 MHz | `0` (fixed) |
| 4 | 1 MHz | 0 ~ 9 |

**Direction:**

| Value | Direction |
|-------|-----------|
| `00` | + (plus) |
| `01` | - (minus) |

---

## Scope VBW (Video Band Width) Settings

**IC-9700:** `1A 05 0191`, `27 1D`
**IC-705:** `27 1D` (sub-command `1D` of `27*`)
**IC-7300 MK2/7610/7760:** `27 1D` (sub-command `1D` of `27*`)

| Byte | 1 | 2 |
|------|---|---|
| Data | XX | XX |

**VBW Setting:**

| Value | Width |
|-------|-------|
| `00` | Narrow |
| `01` | Wide |

**Band Selection (IC-9700 only):**

| Value | Band |
|-------|------|
| `00` | MAIN |
| `01` | SUB |

---

## RIT Frequency Settings

**Command:** `21 00`

| Byte | 1 | 2 | 3 |
|------|---|---|---|
| Data | XX | XX | XX |

| Byte | Digit | Range |
|------|-------|-------|
| 1 | 10 Hz | 0 ~ 9 |
| 1 (high nibble) | 1 Hz | 0 ~ 9 |
| 2 | 100 Hz | 0 ~ 9 |
| 2 (high nibble) | 1 kHz | 0 ~ 9 |
| 3 | Sign | `00` / `01` |

**Sign:**

| Value | Direction |
|-------|-----------|
| `00` | + (plus) |
| `01` | - (minus) |

> BCD encoding, little-endian (LSB first). Bytes 1-2 are standard 2-digit BCD (4 digits total). Byte 3 is the sign byte.

---

## Selected or Unselected VFO Frequency Settings

**Command:** `25` *(Only MAIN band)*

| Byte | 1 | 2 | 3 | 4 | 5 | 6 |
|------|---|---|---|---|---|---|
| Data | XX | XX | XX | XX | XX | XX |

| Byte | Description |
|------|-------------|
| 1 | VFO select: `00` = Selected VFO, `01` = Unselected VFO |
| 2-6 | Operating frequency (BCD, same encoding as command `05`) |

> You cannot set the SUB band frequency.
>
> `00`/`01` can be set in VFO mode only. In satellite mode, `FA` (NG) is returned. In memory channel mode, call channel mode, or DR function, `FA` (NG) is returned because these cannot be set to `01`.

**VFO selection behavior:**

| Selected VFO | Byte 1 = `00` | Byte 1 = `01` |
|--------------|---------------|---------------|
| VFO A | VFO A frequency changes | VFO B frequency changes |
| VFO B | VFO B frequency changes | VFO A frequency changes |

---

## Selected or Unselected VFO Operating Mode and Filter Settings

**Command:** `26` *(Only MAIN band)*

| Byte | 1 | 2 | 3 | 4 |
|------|---|---|---|---|
| Data | XX | XX | XX | XX |

| Byte | Description |
|------|-------------|
| 1 | VFO select: `00` = Selected VFO, `01` = Unselected VFO |
| 2 | Operating mode setting |
| 3 | Data mode setting (can be skipped) |
| 4 | Filter setting (can be skipped) |

> You cannot set the SUB band operating mode and filter settings.
>
> Both data mode (byte 3) and filter (byte 4) settings can be skipped. In that case, "DATA OFF" and the default filter setting of the operating mode are automatically selected.
>
> `00`/`01` can be set in VFO mode only. In satellite mode, `FA` (NG) is returned. In memory channel mode, call channel mode, or DR function, `FA` (NG) is returned because these cannot be set to `01`.

**VFO selection behavior:**

| Selected VFO | Byte 1 = `00` | Byte 1 = `01` |
|--------------|---------------|---------------|
| VFO A | VFO A mode/filter changes | VFO B mode/filter changes |
| VFO B | VFO B mode/filter changes | VFO A mode/filter changes |

**Byte 2 -- Operating Mode:** See [Operating Mode](#operating-mode) table above.

**Byte 3 -- Data Mode:**

| Value | Mode |
|-------|------|
| `00` | Data mode OFF |
| `01` | Data mode ON |

**Byte 4 -- Filter Setting:**

| Value | Filter |
|-------|--------|
| `01` | FIL1 |
| `02` | FIL2 |
| `03` | FIL3 |

---

## Band Selector (IC-7610/7760)

**Command:** `29`

Specify the Main or Sub band before entering the supported commands.
When you receive the OK code (FB), or the NG code (FA), the Command 29 and
Main/Sub specify (00 or 01) is omitted.

```
29 XX XX XX......XX
29     <- Command
00/01  <- 00: MAIN or 01: SUB
XX     <- Commands
XX     <- Data
```

The supported commands are marked by "29" in the command table.

> **Radio availability:** IC-7610 and IC-7760 only. Not available on other radios.

---

## APF (Audio Peak Filter) Settings

**Command:** `16 32` (sub-command of `16*`)

| Value | APF Mode |
|-------|----------|
| `00` | APF OFF |
| `01` | WIDE APF ON |
| `02` | MID APF ON |
| `03` | NAR APF ON |

> **Radio availability:** IC-7300 MK2, IC-7610, IC-7760. The IC-9700 and IC-705 do
> NOT have APF. The IC-7300 original has no CI-V APF command.
>
> The IC-7610 and IC-7760 include a band byte (`29` for HF/50MHz) between the
> sub-command and data value: `16 32 29 00`.

---

## Attenuator Settings

| Radio | Command | Values |
|-------|---------|--------|
| IC-9700 | `0F 11` (sub-command of `0F`) | `00`=OFF, `10`=10 dB |
| IC-705 | `0F 11` (sub-command of `0F`) | `00`=OFF, `20`=20 dB (HF/50MHz only) |
| IC-7100 | `0F 11` (sub-command of `0F`) | `00`=OFF, `12`=12 dB |
| IC-7300 | `11` (top-level) | `00`=OFF, `20`=20 dB |
| IC-7300 MK2 | `11` (top-level) | `00`=OFF, `20`=20 dB |
| IC-7610 | `11` (top-level) | `00`=OFF, `03`-`45` (3-45 dB, 3 dB steps, 16 values) |
| IC-7760 | `11` (top-level) | `00`=OFF, `03`-`45` (3-45 dB, 3 dB steps, 16 values) |