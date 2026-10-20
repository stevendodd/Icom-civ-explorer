# Manual verification lookup table

Checklist for the notes that still need a **visual read of the printed manual page** — the
byte-diagram layouts, icon glyphs, and possible errata that text extraction cannot settle.

For each row: open the radio's PDF (in `docs/icom manuals/`) at the given **PDF viewer page**,
find the command cell named there, then compare with what the API currently ships.

- API base: `http://localhost:8001` (the local verify container — `https://icom-civ.stevendodd.net` works identically).
- Legend: **noteless** = those rows currently get no panel in the API/UI; the page read decides the body we overlay.
- To report back: a screenshot of the page, or a one-line verdict per row, is enough.
- The `q=` searches are substring matches on `cmd`/`sub_cmd`/`data`/`description` — narrow enough that paging is not needed.

---

## IC-7300MK2 — `docs/icom manuals/IC-7300MK2_ENG_CI-V_0.pdf` (biggest gap: most noteless rows)

- [ ] **Band edge frequency settings panel** — **p. 15**, panel; commands `02` and `1E 01`/`1E 03`
      → `http://localhost:8001/radios/7300mk2/commands?q=upper%20and%20lower%20edge` — the `02`, `1E 01`, `1E 03` rows (noteless)
- [ ] **Bandscope edge frequencies, 13-row table** — **p. 21**, panel under `SCOPE > Fixed Edge`; rows `1A 05 01 52`–`02 03`
      → `http://localhost:8001/radios/7300mk2/commands?q=05%2C0152` — page through 05,0152–0203 (all noteless)
- [ ] **IP address digit ranges** — **p. 21**, `1A 05 01 02` / `04` / `05` / `06`
      → `http://localhost:8001/radios/7300mk2/commands?q=05%2C0104` (noteless)
- [ ] **Color setting ranges** — **p. 22**, `1A 05 01 45`/`46`, `02 33`/`34`, `02 51`/`52`
      → `http://localhost:8001/radios/7300mk2/commands?q=05%2C0146`
- [ ] **UTC offset range line (`00 00 ~ 14 00`)** — **p. 21**, find "UTC offset"
      → `http://localhost:8001/radios/7300mk2/commands?q=UTC`
- [ ] **`[ ]`/`[DN]` icon titles (current guess: `[◆]`/`[◇]`)** — **p. 21**, `1A 05 00 60` and `00 62` cells; what icons print above them?
      → `http://localhost:8001/radios/7300mk2/commands?q=05%2C0060` and `?q=05%2C0062`
- [ ] **"Codes for character entries"** — search the doc for the phrase (memory-name section); also shows the `U+F0AB` garbage glyph
      → `http://localhost:8001/radios/7300mk2/commands?q=Memory%20channel%20content`

## IC-9700 — `docs/icom manuals/not-IC-9700_ENG_CI-V_1-en.pdf` (the file really is named `not-…`)

- [ ] **Memory content byte map** — **pp. 14–15**, panel after `1A 00`
      → `http://localhost:8001/radios/9700/commands?q=Memory%20content` (body carries head-glyph junk)
- [ ] **Codes for character entries / `7C`/`7E` glyphs** — **p. 15**, the char-code table; what punctuation prints for `7C`, `7E`?
      → `http://localhost:8001/radios/9700/commands?q=05%2C0144`
- [ ] **Manually entered position data** — **p. 17**
      → `http://localhost:8001/radios/9700/commands?q=Manually%20entered`
- [ ] **Satellite memory content** — **p. 18**
      → `http://localhost:8001/radios/9700/commands?q=Satellite%20memory`
- [ ] **DV TX call signs (24-char)** — **p. 19**, panel under cmd `20`
      → `http://localhost:8001/radios/9700/commands?q=DV%20TX`
- [ ] **DV RX call sign / message / status (`20 0201`/`0202`)** — **p. 20**
      → `http://localhost:8001/radios/9700/commands?q=DV%20RX`
