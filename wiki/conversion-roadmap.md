# Conversion Roadmap

End-to-end status for QY70 → QY700 conversion **and** QY70 SysEx state extraction.

> **Session 32j (2026-04-23)**: Full SysEx extraction pipeline shipped. Every XG parameter the QY70 emits (voices, mixer, effects, drum setup, pattern directory, system meta) is now parseable and displayable via `qymanager info`. 3 user-facing workflows documented for the "get everything from .syx" use case. See [voice-extraction-workflow.md](voice-extraction-workflow.md) and [quickstart-sysex-extraction.md](quickstart-sysex-extraction.md).

## Pipeline Overview

> **Session 19 finding**: The SysEx bitstream decoder **FAILS on complex styles** (~0% accuracy against ground truth). Two conversion pipelines + one extraction pipeline now exist.

### Pipeline A: SysEx Decode (original) — BLOCKED for complex styles

```
QY70 .syx → [Decode Bitstream] → [Abstract Events] → [Encode Q7P] → QY700 .Q7P
```

| Stage | Status | User Patterns | Factory Styles |
|-------|--------|--------------|----------------|
| Parse SysEx | Done | High | High |
| 7-bit decode | Done | High | High |
| Bitstream unpack | Done | High | High |
| Rotation decode (R=9×(i+1)) | Done | **100%** (7/7 proven) | **~0%** (FAILS) |
| Chord event decode | F4 mask → notes | Untested | 0% precision |
| Bass event decode | Chaotic | Untested | 15% precision |
| Drum event decode | R proven for user | **100%** | ~9% precision |
| Chord transposition | Unknown | Unknown | Unknown |

### Pipeline B: Capture-Based (NEW, Session 19) — RECOMMENDED & VALIDATED

```
QY70 Hardware → [MIDI Playback] → [Capture Notes] → [Quantize] → [Encode D0/E0] → QY700 .Q7P
                                                    ↓ also ↓
                                              [Standard MIDI File]
```

| Stage | Status | Confidence |
|-------|--------|------------|
| Send .syx to QY70 | Done (`send_style.py`) | High |
| Start playback (MIDI Start+Clock) | Done (`send_and_capture.py`) | High |
| Capture MIDI notes | Done (`capture_playback.py`) | High |
| Parse captured events | Done (JSON format) | High |
| **Quantize to beats/bars** | **Done** (`quantizer.py`) | **High** |
| **SMF export** | **Done** (`capture_to_q7p.py`) | **High** |
| **D0/E0 phrase encoding** | **Done** (`capture_to_q7p.py`) | **High** (roundtrip byte-identical, Session 27) |
| Q7P metadata write | Done | High |
| **Q7P 5120B build from capture** | **Done** (`build_q7p_5120.py`) | **High** (Session 21+) |
| **Phrase header layout (26B)** | **Done** (Session 27) | **High** (DECAY roundtrip 12/12) |
| **Hardware-validated roundtrip** | **Done** (Session 28) | **High** (208/208 notes) |

**Session 28 status**: Pipeline B validated end-to-end on live QY70 hardware:
- Identity reply, bulk dump request, playback capture, style send all working
- SGT capture → 310 notes → 4-bar Q7P 5120 → 208/208 roundtrip
- Summer capture → 126/126 roundtrip (Session 26)
- DECAY self-parse byte-identical (Session 27)
- Cross-pattern validator: 0 warnings on Summer/SGT/DECAY

**Session 28b status**: AH sweep reveals full QY70 dumpable-area map (pattern body, meta, name directory).

**Advantages**: bypasses all unsolved decoding problems (rotation model, chord transposition, groove templates). Captures the EXACT notes the QY70 produces.

**Requirements**: QY70 hardware must be connected. PATT OUT=9~16, ECHO BACK=Off, MIDI SYNC=External.

