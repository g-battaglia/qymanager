# XG System Parameters

Parametri globali del sistema XG. Riferimento: [xg-parameters.md](xg-parameters.md).

## System Messages

| Parametro | SysEx | Data Range | Default | Note |
|-----------|-------|------------|---------|------|
| Master Volume (Universal) | `F0 7F 7F 04 01 00 XX F7` | 00-7F | 7F | MIDI standard universal |
| Master Volume (XG) | `F0 43 10 4C 00 00 04 XX F7` | 00-7F | 7F | XG-specific |
| Master Transpose | `F0 43 10 4C 00 00 06 XX F7` | 28-58 | 40 | -24..+24 semitoni |
| Master Tune | `F0 43 10 4C 00 00 00 0W 0X 0Y 0Z F7` | 0000-07FF | 0400 | -102.4..+102.3 cent |
| Drum Setup 1 Reset | `F0 43 10 4C 00 00 7D 00 F7` | — | — | Reset Drum Setup 1 |
| Drum Setup 2 Reset | `F0 43 10 4C 00 00 7D 01 F7` | — | — | Reset Drum Setup 2 |
| **XG System On** | `F0 43 10 4C 00 00 7E 00 F7` | — | — | Attiva modalità XG |
| All Parameter Reset | `F0 43 10 4C 00 00 7F 00 F7` | — | — | Reset factory |
| TG300B Mode | `F0 41 10 42 12 40 00 7F 00 41 F7` | — | — | Roland GS compat |
| General MIDI On | `F0 7E 7F 09 01 F7` | — | — | GM mode activation |

**Master Tune encoding**: valore 14-bit split in 4 nibble. Default `00 04 00 00` = centro (0 cent).

## Standard MIDI Controllers

Il QY70, come ogni XG device, riceve Control Change standard su ogni canale. Alcuni CC critici:

### Volume & Expression
| CC# | Parametro | Default |
|-----|-----------|---------|
| 7 | Main Volume | 100 |
| 10 | Pan | 64 |
| 11 | Expression | 127 |
| 91 | Reverb Send | 64 |
| 93 | Chorus Send | 0 |
| 94 | Variation Send | 0 |

### Instrument Selection
| CC# | Parametro | Note |
|-----|-----------|------|
| 0 | Bank Select MSB | 0=Normal, 63=User, 64=SFX, 126/127=Drum Kit |
| 32 | Bank Select LSB | Sub-bank |
| — (Program Change) | Program Number | 0-127 |

### Filter / EG
| CC# | Parametro | Range |
|-----|-----------|-------|
| 71 | Harmonic Content / Resonance | -64..+63 |
| 72 | Release Time | -64..+63 |
| 73 | Attack Time | -64..+63 |
| 74 | Brightness / Cutoff | -64..+63 |

### Modulation
| CC# | Parametro | Note |
|-----|-----------|------|
| 1 | Modulation Wheel | Vibrato depth |
| 5 | Portamento Time | |
| 65 | Portamento Switch | 0-63=OFF, 64-127=ON |
| 84 | Portamento Control | Glide between notes |

### Pedals
| CC# | Parametro |
|-----|-----------|
| 64 | Hold (Sustain) Pedal |
| 66 | Sostenuto Pedal |
| 67 | Soft Pedal |

### RPN/NRPN
| CC# | Parametro |
|-----|-----------|
| 6 | Data Entry MSB |
| 38 | Data Entry LSB |
| 96 | Data Increment |
| 97 | Data Decrement |
| 98 | NRPN LSB |
| 99 | NRPN MSB |
| 100 | RPN LSB |
| 101 | RPN MSB |

### Channel Mode
| CC# | Parametro |
|-----|-----------|
| 120 | All Sounds Off |
| 121 | Reset All Controllers |
| 123 | All Notes Off |
| 124 | Omni Off |
| 125 | Omni On |
| 126 | Mono Mode |
| 127 | Poly Mode |

## UTILITY System Parameters (QY70 local settings)

Parametri locali modificabili dal UI, non XG SysEx ma paralleli. Da OM pag 221:

| Setting | Range | Default | Note |
|---------|-------|---------|------|
| CLICK MODE | Off / Record / Rec+Play / Always | Rec | Metronomo click |
| CLICK BEAT | 16 / 8 / 4 / 2 / 1 | 4 | Suddivisione click |
| REC COUNT | Off, 1 Meas..8 Meas | 1 Meas | Count-in pre-record |
| MASTER TUNE | -102.4 .. +102.3 cent | 000.0 (A4=440) | Equivalente a XG Master Tune via UI |
| **SYS EXCLUSIVE INTERVAL TIME** | 0*100..9*100 ms | — | **Delay tra blocchi SysEx in transmission** |

L'**Interval Time** è la fonte ufficiale del timing ~150ms osservato nei bulk dump: il QY70 inserisce questo delay in uscita e si aspetta che il mittente faccia altrettanto in ricezione (vedi [quirks.md](quirks.md) per i casi edge).

## Source

- [studio4all.de main91.html](http://www.studio4all.de/htmle/main91.html)
- `manual/QY70/QY70_LIST_BOOK.PDF` pag. 56 Table 1-2
- `manual/QY70/QY70_OWNERS_MANUAL.PDF` pag 221 (UTILITY → System)
