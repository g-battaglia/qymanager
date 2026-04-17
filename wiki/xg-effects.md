# XG Effects (Reverb, Chorus, Variation)

Tre blocchi effetti del tone generator XG: Reverb (send effect), Chorus (send effect), Variation (system o insertion). Riferimento: [xg-parameters.md](xg-parameters.md).

**Base address tutti gli effetti**: `02 01 XX`
**Formato**: `F0 43 10 4C 02 01 [AL] XX F7` (parametri 1-byte)
`F0 43 10 4C 02 01 [AL] YY XX F7` (type MSB+LSB, 2-byte)

## Reverb (AL 00-15)

### Type Code

Inviare MSB+LSB a `02 01 00`:

| Type | Code MSB LSB |
|------|--------------|
| OFF | 00 00 |
| Hall 1 (default) | 01 00 |
| Hall 2 | 01 01 |
| Room 1 / 2 / 3 | 02 00 / 01 / 02 |
| Stage 1 / 2 | 03 00 / 01 |
| Plate | 04 00 |
| White Room | 10 00 |
| Tunnel | 11 00 |
| Basement | 13 00 |

### Common Parameters

| AL | Parametro | Range | Note |
|----|-----------|-------|------|
| 00-01 | Type MSB / LSB | — | Vedi sopra |
| 02 | Reverb Time | 00-45 | 0.3-30 s |
| 03 | Diffusion | 00-0A | 0-10 |
| 04 | Initial Delay | 00-3F | 0.1-99.3 ms |
| 05 | HPF Cutoff | 00-34 | 20-8000 Hz |
| 06 | LPF Cutoff | 22-3C | 1000-20000 Hz |
| 0B | Dry/Wet | 01-7F | |
| 0C | Reverb Return | 00-7F | -inf..+6 dB, default 40 |
| 0D | Reverb Pan | 01-7F | default 40 |
| 10 | Reverb Delay | 00-3F | 0.1-99.3 ms |
| 11 | Density | 00-03 | 0-3 |
| 12 | ER/Rev Balance | 01-7F | ER-only..REV-only |
| 14 | Feedback Level | 01-7F | -63..+63 |

### Optional Parameters (White Room, Tunnel, Basement)

| AL | Parametro | Range |
|----|-----------|-------|
| 07 | Width | 00-25 (0.5-10.2 m) |
| 08 | Height | 00-49 (0.5-20.5 m) |
| 09 | Depth | 00-68 (0.5-30.2 m) |
| 0A | Wall Variation | 00-1E |

## Chorus (AL 20-2E)

### Type Code

Inviare MSB+LSB a `02 01 20`:

| Type | Code MSB LSB |
|------|--------------|
| OFF | 00 00 |
| Chorus 1 (default) | 41 00 |
| Chorus 2 / 3 | 41 01 / 02 |
| Chorus 4 | 41 08 |
| Celeste 1-4 | 42 00 / 01 / 02 / 08 |
| Flanger 1 / 2 | 43 00 / 01 |
| Flanger 3 | 43 08 |

### Common Parameters

| AL | Parametro | Range | Note |
|----|-----------|-------|------|
| 20-21 | Type MSB / LSB | — | Vedi sopra |
| 22 | LFO Frequency | 00-7F | 0-39.7 Hz |
| 23 | LFO Phase Mod Depth | 00-7F | |
| 24 | Feedback Level | 01-7F | -63..+63 |
| 27 | EQ Low Frequency | 08-28 | 50-2000 Hz |
| 28 | EQ Low Gain | 34-4C | -12..+12 dB |
| 29 | EQ High Frequency | 1C-3A | 500-16000 Hz |
| 2A | EQ High Gain | 34-4C | -12..+12 dB |
| 2B | Dry/Wet | 01-7F | |
| 2C | Chorus Return | 00-7F | default 40 |
| 2D | Chorus Pan | 01-7F | default 40 |
| 2E | Send Chorus→Reverb | 00-7F | default 00 |

### Chorus/Celeste-only

| AL | Parametro | Range |
|----|-----------|-------|
| 25 | Delay Offset | 00-7F (0-50 ms) |
| 34 | Input Mode | 00=Mono, 01=Stereo |

### Flanger-only

| AL | Parametro | Range |
|----|-----------|-------|
| 25 | Delay Offset | 00-3F (0-6.3 ms) |
| 33 | LFO Phase Difference | 04-7C (-180..+180°) |

## Variation (AL 40-75)

Il Variation può essere **Insertion** (effetto dedicato a una parte) o **System** (effetto send globale come Reverb/Chorus), controllato da AL=5A.

### Type Code

Inviare MSB+LSB a `02 01 40`:

| Type | Code MSB LSB |
|------|--------------|
| Off | 00 00 |
| Thru | 40 00 |
| Hall 1 / 2 | 01 00 / 01 |
| Room 1-3 | 02 00 / 01 / 02 |
| Stage 1 / 2 | 03 00 / 01 |
| Plate | 04 00 |
| Delay L,C,R (default) | 05 00 |
| Delay L,R | 06 00 |
| Echo | 07 00 |
| Cross Delay | 08 00 |
| Early Ref 1 / 2 | 09 00 / 01 |
| Gate Reverb | 0A 00 |
| Reverse Gate | 0B 00 |
| Karaoke 1-3 | 14 00 / 01 / 02 |
| Chorus 1-4 | 41 00 / 01 / 02 / 08 |
| Celeste 1-4 | 42 00 / 01 / 02 / 08 |
| Flanger 1-3 | 43 00 / 01 / 08 |
| Symphonic | 44 00 |
| Rotary Speaker | 45 00 |
| Tremolo | 46 00 |
| Auto Pan | 47 00 |
| Phaser 1 / 2 | 48 00 / 08 |
| Distortion | 49 00 |
| Overdrive | 4A 00 |
| Amp Simulator | 4B 00 |
| 3-Band EQ | 4C 00 |
| 2-Band EQ | 4D 00 |
| Auto Wah | 4E 00 |

### Parametri 1-10 (Type-dependent)

`AL 42` fino a `54` (MSB/LSB coppie per param 1-10). Il significato dipende dal Variation Type selezionato. Esempi pratici (da QY70_LIST_BOOK pag. 62 Table 1-8):

| Variation Type | Param 1 | Param 2 | Param 3 | Param 4 | Param 5 |
|---------------|---------|---------|---------|---------|---------|
| Delay L,C,R (05 00) | Lch Delay | Rch Delay | Cch Delay | Feedback Delay | Feedback Level |
| Delay L,R (06 00) | Lch Delay | Rch Delay | Feedback Delay 1 | Feedback Delay 2 | Feedback Level |
| Echo (07 00) | Lch Delay1 | Lch Feedback | Rch Delay1 | Rch Feedback | High Damp |
| Cross Delay (08 00) | L→R Delay | R→L Delay | Feedback Level | Input Select | High Damp |
| Early Ref 1/2 (09 00/01) | Type | Room Size | Diffusion | Initial Delay | Feedback |
| Karaoke 1-3 (14 0n) | Delay Time | Feedback | HPF Cutoff | LPF Cutoff | — |
| Chorus 1-4 (41 0n) | LFO Frequency | LFO Depth | Feedback | Delay Offset | EQ Low Freq |
| Flanger (43 0n) | LFO Frequency | LFO Depth | Feedback | Delay Offset | EQ Low Freq |
| Symphonic (44 00) | LFO Frequency | LFO Depth | Delay Offset | EQ Low Freq | EQ Low Gain |
| Rotary Speaker (45 00) | LFO Frequency | LFO Depth | AM Depth | PM Depth | EQ Low Freq |
| Tremolo (46 00) | LFO Frequency | AM Depth | PM Depth | EQ Low Freq | EQ Low Gain |
| Auto Pan (47 00) | LFO Frequency | L/R Depth | F/R Depth | Pan Direction | EQ Low Freq |
| Phaser 1/2 (48 00/08) | LFO Frequency | LFO Depth | Phase Shift Offset | Feedback Level | EQ Low Freq |
| Distortion (49 00) | Drive | EQ Low Freq | EQ Low Gain | LPF Cutoff | Output Level |
| Overdrive (4A 00) | Drive | EQ Low Freq | EQ Low Gain | LPF Cutoff | Output Level |
| Amp Simulator (4B 00) | Drive | AMP Type | LPF Cutoff | Output Level | — |
| 3-Band EQ (4C 00) | EQ Low Gain | EQ Mid Freq | EQ Mid Gain | EQ Mid Width | EQ High Gain |
| 2-Band EQ (4D 00) | EQ Low Freq | EQ Low Gain | EQ High Freq | EQ High Gain | — |
| Auto Wah (4E 00) | LFO Frequency | LFO Depth | Cutoff Offset | Resonance | EQ Low Freq |

Param 6-10 completano la parametrizzazione (LFO phase, mix, pre-LPF, ecc.). Vedi tabella completa in QY70_LIST_BOOK.PDF pag. 57-58.

### Common Parameters (Variation)

| AL | Parametro | Range | Default | Note |
|----|-----------|-------|---------|------|
| 56 | Variation Return | 00-7F | 40 | -inf..+6 dB |
| 57 | Variation Pan | 01-7F | 40 | |
| 58 | Send Variation→Reverb | 00-7F | 00 | |
| 59 | Send Variation→Chorus | 00-7F | 00 | |
| 5A | Variation Connection | 00-01 | 00 | 0=Insertion, 1=System |
| 5B | Variation Part | 00-0F, 40, 41, 7F | 7F | Part assign (OFF quando Insertion) |
| 5C | MW Variation Ctrl Depth | 00-7F | 40 | -64..+63 |
| 5D | PB Variation Ctrl Depth | 00-7F | 40 | |
| 5E | AT Variation Ctrl Depth | 00-7F | 40 | |
| 5F | AC1 Variation Ctrl Depth | 00-7F | 40 | |
| 60 | AC2 Variation Ctrl Depth | 00-7F | 40 | |

### Parametri 11-16 (opzionali)

`AL 70-75` — non supportati da tutti i device, presenti su MU90+ e alcuni PLG.

## Source

- [studio4all.de main94.html](http://www.studio4all.de/htmle/main94.html) (Reverb + Chorus)
- [studio4all.de main95.html](http://www.studio4all.de/htmle/main95.html) (Variation)
- `manual/QY70/QY70_LIST_BOOK.PDF` pag. 57-58, 62 Table 1-4, 1-8