**Known limit** (resolved Session 29): phrase area of 5120B Q7P is 2048B (4-bar max). Extended `build_q7p()` auto-detects scaffold size; **6144B SGT..Q7P scaffold supports 6-bar+** (phrase area 4608B). Test `test_roundtrip_hardware_capture_s28_6bar_6144` validates 6-bar SGT roundtrip with 0 warnings.

### Pipeline C: SysEx State Extraction (NEW, Session 32i/j) — PRODUCTION-READY

Not a conversion pipeline — an **extraction/audit pipeline**: given a `.syx` file, recover every parameter the QY70 emits (voices, mixer, effects, drum setup, pattern directory, system meta). Three user-facing workflows bridge the one structural gap (voice identity in pattern bulk alone is opaque — ROM index).

```
┌─── Workflow A (live, recommended) ───────────────────────────────────┐
│ uv run python3 midi_tools/capture_complete.py -o full.syx             │
│ → Init + 9 pattern + AH=0x05 + AH=0x03 + 16 XG MultiPart + close     │
│   (29 dump requests in one session)                                   │
│ uv run qymanager info full.syx  → complete voice/mixer/fx info       │
├─── Workflow B (merge pre-existing captures) ─────────────────────────┤
│ uv run qymanager merge bulk.syx xg_capture.json -o full.syx          │
│   → appends JSON stream (CC + PC + XG SysEx) to bulk                 │
│ uv run qymanager info full.syx  → same as Workflow A                 │
├─── Workflow C (fallback, bulk only) ─────────────────────────────────┤
│ uv run qymanager info pattern.syx     → partial info                 │
│ uv run qymanager audit pattern.syx    → tabular gap report           │
│   → voice class 100% (B17-B20 signature)                             │
│   → voice Bank/LSB/Prog via DB (23 trained entries)                  │
│   → Vol/Pan/FX default to XG init                                    │
└──────────────────────────────────────────────────────────────────────┘
```

| Stage | Status | Notes |
|-------|--------|-------|
| Parse Model 0x5F (pattern bulk, song, system, name directory) | **Done** | 7 AH families covered, CI invariant enforces no silent drops |
| Parse Model 0x4C (XG Param Change) | **Done** | 17 Multi Part params × 16 parts; System; Effects; Drum Setup (16 params × 128 notes × 2 setups) |
| Voice Edit Dump (AH=0x00 AM=0x40) | **Done** | Classified by voice class signature |
| Pattern Name Directory (AH=0x05) encoding fix | **Done (Session 32j)** | Raw ASCII, NOT 7-bit packed (earlier decoder garbled it) |
| 3-tier voice resolver | **Done** | XG (ground truth) → sig DB (conf=1.0) → class fallback |
| `qymanager info` Rich panels | **Done** | 10 panels covering every extracted data type |
| `qymanager audit` completeness report | **Done** | Tabular ✓/~/✗ + actionable workflow suggestions |
| `qymanager bulk-summary` multi-slot inventory | **Done** | Slot-by-slot table for BULK_ALL files |
| `qymanager merge` CLI | **Done** | Hides the Python tool behind a first-class command |
| `qymanager xg inspect` parsed state | **Done** | Shows final values (vs `xg summary` message counts) |
| Integration tests | **Done** | 22 dedicated tests in `test_voice_extraction_pipeline.py` |

**Documented structural limit**: pattern bulk alone does NOT contain resolvable Bank/LSB/Prog. The 640B `AL=0x7F` header encodes voice via an opaque ROM-internal index (7+ iterations of byte-level analysis all failed). Bridge via Workflow A or B; Workflow C's DB gives partial recovery. See [pattern-header-al7f.md](pattern-header-al7f.md).

## Blocking Issues

### 1. Factory Style Decoding FAILS (blocks Pipeline A for all complex styles)

