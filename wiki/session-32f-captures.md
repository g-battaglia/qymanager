# Session 32f — Critical Hardware Captures (2026-04-23)

## Contesto

Sessione di acquisizione massiva dati da QY70 production machine. User ha:
1. Verificato MIDI routing corretto (porte invertite fixed)
2. Confermato PATT OUT CH=9~16, ECHO BACK=OFF, MIDI SYNC=External
3. Fornito accesso a 3 pattern distinti (SGT, AMB#01, STYLE2 multi-section)

Risultato: **dataset ground truth definitivo** per reverse engineering completo.

## Pattern 1 — SGT (user's version, non-standard)

### Bulk backup
- File: `data/captures_2026_04_23/SGT_backup_20260423_112505.syx`
- Size: **13891 bytes**, 480 SysEx
- Msgs: 466 XG (Model 4C), 14 Seq5F (Model 5F) con:
  - AL=0x7F (header): 5 msgs
  - AL=0x27, 0x28, 0x2c, 0x2d, 0x2e (section 4-5 tracks)
  - AH=0x00 AM=0x40 AL=0x20 (new unknown address)

### Voice per canale SGT (extracted via user pattern change stream 158 msgs)

```
ch9  D1/RHY1  Bank 127/0  Prog 26  →  Drum Kit 26 (non-std)  Vol 75  Pan 64  Rev 0   Chor 0
ch10 D2/RHY2  Bank 127/0  Prog 26  →  Drum Kit 26             Vol 60  Pan 64  Rev 40  Chor 0
ch11 PC/PAD   Bank 127/0  Prog 26  →  Drum Kit 26             Vol 63  Pan 64  Rev 60  Chor 0
ch12 BA/BASS  Bank 0/96   Prog 38  →  SynBass1 (XG LSB 96)    Vol 95  Pan 64  Rev 0   Chor 0
ch13 C1/CHD1  Bank 0/0    Prog 81  →  SawLd (GM lead)         Vol 60  Pan 64  Rev 70  Chor 55
ch14 C2/CHD2  Bank 0/16   Prog 89  →  Pad variant (LSB 16)    Vol 95  Pan 64  Rev 40  Chor 0
ch15 C3/PHR1  Bank 0/0    Prog 24  →  NylonGtr                Vol 50  Pan 64  Rev 40  Chor 0
ch16 C4/PHR2  Bank 0/35   Prog 98  →  SciFi variant (LSB 35)  Vol 45  Pan 64  Rev 0   Chor 0
```

### Differenza rispetto al fixture `tests/fixtures/QY70_SGT.syx`

La versione user ha **voice diverse dal fixture**:
- Fixture: Drum Standard Kit (Prog 0) per tutti drum tracks
- User: **Drum Kit 26** (non-standard, XG extended)
- Fixture usa voci defaulty GM
- User ha voci XG con LSB variants (16, 35, 40, 96)

**Conclusione**: User ha modificato SGT nel suo QY70 con voci custom. Il fixture non rappresenta "standard SGT".

---

## Pattern 2 — AMB#01 (ambient single-section)

### Bulk dump
- File: `data/captures_2026_04_23/AMB01_bulk_20260423_113016.syx`
- Size: **2998 bytes**, 21 Seq5F messages
- Structure: **single-section** (AL=0x00-0x07 section 0 only + AL=0x7F header)
- Track sizes: RHY1=3msg, RHY2=2msg, PAD=1msg, BASS=2msg, CHD1=1msg, CHD2=1msg, PHR1=1msg, PHR2=4msg

### Voice per canale
```
ch9  RHY1  Bank 127/0  Prog 25  →  Drum Kit 25           Vol 90  Rev 40  Chor 0
ch10 RHY2  Bank 127/0  Prog 26  →  Drum Kit 26           Vol 60  Rev 40  Chor 0
ch11 PAD   Bank 127/0  Prog 26  →  Drum Kit 26           Vol 50  Rev 40  Chor 0
ch12 BASS  Bank 0/0    Prog 34  →  PickBass              Vol 75  Rev 40  Chor 0
ch13 CHD1  Bank 0/0    Prog 89  →  WarmPad               Vol 90  Rev 97  Chor 127
ch14 CHD2  Bank 0/0    Prog 89  →  WarmPad               Vol 90  Rev 97  Chor 127
ch15 PHR1  Bank 0/40   Prog 44  →  TremStr (LSB 40)      Vol 92  Rev 40  Chor 0
ch16 PHR2  Bank 126/0  Prog 0   →  SFX bank (MSB 126)    Vol 80  Rev 40  Chor 0
```

**Rev 97 + Chor 127** su ch13/14 = heavy ambient effects, consistent with "AMB" naming.

### Playback ground truth
- File: `data/captures_2026_04_23/AMB01_play_20260423_113240.json`
- Duration: 16 bar @ 120 BPM (30+ seconds)
- **587 note-ons catturate** su 8 canali tutti attivi

| Ch | Count | Unique notes | Role |
|----|-------|--------------|------|
| 9 | 208 | {36, 42} | Kick + HHclosed |
| 10 | 71 | {75} | Claves (n75) |
| 11 | 160 | {46, 51} | HHopen + Ride |
| 12 | 80 | {33, 36, 40} | Bass A1/C2/E2 |
| 13 | 12 | {57, 60, 64} | Am chord (A3-C4-E4) |
| 14 | 32 | {60, 64, 67, 69, 71, 72} | Modal scale (C-E-G-A-B-C) |
| 15 | 20 | {69, 74, 76, 77} | PHR1 melody A4-F5 |
| 16 | 4 | {71} | Sparse B4 |

---

## Pattern 3 — STYLE2 (multi-section complex)

### Bulk dump
- File: `data/captures_2026_04_23/STYLE2_bulk_20260423_113615.syx`
- Size: **12659 bytes**, 84 Seq5F messages
- Structure: **6 sezioni complete** (AL=0x00-0x2F)
- Sections mapped:
  - Sec 0 (INTRO): AL 0x00-0x07
  - Sec 1 (MAIN A): AL 0x08-0x0F
  - Sec 2 (MAIN B): AL 0x10-0x17
  - Sec 3 (FILL AB): AL 0x18-0x1F
  - Sec 4 (FILL BA): AL 0x20-0x27
  - Sec 5 (ENDING): AL 0x28-0x2F

### Message count per AL (indica density per track per section)

```
AL 0x00-0x07 INTRO:    1,2,1,2,1,1,1,4
AL 0x08-0x0F MAIN A:   2,2,1,2,1,1,1,1
AL 0x10-0x17 MAIN B:   2,2,1,2,1,1,1,4
AL 0x18-0x1F FILL AB:  2,2,1,2,1,1,1,4
AL 0x20-0x27 FILL BA:  2,2,1,2,1,1,1,4
AL 0x28-0x2F ENDING:   (varies, less dense)
```

**PHR2 (track 7) ha 4 msg in INTRO/MAIN B/FILL/ENDING** = 512B decoded = lead melody dense.
**PAD (track 2) ha 1 msg** sempre = sparse perc.

### Playback per sub-pattern (145 BPM)

| Sub-pattern | Bars | Notes total | Active channels | File |
|-------------|------|-------------|-----------------|------|
| INTRO | 20 | **995** | 9, 10, 12, 13, 14, 16 | STYLE2_INTRO_play |
| MAIN A | 20 | **550** | 9, 10, 11, 12, 13, 15 | STYLE2_MAINA_play |
| MAIN B | 20 | **1004** | 9, 10, 11, 12, 13, 16 | STYLE2_MAINB_play |
| FILL AB | 12 | **618** | 9, 10, 11, 12, 13, 15, 16 | STYLE2_FILLAB_play |
| FILL BA | 12 | **647** | 9, 10, 11, 12, 13, 14, 16 | STYLE2_FILLBA_play |
| ENDING | 16 | **439** | 9, 10, 11, 12, 13, 15 | STYLE2_ENDING_play |

**Totale: 4253 note-on events** con timing preciso.

### Unique notes per canale (aggregato cross-sub-pattern)

| Ch | Track | Unique notes | Analysis |
|----|-------|--------------|----------|
| 9 | RHY1 | {36, 40} | Kick2 + Snare |
| 10 | RHY2 | {44} | HHpedal |
| 11 | PAD | {46} | HHopen |
| 12 | BASS | {31, 35, 36, 40, 43, 47, 48, 52} | G1-E2 bassline range |
| 13 | CHD1 | {59, 60, 62, 64, 66, 67, 71, 74} | B3-D5 diatonic chord tones |
| 14 | CHD2 | {71, 72, 78, 79} | B4-C5 e F#5-G5 (upper voicing) |
| 15 | PHR1 | {84, 90, 91} | C6-F#6 (high fills, sparse) |
| 16 | PHR2 | {71, 72, 74, 76, 78, 79, 83, 86} | B4-D6 melody range |

### Sub-pattern channel activation RULES

- **Drum base SEMPRE attivo**: ch9 (RHY1), ch10 (RHY2)
- **PAD percussion**: attivo MAIN/FILL/ENDING, NON in INTRO
- **BASS**: sempre attivo (ch12)
- **CHD1**: sempre attivo (ch13)
- **CHD2** (ch14): attivo solo INTRO + FILL BA
- **PHR1** (ch15): attivo solo MAIN A + FILL AB + ENDING
- **PHR2** (ch16): attivo INTRO + MAIN B + FILL AB + FILL BA (più dense sezioni)

FILL AB = bridge A→B, include ch15 (da A) + ch16 (da B)
FILL BA = bridge B→A, include ch14 (unique!) + ch16 (lead continua)

---

## RE findings critici

### 1. Channel mapping VERIFIED correctly (fix needed in CLI)

PATT OUT CH=9~16 significa:
```
Track 0 D1  → ch9
Track 1 D2  → ch10
Track 2 PC  → ch11
Track 3 BA  → ch12
Track 4 C1  → ch13
Track 5 C2  → ch14
Track 6 C3  → ch15
Track 7 C4  → ch16
```

**BUG qymanager info**: riporta canali ERRATI (D1→10, PC→3, C1-C4→4-7).

### 2. Voice encoding nel pattern — class identifier bytes

Track header bytes 17-20 (4 byte) encode voice class:

| B17-B20 hex | Class | Esempi (Bank/Prog) |
|-------------|-------|-------------------|
| `f8 80 8e 83` | DRUM | 127/0 Std Kit, 127/0 Kit26 |
| `78 00 07 12` | BASS | 0/0 Prog 32-39 (bass family) |
| `78 00 0f 10` | CHORD/MELODIC | 0/0 GM normal voices |
| `78 00 0e 03` | CHORD variant | 0/16 Prog 89 (Pad var) |
| `0b b5 8a 7b` | EXTENDED | 0/35 Prog 98 (XG non-GM) |

Il pattern byte NON contiene Bank MSB/LSB/Program direttamente — serve extraction via XG Multi Part dump OR correlate with captured pattern-load stream.

### 3. Voice captured via pattern-load Program Change + CC

Quando user cambia pattern, QY70 emette sequenza:
1. **21 XG SysEx** (Model 4C): System On, Effect config, Part Mode per part
2. **136 channel events** (128 CC + 8 Program Change): voice setup per canale

Voice COMPLETE per extraction: Bank MSB (CC0), Bank LSB (CC32), Program (Pgm Chg), Vol (CC7), Pan (CC10), Rev Send (CC91), Chor Send (CC93).

### 4. Pattern bytes vs playback — encoding density varia

AMB#01: 8 track bulk = 2998B, produce 587 notes in 16 bar → **ratio 5.1 byte/note**
STYLE2 totale: ~12KB pattern, produce 4253 notes cross-subpat @ varying bars

Questo ratio è **track-dependent**:
- Dense drum (RHY1): ~2-3 byte/note (polyphonic packed)
- Sparse phrase tracks: 4-8 byte/note

### 5. Sub-pattern encoding pattern-specific

Ogni sub-pattern in STYLE2 ha:
- Stesso 24B track header + 4B preamble per track (class identifier)
- DIVERSO body (event data per section)
- Diversa density per track (nota count varia)

**Implicazione encoder**: per modificare una sub-pattern senza rompere le altre, encoder deve operare ONLY su section-specific bytes (AL=section*8+track), mantenere invariant il track header class.

---

## Dati da usare per validation encoder/decoder

1. **Ground truth playback** = 4253 + 587 notes con timing → validation target
2. **Bulk bytes** = input encoder (decode, modify, re-encode, verify playback identical)
3. **Voice setup** = corretto reference per voice mapping fix in `qymanager info`

## Next steps (priorità alta)

1. **Fix `qymanager info`**:
   - Channel mapping ch9-16 (non ch10+ch1-7)
   - Voice reading via XG Multi Part request OR cached voice from pattern load
   - Volume/Pan/Rev/Chor actual values (non defaults)

2. **Voice byte decoder module** — correlate pattern bytes B14-B23 con voice catturate

3. **R table calibration per STYLE2 sub-pattern** — usare playback per calibrare R per-section

4. **Decoder roundtrip test** — verify encoder produce bytes matching captured bulk

5. **Pattern editor end-to-end** — decode STYLE2 → modify note → encode → send to QY70 → verify playback
