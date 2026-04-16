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

### Pipeline B: Capture-Based (NEW, Session 19) — RECOMMENDED

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
| **D0/E0 phrase encoding** | **Done** (`capture_to_q7p.py`) | **Medium** |
| Q7P metadata write | Done | High |
| Q7P event write (5120) | Needs 5120B template | 40% |

**Session 22 progress**: Full end-to-end pipeline working. Fresh capture: 851 note_on (incl. drums!), 322 notes quantized, 6 tracks, 6 bars. Produces valid SMF (10.1s), Q7P metadata, and D0/E0 phrase data (1746 bytes). Drum output via PATT OUT confirmed working. Delta encoding A0-A7 is hypothesized (step×128+value) — needs hardware validation.

**Advantages**: bypasses all unsolved decoding problems (rotation model, chord transposition, groove templates). Captures the EXACT notes the QY70 produces.

**Requirements**: QY70 hardware must be connected. PATT OUT=9~16, ECHO BACK=Off, MIDI SYNC=External.

~~**Limitation**: drums don't output via PATT OUT in Pattern mode.~~ **Session 22: DISPROVEN** — drums DO output via PATT OUT CH 9~16. The Session 17 finding was caused by MIDI clock echo masking real notes (`timing=False` bug). Fresh capture: RHY1=455 note_on, RHY2=114 note_on.

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

## What Works Today (Session 21)

**Pipeline B produces end-to-end output**:
- Standard MIDI File (.mid) — immediately playable and verifiable
- Q7P with correct metadata (name, tempo, time sig)
- D0/E0 phrase data for all tracks (drum + melody encoding)
- Quantized JSON for debugging/analysis

**Tested on SGT capture**: 374 notes across 6 tracks, 4-bar loop detected (or 6 bars with manual override). SMF duration matches expected time (9.5s at 151 BPM, 6 bars).

The metadata converter (`qy70_to_qy700.py`) also works for volume, pan, and chorus/reverb.

## Recommended Next Steps (by priority)

### Pipeline B (capture-based) — highest priority
1. ~~**Software**: Build capture→quantize pipeline~~ — **DONE** (Session 21)
2. ~~**Hardware**: Fresh capture with drum output~~ — **DONE** (Session 22, drums work via PATT OUT)
3. **Hardware**: Get a 5120-byte Q7P from QY700 (create pattern → save → use as template)
4. **Software**: Integrate D0/E0 phrase data into 5120-byte Q7P template
5. **Hardware**: Validate D0/E0 delta encoding (A0-A7) by loading generated Q7P on QY700

### Pipeline A (SysEx decode) — lower priority, research only
6. **Research**: Investigate why complex styles use different encoding than user patterns
7. **Hardware**: Run `capture_chord_test.py` with CM/Dm/G7 to study chord transposition

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