**Session 19**: R=9×(i+1) rotation produces ~0% accuracy on complex styles (SGT) despite 100% on user patterns. The encoding for dense factory data is fundamentally different or uses additional obfuscation not yet understood. See [Decoder Status](decoder-status.md#what-doesnt-work--critical-session-19).

**Impact**: Pipeline A is usable ONLY for user-created patterns, not factory/preset styles.

### 2. Q7P Event Writing (blocks output generation for both pipelines)

Two paths exist:

| Path | Format | Status | Blocker |
|------|--------|--------|---------|
| **3072-byte** | Sequence events (0x83/0x84/0x88 grid) | Structure mapped, semantics partial | Command semantics unknown, need more Q7P samples |
| **5120-byte** | D0/E0 inline phrases | Well understood | No template file, metadata offsets differ by +0x880 |

**Recommendation**: Get a 5120-byte Q7P from QY700 hardware. Create a pattern with known notes → save as Q7P → use as template.

### ~~3. Capture Quantization~~ — SOLVED (Session 21-22)

`quantizer.py` quantizes raw MIDI timestamps to a 16th-note grid (480 PPQN). Loop detection via per-channel pattern matching + LCM. `capture_to_q7p.py` generates SMF + D0/E0 phrase data. **Drum capture works** (Session 22 disproved Session 17 finding).

### 4. Chord Transposition (blocks Pipeline A chord tracks)

Bar headers store chord-RELATIVE templates. Irrelevant for Pipeline B (capture already has absolute notes).

### 5. Bass Encoding (blocks Pipeline A bass track)

Both 2BE3 and 29CB produce chaotic results. Irrelevant for Pipeline B.

## Strategic Assessment (Session 32j, 2026-04-23)

Dopo 32+ sessioni (incluse Ralph loop session 32g→32j), stato realistico del progetto:

**Completato (~80% obiettivo finale)**:
- **Pipeline B capture-based**: production-ready, roundtrip byte-valid (SGT 208/208, Summer 126/126, DECAY self-parse identical)
- **Pipeline C SysEx state extraction**: production-ready, 17 XG Multi Part params + System + Effects + Drum Setup + name directory + voice edit dumps
- **Dense-factory decoder**: 95-100% per track (calibrated R tables from real captures)
- **Sparse encoder** (user patterns): 100% byte-exact roundtrip su 7 casi noti
- **Q7P format** fully decoded (read + write + validator)
- **UDM (F1)**: format-agnostic Device schema, emette XG/Q7P/.syx/SMF
- **Offline editor (F3)**: path-based DSL `multi_part[0].voice.program=12`
- **Realtime editor (F5)**: live XG Parameter Change via CLI
- **Converter lossy policy (F9)**: `--keep/--drop` granulare
- **Pattern editor CLI (F3a-d)**: 21 sub-command (new-empty, transpose, humanize, merge, …)
- **Unified CLI**: 20+ comandi `qymanager` (info, audit, bulk-summary, merge, xg inspect, edit, …)

**Bloccato (limiti strutturali)**:
- **Voice identity in pattern bulk alone**: opaco (ROM index). Workaround: Pipeline C Workflow A/B. Sblocco completo richiede firmware dump.
- **Time signature byte**: non identificato (servono capture pattern 3/4 o 6/8 per diff)
- **Pattern bar count byte**: non identificato (servono capture con bar count noti diversi)
- **Dense bitstream semantic decoder completo**: 3 eventi Summer "structurally impossible" via rotation alone (Session 32e)

**Raccomandazione corrente (Session 32j)**:
1. Per uso produttivo: usare Pipeline B + Pipeline C Workflow A (capture_complete). Tutto funziona end-to-end.
2. Per estendere RE: focus su voice-differential-capture (stesso pattern, voice diverse) per triangolare voice index bytes.
3. Editor UI su Pipeline B resta la via più veloce a consegnare prodotto completo.

**Stime residue** (sessioni simili):
- Editor UI (GUI) su Pipeline B: 10-20 sessioni
- Voice index byte identification (differential capture): 2-5 sessioni con hardware
- Time signature decode: 1-2 sessioni (serve 1 capture 3/4)
- Decoder dense 100% semantic: 10-30 sessioni (non garantito — forse firmware dump)

## What Works Today (Session 32j)

**Pipeline B produces end-to-end output**:
- Standard MIDI File (.mid) — immediately playable and verifiable
- Q7P 5120B/6144B with correct metadata AND phrase data (hardware-roundtrip validated)
- D0/E0 phrase data for all tracks (drum + melody encoding)
- Quantized JSON for debugging/analysis
- Cross-pattern validator with phrase-stream invariants (0 warnings)

**Pipeline C produces complete SysEx extraction**:
- `qymanager info <file>` — 10 Rich panels (Header/Timing/Effects/XG System/XG Drum Setup/Voice Edit/Directory/Sections/Tracks/Extended XG/Stats)
- `qymanager audit <file>` — extraction completeness report + actionable suggestions
- `qymanager bulk-summary <file>` — slot inventory multi-pattern
- `qymanager merge <bulk> <json> -o <out>` — combine pattern + XG capture
- `qymanager xg inspect <file>` — final parsed XG state
- `midi_tools/capture_complete.py` — live dump of every AH family (29 requests)
- `midi_tools/load_json_to_syx.py` — JSON→.syx flattener + merge helper
- 17 XG Multi Part params + System + Effects + Drum Setup fully extracted when available

**Test suite** (`uv run pytest`): **460 passed, 3 skipped** (~2s). Coverage includes:
- 22 integration tests dedicati in `test_voice_extraction_pipeline.py`
- CI invariants: no-address-silently-ignored, no-crash-on-any-sample
- Hardware-in-the-loop markers (opt-in `QY_HARDWARE=1`)
- Property tests (Hypothesis) on UDM/XG roundtrip

**Tested on**:
- SGT live capture 208/208 roundtrip (Session 28, hardware)
- Summer capture 126/126 roundtrip (Session 26-27)
- DECAY self-parse byte-identical (Session 27)
- AMB01 + SGT_backup + STYLE2 reference captures (Session 32f, 3 patterns + XG)

**Hardware I/O orchestration**:
- `auto_capture_pipeline.py` — send style + capture playback + build Q7P in one shot
- `request_dump.py` — bulk dump with Init handshake (Session 22 fix)
- `decode_pattern_names.py` — decode AH=0x05 pattern directory (Session 28b)
- **`capture_complete.py`** — live capture of pattern + directory + system + XG Multi Part (Session 32i)

The metadata converter (`qy70_to_qy700.py`) also works for volume, pan, and chorus/reverb (voice writes disabled — caused prior bricking).

## Recommended Next Steps (by priority)

### Pipeline B (capture-based) — production-ready for 4-bar AND 6-bar
1. ~~**Software**: Build capture→quantize pipeline~~ — **DONE** (Session 21)
2. ~~**Hardware**: Fresh capture with drum output~~ — **DONE** (Session 22)
3. ~~**Hardware**: Get 5120B Q7P from QY700~~ — **DONE** (DECAY scaffold)
4. ~~**Software**: Integrate D0/E0 into 5120B Q7P template~~ — **DONE** (Session 21+)
5. ~~**Software**: Hardware-validated roundtrip~~ — **DONE** (Session 28)
6. ~~**Software**: Extend to 6-bar+ via 6144B scaffold~~ — **DONE** (Session 29)
7. **Hardware**: Load a generated Q7P on QY700 to confirm playback (risky — use safe_q7p_tester)

### Pipeline C (SysEx extraction) — production-ready (Session 32j)
1. ~~**Parser**: XG Multi Part all params~~ — **DONE** (17 params/part)
2. ~~**Parser**: XG System / Effects / Drum Setup~~ — **DONE**
3. ~~**Parser**: Pattern Name Directory (AH=0x05)~~ — **DONE** (raw encoding fix)
4. ~~**CLI**: 5 new commands unified (info/audit/bulk-summary/merge/xg inspect)~~ — **DONE**
5. ~~**Tools**: capture_complete.py + load_json_to_syx.py~~ — **DONE**
6. ~~**Documentation**: 3 wiki pages + README section~~ — **DONE**
7. **Next** — Extend voice signature DB with more pattern captures (now 23 entries, 3 patterns)

### Pipeline A (SysEx decode) — research block, long-term
8. **Research**: Dense encoding (rotation fails on 3 Summer events — "structurally impossible" Session 32e)
9. **Hardware**: Capture ground truth patterns with different time signatures (3/4, 6/8) for time-sig byte RE
10. **Hardware**: Voice-differential capture (same pattern, different voice) to triangulate voice index byte

## File Map

### Conversion (Pipeline A / B)
| File | Role |
|------|------|
| `qymanager/converters/qy70_to_qy700.py` | Metadata converter (tempo, pan, chorus/reverb) |
| `qymanager/formats/qy700/phrase_parser.py` | Q7P phrase reader (5120 D0/E0 + 3072 grid) |
| `qymanager/formats/qy700/decoder.py` | Q7P decoder (reads metadata + sections) |
| `midi_tools/event_decoder.py` | QY70 bitstream decoder (rotation model) |
| `midi_tools/quantizer.py` | Capture quantizer (raw MIDI → beat grid) |
| `midi_tools/capture_to_q7p.py` | Pipeline B orchestrator (SMF + Q7P + D0/E0) |
| `midi_tools/auto_capture_pipeline.py` | One-shot send+capture+build |
| `midi_tools/captured/*.mid` / `*.Q7P` | SGT/Summer/DECAY reference outputs |

### Extraction (Pipeline C, Session 32i/j)
| File | Role |
|------|------|
| `qymanager/analysis/syx_analyzer.py` | Enhanced — 7 AH families + XG Model 4C parser (System/Effects/Multi Part/Drum Setup) + 3-tier voice resolver |
| `qymanager/formats/qy70/encoder_dense.py` | Dense-factory encoder with per-event R lookup (SGT byte-exact) |
| `qymanager/formats/qy70/encoder_sparse.py` | Sparse encoder (R=9×(i+1) proven) |
| `qymanager/formats/qy70/xg_multi_part.py` | Multi Part Bulk request helper |
| `cli/commands/info.py` | Main info command (auto-detects multi-slot) |
| `cli/commands/audit.py` | Extraction completeness report |
| `cli/commands/merge.py` | Pattern+JSON → .syx merger |
| `cli/commands/bulk_summary.py` | Multi-slot inventory |
| `cli/commands/xg.py` | `xg inspect` added — parsed state view |
| `cli/display/tables.py` | Rich panels (System/DrumSetup/VoiceEdit/Extended XG) |
| `midi_tools/capture_complete.py` | **Live capture all-in-one** (29 dump requests/session) |
| `midi_tools/load_json_to_syx.py` | JSON capture → .syx (+merge-with) |
| `data/voice_signature_db.json` | 23 voice signatures (21 unambiguous, tier-2 resolver) |
| `data/captures_2026_04_23/` | Reference captures (SGT/AMB01/STYLE2) for tests |

### Test
| File | Role |
|------|------|
| `tests/test_voice_extraction_pipeline.py` | 22 integration tests: bulk-only, merge, DB, XG, CLI end-to-end |
| `tests/formats/test_qy70_encoders.py` | Dense + sparse encoder roundtrip |

### Documentation
| File | Role |
|------|------|
| `wiki/pattern-header-al7f.md` | 640B header map + encoding-per-AH + failed approaches |
| `wiki/voice-extraction-workflow.md` | 3 workflow detailed (A/B/C) |
| `wiki/quickstart-sysex-extraction.md` | Decision tree + one-liner recipes |
| `wiki/dense-encoding-spec.md` | Dense encoding structural spec |
| `wiki/session-32f-captures.md` | Reference captures documentation |
| `wiki/log.md` | Chronological session log (up to 32j) |

See [Q7P Format](q7p-format.md), [Event Fields](event-fields.md), [Open Questions](open-questions.md).
