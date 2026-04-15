# Conversion Roadmap

End-to-end status for QY70 → QY700 conversion.

## Pipeline Overview

```
QY70 .syx → [Decode Bitstream] → [Abstract Events] → [Encode Q7P] → QY700 .Q7P
```

| Stage | Status | Confidence |
|-------|--------|------------|
| Parse SysEx | Done | High |
| 7-bit decode | Done | High |
| Bitstream unpack | Done | High |
| Rotation decode (R=9×(i+1)) | Done (single-segment) | High |
| Chord event decode | F4 mask → notes | 82% |
| Bass event decode | Chaotic results | 25-31% |
| Drum event decode | R proven, fields decoded | 80% (drum) |
| General event decode | Same as chord? | 38% |
| Chord transposition | Templates, not absolute | Unknown |
| Q7P metadata write | Name, tempo, vol, pan | High |
| Q7P event write (3072) | Format partially mapped | 30% |
| Q7P event write (5120) | Format understood (D0/E0) | 0% (no template) |

## Blocking Issues

### 1. Chord Transposition (blocks ALL chord/melody conversion)

Bar headers store chord-RELATIVE templates. The QY70 applies real-time transposition based on user chord input. Without the transposition formula, decoded notes don't match playback.

**What's needed**: Multi-chord capture comparison (CM, Dm, G7) using `capture_chord_test.py`.

**Hardware config**: PATT OUT=9~16, ECHO BACK=Off, MIDI SYNC=External.

### 2. Q7P Event Writing (blocks output generation)

Two paths exist:

| Path | Format | Status | Blocker |
|------|--------|--------|---------|
| **3072-byte** | Sequence events (0x83/0x84/0x88 grid) | Structure mapped, semantics partial | Command semantics unknown, need more Q7P samples |
| **5120-byte** | D0/E0 inline phrases | Well understood | No template file, metadata offsets differ by +0x880 |

**Recommendation**: Get a 5120-byte Q7P from QY700 hardware. Create a pattern with known notes → save as Q7P → use as template.

### 3. Bass Encoding (blocks bass track conversion)

Both 2BE3 and 29CB encodings produce chaotic results (25-31% confidence). The rotation model works but F3-F5 field interpretation is wrong for bass.

**What's needed**: Ground truth capture — program a bass pattern with known notes on QY70, capture bulk dump, compare with decoded output.

### 4. Multi-segment Rotation (minor, ~5% events affected)

Control events at odd positions disrupt the cumulative index in multi-segment tracks. Model G cascade (std→skip-ctrl→R=47) achieves 94-96% but ~3 events per track still fail.

## What Works Today

The current converter (`qy70_to_qy700.py`) safely produces:
- Valid 3072-byte Q7P files
- Correct name, tempo, volume, pan
- Template musical data (USER TMPL drum pattern)

Musical event conversion is NOT implemented — output always has the template's drum pattern regardless of input.

## Recommended Next Steps (by priority)

1. **Hardware**: Set QY70 to PATT OUT=9~16, ECHO BACK=Off, run `capture_chord_test.py` with CM/Dm/G7
2. **Hardware**: On QY700, create pattern with known notes, save as Q7P, hex-analyze
3. **Software**: Implement transposition formula from step 1 data
4. **Software**: If 5120-byte Q7P obtained in step 2, implement D0/E0 event writer
5. **Software**: If no 5120, decode 3072-byte command semantics from step 2 patterns
6. **Software**: Integrate event decoder + writer into converter pipeline

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

See [Q7P Format](q7p-format.md), [Event Fields](event-fields.md), [Open Questions](open-questions.md).
