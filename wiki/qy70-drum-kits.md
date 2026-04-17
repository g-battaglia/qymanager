# QY70 Drum Kits Note Mapping

Mapping note → drum instrument per i 20 drum kit del QY70. Riferimento: `manual/QY70/QY70_LIST_BOOK.PDF` pag 10-14.

## Range note drum

Note MIDI utilizzabili: **13-91** (0x0D-0x5B) = 79 slot disponibili. Non tutte le note sono mappate in ogni kit.

Attenzione: il range drum XG è più ampio di quello GM (35-81). Il QY70 accetta l'intero range 13-91 ma mostra solo le note effettivamente mappate nel kit selezionato.

## Standard Kit 1 (Bank 127, Prog 0) — kit di default

Note comuni, osservate nel capture `ground_truth_preset.syx` (sess. 30f):

| Note | Hex | Name |
|------|-----|------|
| 31 | 1F | SFX Snare (Standard) |
| 33 | 21 | Metronome Click |
| 35 | 23 | Kick 1 |
| 36 | 24 | **Kick 2** (primary) |
| 37 | 25 | Side Stick |
| 38 | 26 | **Snare 1** (primary) |
| 39 | 27 | Hand Clap |
| 40 | 28 | Snare 2 |
| 42 | 2A | **Closed Hi-Hat** |
| 44 | 2C | Pedal Hi-Hat |
| 46 | 2E | **Open Hi-Hat** |
| 49 | 31 | Crash Cymbal 1 |
| 51 | 33 | Ride Cymbal 1 |
| 52 | 34 | Chinese Cymbal |
| 53 | 35 | Ride Bell |
| 54 | 36 | Tambourine |
| 56 | 38 | Cowbell |
| 57 | 39 | Crash Cymbal 2 |
| 59 | 3B | Ride Cymbal 2 |

Lista completa (72 note 13-84): `midi_tools/xg_voices.py` `GM_DRUM_NOTES`.

## Room / Rock / Electro / Analog kits

Mantengono il layout Standard Kit ma con sound replacements:
- **Room Kit**: ambient reverb version dei sound standard
- **Rock Kit**: kick e snare più punchy, hat più brillante
- **Electro Kit**: sound elettronici (Linn, Simmons)
- **Analog Kit**: TR-808 e TR-909 samples → 808 Kick su 36, 808 Snare su 38, 808 Cowbell su 56

## Jazz / Brush / Classic

- **Jazz Kit**: ride pronunciato, brush snare
- **Brush Kit**: tutti snare come brush + brush slap
- **Classic Kit**: timpani su note basse (36-38), symphonic cymbals (49-57)

## SFX Kit (Bank 64)

Sound effects preset (gunshot, bird tweet, laser, footstep, ecc.) mappati su note drum. Uso raro nei pattern ma accessibile via Program Change con Bank MSB=64.

## Note speciali per-kit

Alcuni kit sovrascrivono note con sample custom. Esempi:
- **Analog Kit** → note 75-78 diventano Conga/Bongo 808
- **Classic Kit** → note 36-38 diventano Timpani pitched
- **SFX Kit** → TUTTE le note sono sound effects

## Uso nel RE

Il decoder drum del QY70 usa queste note per mappare strike rhyt → drum instrument. Ground truth capture di `Summer` (RHY1, session 22): 61 drum strikes mappati su note 24, 26, 2A, 2C = Kick 2, Snare 1, Closed HH, Pedal HH.

Vedi [summer_ground_truth.json](../midi_tools/captured/) per validation data.

## Cross-references

- [xg-drum-setup.md](xg-drum-setup.md) — editing per-note params (pitch, pan, level)
- [qy70-voice-list.md](qy70-voice-list.md) — kit selection via Program Change
- [2543-encoding.md](2543-encoding.md) — drum encoding RE
- `manual/QY70/QY70_LIST_BOOK.PDF` pag 10-14
