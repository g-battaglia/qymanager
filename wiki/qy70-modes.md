# QY70 Modes

Il QY70 opera in 7 modalità principali accessibili via tasto MODE. Riferimento: QY70 Owner's Manual.

## Modalità operative

| Mode | Scope | Note |
|------|-------|------|
| **SONG** | Playback/record song completi (fino a 20 slot + 3 demo 21-23) | 16 sequencer tracks + Pattern/Chord/Tempo track |
| **PATTERN** | Creazione/edit user style (U01-U64) | 8 tracks (D1/D2/PC/BA/C1-C4), 6 sections |
| **VOICE** | Mixer on-screen per assegnamento voci | Configura voci per pattern tracks o song tracks |
| **EFFECT** | Edit Reverb/Chorus/Variation | In Pattern mode solo Variation è editabile |
| **UTILITY** | Config system/MIDI/bulk dump/fingered zone | 4 sub-sezioni F1-F4 |
| **JOB** | Operazioni batch | Clear, Copy, Quantize, Normalize, Expand Backing, ecc. |
| **EDIT** | Event Edit nota-per-nota | Modifica puntuale eventi della traccia |

## Pattern mode: track mapping

I nomi slot visibili dipendono dal contesto:

| Style-level | Pattern-level | Ch drum out (PATT OUT 1~8) | Ch drum out (9~16) |
|-------------|---------------|------------------------------|------------------------|
| RHY1 | D1 | 1 | 9 |
| RHY2 | D2 | 2 | 10 |
| PAD | PC (Percussion) | 3 | 11 |
| BASS | BA | 4 | 12 |
| CHD1 | C1 | 5 | 13 |
| CHD2 | C2 | 6 | 14 |
| PHR1 | C3 | 7 | 15 |
| PHR2 | C4 | 8 | 16 |

I nomi slot sono fissi — NON indicano automaticamente il tipo di voce usato.

## Sections (Pattern mode)

6 sezioni per pattern: **INTRO** (default 2 bar), **MAIN A** (2 bar), **MAIN B** (2 bar), **FILL AB** (1 bar), **FILL BA** (1 bar), **ENDING** (2 bar).

Pattern length modificabile 1-8 bar. Time signature: `1..16/16`, `1..16/8`, `1..8/4`.

## Cross-references

- [qy70-device.md](qy70-device.md) — hardware specs
- [track-structure.md](track-structure.md) — layout interno
- [midi-setup.md](midi-setup.md) — PATT OUT CH configuration
- OM QY70 pag 3-12 (modi overview)
