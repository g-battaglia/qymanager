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
QY70 Hardware → [MIDI Playback] → [Capture Notes] → [Abstract Events] → [Encode Q7P] → QY700 .Q7P
```

| Stage | Status | Confidence |
|-------|--------|------------|
| Send .syx to QY70 | Done (`send_style.py`) | High |
| Start playback (MIDI Start+Clock) | Done (`send_and_capture.py`) | High |
| Capture MIDI notes | Done (`capture_playback.py`) | High |
| Parse captured events | Done (JSON format) | High |
| Quantize to beats/bars | Not started | Medium |
| Map to Q7P events | Not started | 30% |
| Q7P metadata write | Done | High |
| Q7P event write (3072) | Format partially mapped | 30% |

**Advantages**: bypasses all unsolved decoding problems (rotation model, chord transposition, groove templates). Captures the EXACT notes the QY70 produces.

**Requirements**: QY70 hardware must be connected. PATT OUT=9~16, ECHO BACK=Off, MIDI SYNC=External.

**Limitation**: drums don't output via PATT OUT in Pattern mode. May need Style mode for drum capture.

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

### 3. Capture Quantization (blocks Pipeline B)

Captured MIDI notes have real-time timestamps. Need to quantize to beat/bar grid and map to Q7P event format. Also need drum capture (drums don't output in Pattern mode).

### 4. Chord Transposition (blocks Pipeline A chord tracks)

Bar headers store chord-RELATIVE templates. Irrelevant for Pipeline B (capture already has absolute notes).

### 5. Bass Encoding (blocks Pipeline A bass track)

Both 2BE3 and 29CB produce chaotic results. Irrelevant for Pipeline B.

## What Works Today

The current converter (`qy70_to_qy700.py`) safely produces:
- Valid 3072-byte Q7P files
- Correct name, tempo, volume, pan
- Template musical data (USER TMPL drum pattern)

Musical event conversion is NOT implemented — output always has the template's drum pattern regardless of input.

## Recommended Next Steps (by priority)

### Pipeline B (capture-based) — highest priority
1. **Software**: Build capture→quantize pipeline (MIDI timestamps → beat/bar grid)
2. **Hardware**: Capture full SGT style via playback (all tracks, all sections)
3. **Software**: Build quantized-events → Q7P writer
4. **Hardware**: On QY700, create pattern with known notes, save as Q7P, hex-analyze (needed for Q7P format)
5. **Hardware**: Find way to capture drums (Style mode? Different PATT OUT setting?)

### Pipeline A (SysEx decode) — lower priority, research only
6. **Research**: Investigate why complex styles use different encoding than user patterns
7. **Hardware**: Run `capture_chord_test.py` with CM/Dm/G7 to study chord transposition (useful for understanding QY70 internals even if not needed for Pipeline B)

## File Map

| File | Role |
|------|------|
| `qymanager/converters/qy70_to_qy700.py` | Main converter (metadata only) |
| `qymanager/formats/qy700/phrase_parser.py` | Q7P phrase reader (5120 D0/E0 + 3072 grid) |
| `qymanager/formats/qy700/decoder.py` | Q7P decoder (reads metadata + sections) |
| `midi_tools/event_decoder.py` | QY70 bitstream decoder (rotation model) |
| `midi_tools/q7p_sequence_analyzer.py` | Q7P sequence events analyzer |
| `midi_tools/capture_chord_test.py` | Chord transposition capture tool |
| `midi_tools/send_and_capture.py` | Combined send + capture workflow |
| `midi_tools/validate_sgt_capture.py` | Ground truth validation (Session 19) |
| `midi_tools/captured/sgt_full_capture.json` | SGT playback capture (2570 msgs, 6 channels) |

See [Q7P Format](q7p-format.md), [Event Fields](event-fields.md), [Open Questions](open-questions.md).
