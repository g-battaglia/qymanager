# QY70 Voice Architecture

Architettura voice del tone generator XG del QY70. Riferimento: `manual/QY70/QY70_LIST_BOOK.PDF` pag 1-14.

## Panoramica

| Categoria | Count | Bank MSB | Note |
|-----------|-------|----------|------|
| **XG Normal** | 519 | 0 (+ varianti LSB) | 128 GM base + 391 bank variations |
| **Drum Kits** | 20 | 127 (0x7F) | Standard/Room/Rock/Electro/Analog/Jazz/Brush/Classic/SFX kits |
| **SFX Kit** | — | 64 (0x40) | Preset orchestra/sound effect kit |

**Totale**: 519 voci XG Normal + 20 Drum Kits = macchina XG completa.

## GM Level 1 base (Bank MSB=0, LSB=0)

128 program number (1-128 UI = 0-127 MIDI). Categorie:

| Prog range | Famiglia |
|------------|----------|
| 1-8 | Piano |
| 9-16 | Chromatic Percussion |
| 17-24 | Organ |
| 25-32 | Guitar |
| 33-40 | Bass |
| 41-48 | Strings |
| 49-56 | Ensemble |
| 57-64 | Brass |
| 65-72 | Reed |
| 73-80 | Pipe |
| 81-88 | Synth Lead |
| 89-96 | Synth Pad |
| 97-104 | Synth Effects |
| 105-112 | Ethnic |
| 113-120 | Percussive |
| 121-128 | Sound Effects |

Nomi completi in `midi_tools/xg_voices.py` (`GM_VOICES` tuple).

## XG Bank variations

Il QY70 supporta 391 bank variations accessibili via **Bank Select LSB** (CC#32). Ogni GM program può avere varianti timbriche (es. "Piano 1" ha Bright Piano, CP80, ecc.). Bank MSB resta 0 per voci normali; solo LSB varia.

Esempi tipici:
- MSB=0 LSB=0 → GM standard (GrandPno)
- MSB=0 LSB=1 → XG variation 1 (Bright Piano)
- MSB=0 LSB=2..4 → altre varianti timbriche

Tabella completa pag 1-5 LIST_BOOK.

## Drum Kits (Bank MSB=127)

20 kit selezionabili via Program Change dopo Bank MSB=127:

| Prog | Nome | Note |
|------|------|------|
| 0 | StandKit 1 | Standard acoustic |
| 1 | StandKit 2 | Alt standard |
| 8 | Room Kit | Ambient room |
| 16 | Rock Kit | Hard-rock sounds |
| 24 | Electro Kit | Electronic |
| 25 | Analog Kit | TR-808/909 |
| 32 | Jazz Kit | Jazz brushes |
| 40 | Brush Kit | Brush drums |
| 48 | Classic Kit | Classical percussion |

Ulteriori kit (Orchestral, SFX1/2, GM2/XG extensions) a program 56, 64, 72, ecc. Tabella completa: `midi_tools/xg_voices.py` `XG_DRUM_KITS`.

## SFX Kit (Bank MSB=64)

Preset Sound Effect kit: GS-style sfx sounds mappati su note drum. Uso atipico in pattern user. Vedi [qy70-drum-kits.md](qy70-drum-kits.md).

## Voice selection SysEx

Per cambiare voce su un canale/part, **serve una sequenza di 3 MIDI channel events**:

```
Bn 00 MSB     → Bank Select MSB (CC#0)
Bn 20 LSB     → Bank Select LSB (CC#32)
Cn PROG       → Program Change
```

**Esempio pratico**: Rock Kit su canale 10:
```
B9 00 7F     → MSB=127
B9 20 00     → LSB=0
C9 10        → Program 16 = Rock Kit
```

**Importante**: questi NON sono XG Parameter Change — sono canale events standard. Vedi [xg-parameters.md#limite-critico-xg-parm-out-non-trasmette-bankprogram](xg-parameters.md).

## QY70 vs QY700 voice count

| Device | Normal | Drum Kits |
|--------|--------|-----------|
| QY70 | 519 | 20 |
| QY700 | 491 (dichiarato manual) | — |

## Cross-references

- [xg-multi-part.md](xg-multi-part.md) — Multi Part Bank/Program fields
- [qy70-drum-kits.md](qy70-drum-kits.md) — drum note mapping per-kit
- [xg-drum-setup.md](xg-drum-setup.md) — editing per-note drum params
- `midi_tools/xg_voices.py` — lookup in codice
- `manual/QY70/QY70_LIST_BOOK.PDF` pag 1-14
