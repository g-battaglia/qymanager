# QY70 RE Data Captures — 2026-04-23

Sessione critica di acquisizione dati da hardware production QY70.

## Dataset totale

- **3 style/pattern** catturati: SGT, AMB#01, STYLE2 (multi-section completo)
- **Bulk pattern bytes**: 29KB totali
- **Playback notes**: >5000 note-on events con timing preciso
- **Voice setup**: 24 canali×parametri acquisiti via PC+CC+XG stream

## File registry

### SGT (current U01 on QY70)
| File | Size | Note |
|------|------|------|
| `SGT_backup_20260423_112505.syx` | 13891B | Bulk backup SGT version user QY70 |
| (voice user recorded durante pattern change) | 158 msgs | 8 Program Change + 128 CC + 21 XG |

**Voice SGT**:
- ch9 RHY1: Bank 127/0 Prog 26 = **Drum Kit 26** (non-standard)
- ch10 RHY2: Bank 127/0 Prog 26 = Drum Kit 26 (Vol 60, Rev 40)
- ch11 PAD: Bank 127/0 Prog 26 = Drum Kit 26 (Vol 63, Rev 60)
- ch12 BASS: Bank 0/96 Prog 38 = **SynBass1 XG variant** (Vol 95)
- ch13 CHD1: Bank 0/0 Prog 81 = **SawLd** (Vol 60, Rev 70, Chor 55)
- ch14 CHD2: Bank 0/16 Prog 89 = **Pad variant LSB 16** (Vol 95)
- ch15 PHR1: Bank 0/0 Prog 24 = **NylonGtr** (Vol 50, Rev 40)
- ch16 PHR2: Bank 0/35 Prog 98 = **SciFi XG variant** (Vol 45)

### AMB#01 (ambient pattern)
| File | Size | Contents |
|------|------|----------|
| `AMB01_bulk_20260423_113016.syx` | 2998B | Bulk dump (21 Seq5F msgs, 8 tracks section 0 only) |
| `AMB01_load_20260423_113116.json` | — | Pattern change stream (voice setup) |
| `AMB01_play_20260423_113240.json` | — | Playback capture: **587 notes 16 bars @ 120 BPM** |

**Voice AMB#01**:
- ch9: Drum Kit 25
- ch10: Drum Kit 26 (Rev 40)
- ch11: Drum Kit 26 (Vol 50, Rev 40)
- ch12: **PickBass** (GM 34, Vol 75)
- ch13: WarmPad (Prog 89, **Rev 97 + Chor 127** = heavy ambient)
- ch14: WarmPad (Rev 97 + Chor 127)
- ch15: **TremStr** (LSB 40 Prog 44)
- ch16: Bank 126 Prog 0 (SFX bank speciale)

**Structure**: single-section pattern (AL=0x00-0x07 only + header AL=0x7F)

### STYLE2 (complex multi-section)
| File | Size | Contents |
|------|------|----------|
| `STYLE2_bulk_20260423_113615.syx` | 12659B | Bulk 84 Seq5F msgs, **6 sezioni complete** AL=0x00-0x2F |
| `STYLE2_INTRO_play_*.json` | — | 20bar @ 145 BPM **995 notes** ch 9,10,12,13,14,16 |
| `STYLE2_MAINA_play_*.json` | — | 20bar **550 notes** ch 9,10,11,12,13,15 |
| `STYLE2_MAINB_play_*.json` | — | 20bar **1004 notes** ch 9,10,11,12,13,16 |
| `STYLE2_FILLAB_play_*.json` | — | 12bar **618 notes** ch 9,10,11,12,13,15,16 |
| `STYLE2_FILLBA_play_*.json` | — | 12bar **647 notes** ch 9,10,11,12,13,14,16 |
| `STYLE2_ENDING_play_*.json` | — | 16bar **439 notes** ch 9,10,11,12,13,15 |

**Totale STYLE2 notes**: 4253

## Findings critici RE

### 1. **Channel mapping QY70 Pattern mode = ch9-16 (NON ch10 + ch1-7)**

Il comando `qymanager info` oggi ritorna canali errati:
- ❌ D1/D2 → ch10
- ❌ PC → ch3
- ❌ BA → ch2
- ❌ C1-C4 → ch4-7

**CORRETTO** (verificato via PATT OUT capture):
- ✅ D1/RHY1 → **ch9**
- ✅ D2/RHY2 → **ch10**
- ✅ PC/PAD → **ch11**
- ✅ BA/BASS → **ch12**
- ✅ C1/CHD1 → **ch13**
- ✅ C2/CHD2 → **ch14**
- ✅ C3/PHR1 → **ch15**
- ✅ C4/PHR2 → **ch16**

### 2. **Voice reading dal pattern bytes NON implementato**

`qymanager info` ritorna voci hardcoded (Standard Kit, Grand Piano) ignorando i byte del pattern. Voice class è in **B17-B20 track header**:
- `f8 80 8e 83` → Drum kit
- `78 00 07 12` → Bass voice
- `78 00 0f 10` → Chord/Phrase voice
- Altri pattern (es. XG extended) hanno encoding differente

Bank MSB/LSB/Program esatto: richiede capture dal QY70 (pattern load emission) perché i byte pattern hanno encoding packed non 1:1.

### 3. **Volume/Pan/Rev/Chor effettivi NEL pattern**

Attualmente `info` mostra tutti default (Vol 100, Pan C, Rev 40, Chor 0). I valori reali catturati vanno da Vol 45-95, Rev 0-97, Chor 0-127 per pattern. Devono essere letti da byte track header specifici o da XG Multi Part bulk dump integrato.

### 4. **Sub-pattern channel activation pattern**

Per STYLE2:
- Drum base (ch9-11): sempre attivi
- BASS (ch12) + CHD1 (ch13): sempre attivi
- Variazione per sub-pattern:
  - INTRO: +ch14 +ch16 (no ch15)
  - MAIN A: +ch15 (no ch14, ch16)
  - MAIN B: +ch16 (no ch14, ch15)
  - FILL AB: +ch15 +ch16 (bridging A→B)
  - FILL BA: +ch14 +ch16 (bridging B→A)
  - ENDING: +ch15 (like MAIN A, minimalist)

## Azioni RE da fare

1. **Fix `qymanager info`** — channel mapping + voice reading + vol/pan/fx
2. **Voice byte decoder** — decode B14-B23 track header → Bank/Program exact
3. **Sub-pattern playback GT database** — per-section R table calibration
4. **Encoder validation** — usando voice setup catturato + bulk bytes, verify encoder output corrisponde
