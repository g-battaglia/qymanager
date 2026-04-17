# QY700 Effect Mode

Ref: `manual/QY700/QY700_MANUAL/09_4EffectMode.txt` + `QY700_REFERENCE_LISTING.pdf` Table 1-7 (Effect Type List)

Effect mode gestisce i 3 system effects del tone generator XG:
- **Reverb** (11 types) — sempre system send/return
- **Chorus** (11 types) — sempre system send/return
- **Variation** (43 types) — **System** OR **Insertion**

## Variation Mode

Settaggio critico:

| Mode | Behavior |
|------|----------|
| **System** | Send/Return come Reverb e Chorus. Tutte le 32 parts possono mandare un level via CC 94. |
| **Insertion** | Applicato a UNA sola part. MW/AC1 controllabili in realtime (per effetti dinamici tipo wah-auto, distortion). |

In **Insertion** mode, CC 94 (Variation Send) è ignorato. Solo la part selezionata riceve l'effetto.

## Reverb types (11)

`HALL 1`, `HALL 2`, `ROOM 1`, `ROOM 2`, `ROOM 3`, `STAGE 1`, `STAGE 2`, `PLATE`, `WHITE ROOM`, `TUNNEL`, `BASEMENT`.

## Chorus types (11)

`CHORUS 1`, `CHORUS 2`, `CHORUS 3`, `CHORUS 4`, `CELESTE 1`, `CELESTE 2`, `CELESTE 3`, `CELESTE 4`, `FLANGER 1`, `FLANGER 2`, `FLANGER 3`.

## Variation types (43)

Reverb family: `HALL 1`, `HALL 2`, `ROOM 1-3`, `STAGE 1-2`, `PLATE`, `DELAY LCR`, `DELAY L,R`, `ECHO`, `CROSSDELAY`, `ER1`, `ER2`, `GATE REV`, `REVRS GATE`, `KARAOKE 1-3`, `THRU`.

Modulation family: `CHORUS 1-4`, `CELESTE 1-4`, `FLANGER 1-3`, `SYMPHONIC`, `ROTARY SP`, `TREMOLO`, `AUTO PAN`, `PHASER 1`, `PHASER 2`.

Distortion/EQ family: `DISTORTION`, `OVERDRIVE`, `AMP SIM`, `3-BAND EQ`, `2-BAND EQ`, `AUTO WAH`.

## Connection params

| Parameter | Range | Applies to |
|-----------|-------|------------|
| Reverb Return | 0..127 | Master reverb level |
| Reverb Pan | ±63 | Master reverb L/R |
| Chorus Return | 0..127 | |
| Chorus Pan | ±63 | |
| Variation Return | 0..127 | solo se Variation Mode = System |
| Variation Pan | ±63 | solo se Variation Mode = System |
| Send Chorus→Reverb | 0..127 | |
| Send Variation→Chorus | 0..127 | solo se System |
| Send Variation→Reverb | 0..127 | solo se System |

## Variation Insertion params

In Insertion mode, add these:

| Parameter | Range |
|-----------|-------|
| Dry/Wet | D63>W .. D=W .. D<W63 |
| AC1 Control depth | ±63 (CC 16 modula wet/dry) |

## Effect Type SysEx encoding

Nel SysEx (Bulk Dump `02 01 XX` o Parameter Change), ogni effect type è identificato da:
- **MSB** (type category)
- **LSB** (sub-type variant)

Range addresses:

| Effect | MSB range | Esempio |
|--------|-----------|---------|
| Reverb | `00..7F` | `RevHall1` = `01 00`, `RevRoom1` = `02 00` |
| Chorus | `00..7F` | `ChoChorus1` = `41 00` |
| Variation System-only | `00..3F` | |
| Variation Insertion | `40..7F` | `VarDistortion` = `49 00` |

Tabella completa in `xg-effects.md`.

## Rilevanza per qyconv

### Pattern Effects nel Q7P

Lo style Q7P include Pattern Effect settings (tipo + params di R/C/V). Converter deve:
- Mappare gli effect QY70 → QY700 (stessa tabella XG, ma alcuni type sono QY700-only)
- Preservare Insertion vs System flag
- Convertire send levels

### Effect mode fisso vs Pattern Setup

Vedi [qy700-song-mode.md](qy700-song-mode.md) — Pattern Setup switch ON/OFF determina quali effect suonano in una song.
