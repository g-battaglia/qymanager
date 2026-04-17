# QY700 Preset Phrase Lists

Ref: `QY700_REFERENCE_LISTING.pdf` pagine 15-29

Il QY700 ha **3,876 preset phrase** divise per categoria e beat field. Le phrase sono pre-registrate; il converter può referenziarle per numero invece di inserire i dati MIDI (risparmio di memoria).

## Phrase numbering convention

`<CATEGORY><BEAT><NNN>`, es:
- `Da16001` = Drum-a, 16-beat, #001
- `KA08030` = Keyboard Arpeggio, 8-beat, #030
- `BR34002` = Brass, 3/4-beat, #002

## Category codes

| Code | Category |
|------|----------|
| Da | Drum a |
| Db | Drum b |
| Fa | Fill a |
| Fb | Fill b |
| Fc | Fill c |
| DP | Drum + Perc |
| PC | Percussion |
| PF | Perc fill |
| Ba | Bass a |
| Bb | Bass b |
| GC | Guitar Chord |
| GA | Guitar Arpeggio |
| GR | Guitar Riff |
| KC | Keyboard Chord |
| KA | Keyboard Arpeggio |
| KR | Keyboard Riff |
| PD | Pad |
| BR | Brass |
| SE | Sound Effect |
| US | User (registered by user, 99 max/style) |

## Beat codes

| Code | Meaning |
|------|---------|
| 16 | 16-beat (straight 16th) |
| 08 | 8-beat (straight 8th) |
| 34 | 3/4-beat (o 6/8 swing) |

## Phrase count summary

Approssimativo (la lista PDF enumera le phrase individualmente per categoria e beat). Numeri confermati da spot-check:

| Category | 16-beat | 8-beat | 3/4-beat |
|----------|---------|--------|----------|
| Da | ~200 | ~200 | ~50 |
| Db | ~200 | ~100 | — |
| Fa/Fb/Fc | vari | vari | vari |
| DP | molti | molti | — |
| PC | ~100 | ~100 | — |
| PF | ~50 | ~50 | — |
| Ba | ~300 | ~200 | ~50 |
| Bb | ~200 | ~200 | — |
| GC | ~200 | ~150 | ~30 |
| GA | ~150 | ~100 | — |
| GR | ~100 | ~80 | — |
| KC | ~150 | ~100 | ~30 |
| KA | 30 | 31 | 3 |
| KR | 79 | 25 | 4 |
| PD | 27 | 27 | 27 |
| BR | 37 | 21 | 2 |
| SE | 6 | 63 | 1 |

**Totale**: 3,876 preset phrase.

## Phrase types (per chord conversion)

Ogni phrase ha un **Phrase Type** che indica come deve essere trasposta/mappata quando il chord cambia:

| Type | Behavior |
|------|----------|
| Mldy1 | Melody mappata su root + scale naturale |
| Mldy2 | Melody mappata su chord tones |
| Chrd1 | Chord phrase, mappata su tutte le chord tones |
| Chrd2 | Variante chord mapping |
| Bass | Bass, segue chord root o on-bass |
| Bypas | Bypass — non trasposta |
| Para | Parallel — trasposta per intervallo |

Questo è un attributo della phrase, configurabile in edit.

## Rilevanza per qyconv

### Reference by number

In un Q7P, se una phrase pattern track usa una preset phrase, può contenere solo il numero di phrase (4 byte: 2 bytes category+beat code, 3 bytes number? — da investigare nel formato Q7P binary). Questo risparmia MB.

### Importazione QY70 → QY700

Le phrase QY70 preset NON corrispondono 1:1 alle QY700 preset (numeri diversi, contenuto diverso). Per conversion:
- Preset QY70 → convertire a **User phrase** sul QY700 (inserire i MIDI data espliciti)
- Mantenere category + beat code per consistency

### Lista completa

La lista nome-per-nome è in `QY700_REFERENCE_LISTING.pdf` pagine 15-29. Se il converter avesse bisogno di creare mapping automatico, dovremmo fare OCR o estrarre dal PDF (non implementato).
