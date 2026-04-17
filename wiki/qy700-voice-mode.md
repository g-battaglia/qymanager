# QY700 Voice Mode

Ref: `manual/QY700/QY700_MANUAL/08_3VoiceMode.txt`

Voice mode gestisce il tone generator interno (AWM2, 32 voci, 491 preset).

## Sub-modi (F1..F5)

| Key | Sub-mode |
|-----|----------|
| F1 | Mixer |
| F2 | Tune |
| F3 | Voice Edit |
| F4 | Drum Setup 1 Edit |
| F5 | Drum Setup 2 Edit |

## Voice Categories (Bank MSB)

| MSB | Category | Note |
|-----|----------|------|
| 000 | Normal | 480 voices (Bank LSB seleziona variante) |
| 064 | SFX Voice | Sound effect non-drum |
| 126 | SFX Kit | Drum kit di SFX |
| 127 | Drum Voice | 11 drum kit standard |
| — | Drum Setup 1 | Overlay editabile on drum kit (NRPN/SysEx) |
| — | Drum Setup 2 | Secondo overlay |
| — | Off | Part disabled |

### Drum Kits preset

| Program # | Name |
|-----------|------|
| 001 | StandKit |
| 002 | Stnd2Kit |
| 009 | RoomKit |
| 017 | RockKit |
| 025 | ElectKit |
| 026 | AnalgKit |
| 033 | JazzKit |
| 041 | BrushKit |
| 049 | ClascKit |
| — | SFX1 |
| — | SFX2 |

Drum Setup 1/2 sono overlay editabili sopra uno di questi kit. Salvati come parte del pattern/song.

## F1 Mixer

Per-part params (32 parts totale):

| Parameter | Range |
|-----------|-------|
| Voice | Bank+Program |
| Program | 1..128 (per bank) |
| Bank | MSB+LSB |
| Reverb Send | 0..127 |
| Chorus Send | 0..127 |
| Variation Send | 0..127 |
| Variation Switch | On/Off |
| Pan | Random, ±63 (64=center) |
| Volume | 0..127 |
| Expression | 0..127 |

## F2 Tune

Per-part tuning params:

| Parameter | Range |
|-----------|-------|
| Detune | ±12.7 Hz (passo 0.1 Hz) |
| Note Shift | ±24 semi |
| Transpose | ±24 semi |

**Note Shift** = fixed octave-shift per la part (persistente).
**Transpose** = applicato solo al momento della playback, non cambia la nota salvata.

## F3 Voice Edit

Edit per-part dei parametri XG (overlay sulla voice base). Corrisponde agli offset SysEx `08 nn XX` (vedi [xg-multi-part.md](xg-multi-part.md) e [qy700-midi-protocol.md](qy700-midi-protocol.md)).

Params principali:

| Parameter | Range |
|-----------|-------|
| Mono/Poly | Mono / Poly |
| Element Reserve | 0..32 |
| Velocity Sens Depth | 0..127 |
| Velocity Sens Offset | 0..127 |
| Portamento Switch | On/Off |
| Portamento Time | 0..127 |
| MW LFO | Pitch/Filter/Amp mod depth |
| Filter Cutoff | -64..+63 |
| Filter Resonance | -64..+63 |
| EG Attack | -64..+63 |
| EG Decay | -64..+63 |
| EG Release | -64..+63 |
| Vibrato Rate | -64..+63 |
| Vibrato Depth | -64..+63 |
| Vibrato Delay | -64..+63 |
| Pitch Bend Range | ±24 semi |
| Dry Level | 0..127 (solo se Variation Mode = System) |

## F4, F5 Drum Setup Edit

Per ogni nota drum (C♯-1..C5) del Drum Setup 1 o 2:

| Parameter | Range |
|-----------|-------|
| Pitch Coarse | ±64 semi |
| Pitch Fine | ±64 cent |
| Level | 0..127 |
| Alternate Group | 0..127 (mute mutualmente esclusivo con altre note stessa group) |
| Pan | Random, ±63 |
| Reverb Send | 0..127 |
| Chorus Send | 0..127 |
| Variation Send | 0..127 |
| Key Assign | Single (1 voce/note) / Multi (N voci) |
| Rcv Note Off | On/Off |
| Filter Cutoff | -64..+63 |
| Filter Resonance | -64..+63 |
| EG Attack Rate | -64..+63 |
| EG Decay1 Rate | -64..+63 |
| EG Decay2 Rate | -64..+63 |

**Alternate Group**: es. kit con 2 hi-hat (open + closed) — assegnando entrambe allo stesso group, l'open viene mutata quando suona closed (comportamento naturale HH).

## XG PARM OUT

Ogni modifica Voice/Drum Setup può essere trasmessa come XG SysEx via MIDI OUT se `XG Parameter Out` != Off (vedi [qy700-utility-mode.md](qy700-utility-mode.md) F2). Utile per sincronizzare altri tone generator XG.

**Nota**: QY70 ha gap noti nell'XG PARM OUT stream (vedi [quirks.md](quirks.md)); QY700 non è stato ancora testato a riguardo.

## Rilevanza per qyconv

### Mapping voci QY70 → QY700

Entrambi usano XG Level 1, quindi mapping 1:1 di Bank/Program/CC è possibile. Drum kit numbers identici (StandKit=001, ecc.).

### Drum Setup export

Drum Setup 1/2 del QY700 sono più ricchi della versione QY70. Per export verso QY70:
- Semplificare params (QY70 ha meno param/nota)
- Usare NRPN drum params invece di Drum Setup SysEx

### Voice data in Q7P

Lo style Q7P contiene:
- **Pattern Voice**: assegnazione voice per le 16 pattern tracks
- **Pattern Effect**: Reverb/Chorus/Variation type + params per lo style

Non include XG System o Drum Setup (quelli sono nel Q7S / Q7A a livello di song o globali).
