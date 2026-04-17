# XG Drum Setup Parameters

Parametri per-nota dei Drum Kit programmabili. Il QY70 ha 2 Drum Setup (DS1, DS2) attivabili via [Multi Part](xg-multi-part.md) `Part Mode = 2` (DS1) o `3` (DS2).

**Formato**: `F0 43 10 4C 3n RR [AL] XX F7`
- `n = 0` per Drum Setup 1 (Base `30`)
- `n = 1` per Drum Setup 2 (Base `31`)
- `RR` = Note Number (drum instrument), range 0Dh-5Bh (13-91)

## Parametri

| AL | Parametro | Range | Default | Note |
|----|-----------|-------|---------|------|
| 00 | Pitch Coarse | 00-7F | 40 | -64..+63 semitoni |
| 01 | Pitch Fine | 00-7F | 40 | -64..+63 cent |
| 02 | Level | 00-7F | Varies | Volume individuale |
| 03 | Alternate Group | 00-7F | Varies | 0=OFF, 1..127=gruppo esclusivo |
| 04 | Pan | 00-7F | Varies | 0=Random, 1..64..127=L..C..R |
| 05 | Reverb Send | 00-7F | Varies | |
| 06 | Chorus Send | 00-7F | Varies | |
| 07 | Variation Send | 00-7F | 7F | |
| 08 | Key Assign | 00-01 | 00 | 0=Single, 1=Multi |
| 09 | Rcv Note Off | 00-01 | Varies | (Invalid per voci con GMx Note-off recognition) |
| 0A | Rcv Note On | 00-01 | 01 | |
| 0B | Filter Cutoff | 00-7F | 40 | -64..+63 |
| 0C | Filter Resonance | 00-7F | 40 | -64..+63 |
| 0D | EG Attack Rate | 00-7F | 40 | -64..+63 |
| 0E | EG Decay 1 Rate | 00-7F | 40 | -64..+63 |
| 0F | EG Decay 2 Rate | 00-7F | 40 | -64..+63 |

## EQ (MU90/MU100/SW1000XG only — non QY70)

| AL | Parametro |
|----|-----------|
| 20 | EQ Bass Gain |
| 21 | EQ Treble Gain |
| 24 | EQ Bass Frequency |
| 25 | EQ Treble Frequency |

## Note

- Quando ricevi **XG System On** o **GM System On**, tutti i Drum Setup parameters vengono inizializzati.
- Usa **Drum Setup Reset** (`F0 43 10 4C 00 00 7D 0n F7`, n=0/1) per reset selettivo.
- I valori "Varies" dipendono dal Drum Kit selezionato via Program Change/Bank Select (tipicamente tutti 40h dopo reset).

### Note mapping per-kit

Il range fisico `RR = 0Dh-5Bh` (13-91) copre 127 possibili drum voice, ma **ogni kit mappa solo un subset**. Il QY70 include Standard/Room/Rock/Electro/Analog/Jazz/Brush/Classic/SFX kits; il QY700 estende a 20 kits. Osservato nel capture `ground_truth_preset.syx` (sess. 30f): notes 31, 33, 35-40, 42, 44, 46, 51 attive in Standard Kit. Mapping completo: [QY70_LIST_BOOK.PDF pag. 15-20 Drum Voice List](../manual/QY70/QY70_LIST_BOOK.PDF).

### Drum note receive range

QY70 drum voice program numbers `P=1..49` = 18 drum kits + SFX varianti. Voice selection via Bank MSB=127 (7Fh) + LSB=0 + Program=P.

## Source

- [studio4all.de main93.html](http://www.studio4all.de/htmle/main93.html)
- `manual/QY70/QY70_LIST_BOOK.PDF` pag. 61 Table 1-7
