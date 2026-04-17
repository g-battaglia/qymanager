# QY700 Chord Types

Ref: `QY700_REFERENCE_LISTING.pdf` — Chord Type List

Il QY700 supporta **28 chord types + 1 THRU** per la Fingered Chord engine. Ogni type è definito dalle note costituenti (relative al root).

## Chord Roots (12)

`C, C♯ (D♭), D, E♭ (D♯), E, F, F♯ (G♭), G, A♭ (G♯), A, B♭ (A♯), B`

## Chord Types

Le intervalli sono relativi al root (1 = tonica):

| # | Name | Notes (rel. to root) | Example on C |
|---|------|----------------------|--------------|
| 1 | **M** (Major) | 1, 3, 5 | C E G |
| 2 | **M7** | 1, 3, 5, 7 | C E G B |
| 3 | **6** | 1, 3, 5, 6 | C E G A |
| 4 | **7** | 1, 3, 5, ♭7 | C E G B♭ |
| 5 | **m** (Minor) | 1, ♭3, 5 | C E♭ G |
| 6 | **m7** | 1, ♭3, 5, ♭7 | C E♭ G B♭ |
| 7 | **m6** | 1, ♭3, 5, 6 | C E♭ G A |
| 8 | **mM7** | 1, ♭3, 5, 7 | C E♭ G B |
| 9 | **m7(♭5)** | 1, ♭3, ♭5, ♭7 | C E♭ G♭ B♭ |
| 10 | **dim** | 1, ♭3, ♭5, 6 (bb7) | C E♭ G♭ A |
| 11 | **aug** | 1, 3, ♯5 | C E G♯ |
| 12 | **sus4** | 1, 4, 5 | C F G |
| 13 | **add9** | 1, 3, 5, 9 | C E G D (ottava sopra) |
| 14 | **M7(9)** | 1, 3, 5, 7, 9 | C E G B D |
| 15 | **6(9)** | 1, 3, 5, 6, 9 | C E G A D |
| 16 | **7(9)** | 1, 3, 5, ♭7, 9 | C E G B♭ D |
| 17 | **madd9** | 1, ♭3, 5, 9 | C E♭ G D |
| 18 | **M9** | 1, 3, 5, 7, 9 | C E G B D (same as M7(9)?) |
| 19 | **m7(9)** | 1, ♭3, 5, ♭7, 9 | C E♭ G B♭ D |
| 20 | **m7(11)** | 1, ♭3, 5, ♭7, 11 | C E♭ G B♭ F |
| 21 | **7(♭5)** | 1, 3, ♭5, ♭7 | C E G♭ B♭ |
| 22 | **7(♯5)** | 1, 3, ♯5, ♭7 | C E G♯ B♭ |
| 23 | **7(♭9)** | 1, 3, 5, ♭7, ♭9 | C E G B♭ D♭ |
| 24 | **7(♯9)** | 1, 3, 5, ♭7, ♯9 | C E G B♭ D♯ |
| 25 | **7(13)** | 1, 3, 5, ♭7, 13 | C E G B♭ A (ottava sopra) |
| 26 | **7(♭13)** | 1, 3, 5, ♭7, ♭13 | C E G B♭ A♭ |
| 27 | **7sus4** | 1, 4, 5, ♭7 | C F G B♭ |
| 28 | **7(♯11)** | 1, 3, 5, ♭7, ♯11 | C E G B♭ F♯ |
| (—) | **THRU** (`---`) | Bypass | Nessuna trasposizione della phrase |

**THRU** = special type: la phrase NON viene convertita in base al chord. Usato per passaggi scritti liberamente (drum track, SFX, ecc.).

## On Bass

Nota singola premuta nella zona bass (sotto la Fingered Chord Zone) che sostituisce il bass del chord. Es: `C/G` = chord C Major con G come bass.

Memorizzato come nota MIDI separata nella Chord track.

## Original Bass

Se **no** On Bass è specificato, il chord è usato per intero (root = bass). Memorizzato come tutti chord tones nella Chord track.

## MIDI Input (Fingered Chord)

La **Fingered Chord Zone** è configurata in UTILITY F6 (vedi [qy700-utility-mode.md](qy700-utility-mode.md)):
- Zone Low..High: range di note riconosciute come input chord
- MIDI Port + Channel: dove arriva l'input
- Convention microkeyboard: E2-D♯3 = root, E3-F4 = type (simboli stampati)

## Rilevanza per qyconv

### Mapping QY70 ↔ QY700

QY70 ha **lo stesso set di 28 chord types** (sia QY70 che QY700 usano la XG Fingered Chord). Mapping 1:1 diretto via index/nome.

### Rappresentazione in Chord track

Byte encoding nella Chord track del Q7S/Q7P (da confermare):
- Root: 0-11 (C=0, C♯=1, ..., B=11)
- Type: 0-27 (+ 28 = THRU)
- On Bass: root byte (se presente) o flag per no-bass
- Original Bass: flag/mask

Struttura esatta richiede RE del Q7S format.

### Conversion tables per phrase type

Se implementiamo una `convert_chord` function per trasporre una phrase tra chord, serve una tabella (root, type) → [note intervals]. Quella tabella è già sopra.