- [ ] **GPS/D-PRS data / message** — **pp. 21–22**, `1A 05 03 10`–`15`
      → `http://localhost:8001/radios/9700/commands?q=05%2C0310`
- [ ] **DV TX data / DV RX data (transceive)** — **p. 23**, cmds `22`, `23`
      → `http://localhost:8001/radios/9700/commands?q=DV%20TX%20data`
- [ ] **`25`/`26` "(Only MAIN band)" — one panel or two?** — **printed p. 23** (summary)
      → `http://localhost:8001/radios/9700/commands?q=Only%20MAIN%20band`
- [ ] **`16 5D` — what does the manual print in that sub cell?** — find `16 5D` in the tone page (~pp. 5–6)
      → `http://localhost:8001/radios/9700/commands?q=16%2C5D`

## IC-7100 — `docs/icom manuals/IC-7100_ENG_FM_5.pdf` (CI-V section at the **end** of the full manual)

- [ ] **Memory content: `ʜ` boxes and the invisible `U+0011` cell** — **p. 370**, panel after `1A 00`
      → `http://localhost:8001/radios/7100/commands?q=Memory%20content%20setting`
- [ ] **Character code setting — which rows it should live on** — **p. 370**
      → `http://localhost:8001/radios/7100/commands?q=DV%20RX%20Call%20signs` — the `20 00 01`/`00 02` rows
- [ ] **DV RX call sign / message / status panels (`20 00 01`, `20 01 01`, `20 02 01`)** — **p. 373**
      → `http://localhost:8001/radios/7100/commands?q=DV%20RX%20message` (noteless)
- [ ] **Band edge (`02`, `1E 01`, `1E 03`)** — **p. 370**
      → `http://localhost:8001/radios/7100/commands?q=Band%20edge`

## IC-705 — `docs/icom manuals/IC-705_ENG_CI-V_6.pdf`

- [ ] **`[C]`/`[D]` icons — what really prints?** (current CSV shows bracket placeholders) — **printed p. 21**, `1A 05 00 76`/`00 77`
      → `http://localhost:8001/radios/705/commands?q=05%2C0076` and `?q=05%2C0077`
- [ ] **Manually entered position data** — **p. 22**
      → `http://localhost:8001/radios/705/commands?q=Manually%20entered`
- [ ] **DV MY call sign** — **p. 23**
      → `http://localhost:8001/radios/705/commands?q=DV%20MY`
- [ ] **DV RX call sign / message / status** — **p. 24**
      → `http://localhost:8001/radios/705/commands?q=DV%20RX`
- [ ] **GPS/D-PRS data / message** — **pp. 25–26**
      → `http://localhost:8001/radios/705/commands?q=D-PRS`
- [ ] **DV TX data** — **p. 27**
      → `http://localhost:8001/radios/705/commands?q=DV%20TX`

## IC-7300 — `docs/icom manuals/IC-7300_ENG_FM_12atob.pdf`

- [ ] **Bandscope edge frequency settings panel (currently unshipped)** — **p. 166**, panel; rows `02 04–16` and `1A 05 01 12–50`
      → `http://localhost:8001/radios/7300/commands?q=05%2C0112`
- [ ] **Memory content (`U+F0AB` glyph)** — **printed p. 19-11**, PDF ~p. 166
      → `http://localhost:8001/radios/7300/commands?q=Memory%20content`
- [ ] **Fixed edge + footnote wording for the edge footnote** — **printed p. 19-15**, `27 1D`/`1E`
      → `http://localhost:8001/radios/7300/commands?q=Scope%20Fixed`
- [ ] **`*3` example byte values (CW panel)** — find the CW panel under cmd `17` (~printed 19-9)
      → `http://localhost:8001/radios/7300/commands?q=CW` — look at cmd 17's note

## IC-7610 — `docs/icom manuals/IC-7610_ENG_CI-V_3.pdf`

- [ ] **Band edge frequency settings panel** — **p. 10**
      → `http://localhost:8001/radios/7610/commands?q=Band%20edge`
