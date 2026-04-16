# Conversion Roadmap

End-to-end status for QY70 → QY700 conversion.

## Pipeline Overview

> **Session 19 finding**: The SysEx bitstream decoder **FAILS on complex styles** (~0% accuracy against ground truth). Two conversion pipelines now exist: the original (broken for complex styles) and a new capture-based approach.

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

## What Works Today (Session 28)

**Pipeline B produces end-to-end output**:
- Standard MIDI File (.mid) — immediately playable and verifiable
- Q7P 5120B with correct metadata AND phrase data (hardware-roundtrip validated)
- D0/E0 phrase data for all tracks (drum + melody encoding)
- Quantized JSON for debugging/analysis
- Cross-pattern validator with phrase-stream invariants (0 warnings)
- Full test suite (26 tests passing, including hardware-capture regression)

**Tested on**:
- SGT live capture 208/208 roundtrip (Session 28, hardware)
- Summer capture 126/126 roundtrip (Session 26-27)
- DECAY self-parse byte-identical (Session 27)

**Hardware I/O orchestration**:
- `auto_capture_pipeline.py` — send style + capture playback + build Q7P in one shot
- `request_dump.py` — bulk dump with Init handshake (Session 22 fix)
- `decode_pattern_names.py` — decode AH=0x05 pattern directory (Session 28b)

The metadata converter (`qy70_to_qy700.py`) also works for volume, pan, and chorus/reverb (voice writes disabled — caused prior bricking).

## Recommended Next Steps (by priority)

### Pipeline B (capture-based) — production-ready for 4-bar AND 6-bar
1. ~~**Software**: Build capture→quantize pipeline~~ — **DONE** (Session 21)
2. ~~**Hardware**: Fresh capture with drum output~~ — **DONE** (Session 22)
3. ~~**Hardware**: Get 5120B Q7P from QY700~~ — **DONE** (DECAY scaffold)
4. ~~**Software**: Integrate D0/E0 into 5120B Q7P template~~ — **DONE** (Session 21+)
5. ~~**Software**: Hardware-validated roundtrip~~ — **DONE** (Session 28)
6. ~~**Software**: Extend to 6-bar+ via 6144B scaffold~~ — **DONE** (Session 29, SGT..Q7P scaffold)
7. **Hardware**: Load a generated Q7P on QY700 to confirm playback (risky — use safe_q7p_tester)

### Pipeline A (SysEx decode) — research block, long-term
8. **Research**: Dense encoding (rotation fails on factory styles)
9. **Hardware**: Capture ground truth patterns A/B/D/E/F (see [Open Questions](open-questions.md))

## File Map

| File | Role |
|------|------|
| `qymanager/converters/qy70_to_qy700.py` | Main converter (metadata only) |
| `qymanager/formats/qy700/phrase_parser.py` | Q7P phrase reader (5120 D0/E0 + 3072 grid) |
| `qymanager/formats/qy700/decoder.py` | Q7P decoder (reads metadata + sections) |
| `midi_tools/event_decoder.py` | QY70 bitstream decoder (rotation model) |
| `midi_tools/quantizer.py` | **NEW** — Capture quantizer (raw MIDI → beat grid) |
| `midi_tools/capture_to_q7p.py` | **NEW** — Pipeline B orchestrator (SMF + Q7P + D0/E0) |
| `midi_tools/q7p_sequence_analyzer.py` | Q7P sequence events analyzer |
| `midi_tools/capture_chord_test.py` | Chord transposition capture tool |
| `midi_tools/send_and_capture.py` | Combined send + capture workflow |
| `midi_tools/validate_sgt_capture.py` | Ground truth validation (Session 19) |
| `midi_tools/captured/sgt_full_capture.json` | SGT playback capture (2570 msgs, 6 channels) |
| `midi_tools/captured/sgt_converted.mid` | **NEW** — SGT as Standard MIDI File (4 bars) |
| `midi_tools/captured/sgt_6bar.mid` | **NEW** — SGT as SMF (6 bars, full section) |
| `midi_tools/captured/sgt_converted.Q7P` | **NEW** — SGT Q7P with metadata |

See [Q7P Format](q7p-format.md), [Event Fields](event-fields.md), [Open Questions](open-questions.md).