- [ ] **Codes for character entries (carrier row TBD: `05,0133`?)** — **p. 11**
      → `http://localhost:8001/radios/7610/commands?q=05%2C0133`
- [ ] **Bandscope edge (`1A 05 01 82`–`02 17`)** — **p. 12**
      → `http://localhost:8001/radios/7610/commands?q=05%2C0182`
- [ ] **Antenna memory settings (`1A 05 02 76`–`02 87`)** — **p. 13**
      → `http://localhost:8001/radios/7610/commands?q=05%2C0276`

## IC-7760 — `docs/icom manuals/IC-7760_ENG_CI-V_2.pdf`

- [ ] **RBW print — does the manual itself print `01=NAR`?** (possible errata) — **printed p. 25** (summary table on PDF p. 16 under `SCOPE > RBW`)
      → `http://localhost:8001/radios/7760/commands?q=RBW` — row `27 1F`
- [ ] **Bandscope edge (`1A 05 02 49`–`02 71`)** — **p. 22**
      → `http://localhost:8001/radios/7760/commands?q=05%2C0249`
- [ ] **Antenna memory (`1A 05 03 49`–`03 60`)** — **p. 22**
      → `http://localhost:8001/radios/7760/commands?q=05%2C0349`
- [ ] **RIT/∂TX frequency settings (`21 00 10`–`19`)** — **p. 23**
      → `http://localhost:8001/radios/7760/commands?q=21%2C0010`

## Fleet-wide glyph conventions (one read settles all)

- [ ] **`∂F`/`∂TX`** — manual prints a stylized F/T glyph; confirm we keep rendering it as `∂`
      (e.g. mk2 p. 21, 7760 p. 23)
      → `http://localhost:8001/radios/7300mk2/commands?q=%E2%88%82F` (`q=∂F`)
- [ ] **Small-cap glyph boxes (`ʜ ʙ` on the 7100's DV/memory panels)** — 7100 pp. 370/373
      → covered by the 7100 rows above

---

## After verifying

Each verdict becomes a body in `docs/icom manuals/notes-overrides/<rid>.json`, then the standard
loop: resolve → tests → build → live verify → commit. The "review binding" panels (7100 Character
code, 7610 UTC/Color, etc.) also get a re-check of *where they attached*, enumerated automatically
once transcriptions start.

---

# Quick tables view (rendered boxes in render-markdown)

| Radio | Biggest gap | PDF page | API query |
|---|---|---|---|
| 7300mk2 | Band edge + Bandscope edge panels noteless | 15 / 21 | `?q=05%2C0152` |
| 7300mk2 | IP/Color/UTC/character codes | 21 / 22 | `?q=05%2C0104` |
| 9700 | Memory content, char entries (`7C`/`7E`), DV panels | 14–23 | `?q=Memory%20content` |
| 9700 | `25`/`26` "(Only MAIN band)" split · `16 5D` | p. 23 / tone page | `?q=16%2C5D` |
| 7100 | Memory `ʜ` boxes + `U+0011`, DV RX panels, char code rows | 370 / 373 | `?q=DV%20RX%20message` |
| 705 | `[C]`/`[D]` icons + DV/GPS byte-cells | 21–27 | `?q=05%2C0076` |
| 7300 | Bandscope edge panel unshipped; `U+F0AB` glyph | 166 | `?q=05%2C0112` |
| 7610 | Band edge unsent; char entries; bandscope; antenna mem | 10–13 | `?q=05%2C0276` |
| 7760 | **RBW `01=NAR` errata?**; bandscope; RIT/∂TX | 16–23 / p. 25 | `?q=RBW` |

| Fleet glyph | Question | API |
|---|---|---|
| `∂F`/`∂TX` | keep the stylized-`∂` rendering? | `?q=∂F` |
| 7100 `ʜ ʙ` boxes | what does the page print? | 7100 pp. 370/373 |
| mk2 `[◆]/[◇]`, 705 icons | real icon identities? | `?q=05%2C0060` |