# 2543 Drum/Pattern Encoding

The `2543` preamble encoding is used for [RHY1](track-structure.md) (slot 0) in Style mode, and for **ALL tracks** in Pattern mode. Unlike the [chord encoding](event-fields.md) (`1FA3`), it uses absolute MIDI events rather than chord-relative masks.

## Key Differences from Chord Encoding (1FA3)

| Property | 1FA3 (chord) | 2543 (drum/pattern) |
|----------|-------------|---------------------|
| Rotation | **Cumulative** (R × event_index) | **Constant** (same R for every event) |
| F0 | Shift register (history) | Note number + flags |
| F1-F4 | Shift register + beat/chord | Position encoding (shared by simultaneous events) |
| F5 | Timing/gate | Gate time in ticks |
| Bar header | 5 chord notes + 6 params | Different structure (not chord notes) |

Confidence: **High** (PROVEN on known_pattern.syx 7/7 perfect match)

## Rotation — PROVEN: Cumulative R=9×(i+1)

### Definitive proof via known_pattern.syx (Session 14)

The rotation model `R = (9 × (event_index + 1)) % 56` is **definitively proven** with a ground truth test: 7 events in `known_pattern.syx` with exactly known note, velocity, tick, and gate values — **ALL 7 match perfectly**:

```
GT[0]: Kick1  n=36 v=127 t=240  g=412 → R=9  FULL MATCH
GT[1]: Crash1 n=49 v=127 t=240  g=74  → R=18 FULL MATCH
GT[2]: HHped  n=44 v=119 t=240  g=30  → R=27 FULL MATCH
GT[3]: HHped  n=44 v=95  t=720  g=30  → R=36 FULL MATCH
GT[4]: Snare1 n=38 v=127 t=960  g=200 → R=45 FULL MATCH
GT[5]: HHped  n=44 v=95  t=960  g=30  → R=54 FULL MATCH
GT[6]: HHped  n=44 v=95  t=1440 g=30  → R=7  FULL MATCH (9*7=63, 63%56=7)
```

This is the definitive test — no other rotation model achieves 7/7 on all four fields.

```python
def derotate_2543(raw_bytes: bytes, event_index: int) -> int:
    val = int.from_bytes(raw_bytes, "big")
    r = (9 * (event_index + 1)) % 56
    return ((val >> r) | (val << (56 - r))) & ((1 << 56) - 1)
```

### Event index is PER-SEGMENT (resets at DC delimiter)

The event index **resets to 0** at each DC delimiter (bar boundary). Global indexing across segments does NOT work:

| Index mode | Expected note hits (USER-RHY1) |
|------------|-------------------------------|
| **per_segment** | **6/36 (best)** |
| global | 1/36 |
| global_plus_headers | 1/36 |

Confirmed on known_pattern.syx (single segment) and cross-validated on USER-RHY1 multi-segment data.

### Historical context

The original "proof" of constant R=9 (Session 12c) was based on identical events at e0 position, where constant R=9 and cumulative R=9×(0+1)=9 give the same result — inconclusive. The mixed model (cumulative + R=9 fallback, Session 12e-12f) was a stepping stone. Session 14's known_pattern.syx test is the definitive proof.

### Multi-segment control event interference (OPEN)

In multi-segment tracks, control events appear at odd positions within segments. When the cumulative index includes these control events, subsequent note events decode incorrectly. Position-specific R values `{e0:9, e1:22, e2:12, e3:53}` give 100% match on USER-RHY1 bars 3-4, but:

- No linear formula `R = a*i + b (mod 56)` fits these values
- SGT-RHY1 requires completely different R values per position
- The R values appear to be **style-specific** or depend on something not yet decoded

**Solution: Model G cascade** (Session 14). When a control event is detected at standard cumulative R, subsequent note events may need an alternative R computed from a "note-only" index (skipping ctrl events in the count):

```python
# Model G: std → skip-ctrl → R=47 cascade
r_std = (9 * (event_index + 1)) % 56     # all events count
r_skip = (9 * (note_index + 1)) % 56     # only note events count
# Try r_std first; if invalid note AND not ctrl, try r_skip; lastly R=47
```

Results: **96% USER-RHY1, 94% SGT-RHY1** (vs 84%/85% for std-only). After a ctrl event at e9 in USER seg6, the skip model correctly decodes Crash1(49) and Ride1(51) where the standard model gives garbage (n=4, n=1).

## Field Map

After cumulative R=9×(i+1) de-rotation, the 56 bits decompose as 6 × 9-bit fields + 2 remainder bits (same layout as [bitstream.md](bitstream.md)):

| Field | Bits | Content | Confidence |
|-------|------|---------|------------|
| F0 | 55-47 | Note number (lo7) + flags (bit8, bit7) | **High** |
| F1 | 46-38 | Position encoding (part 1) | Medium |
| F2 | 37-29 | Position encoding (part 2) | Medium |
| F3 | 28-20 | Position encoding (part 3) | Medium |
| F4 | 19-11 | Position encoding (part 4) | Medium |
| F5 | 10-2 | Gate time (ticks, ~480/beat) | **High** |
| R | 1-0 | Remainder (correlates with note type) | Low |

### F0: Note Number

- `lo7` (bits 6-0) = MIDI note number
- `bit7` (bit 7) = flag (possibly velocity level bit 0)
- `bit8` (bit 8) = flag (possibly velocity level bit 1)

Decomposition: `[bit8: 1][bit7: 1][note: 7 bits]`

Known drum mappings (confirmed from repeated events):

| F0 | bit8 | bit7 | lo7 | GM Drum |
|----|------|------|-----|---------|
| 36 | 0 | 0 | 36 | Kick1 |
| 44 | 0 | 0 | 44 | HH Pedal |
| 46 | 0 | 0 | 46 | HH Open |
| 48 | 0 | 0 | 48 | Hi-Mid Tom |
| 51 | 0 | 0 | 51 | Ride Cymbal 1 |
| 57 | 0 | 0 | 57 | Crash 2 |
| 35 | 0 | 0 | 35 | Kick2 |
| 80 | 0 | 0 | 80 | Mute Triangle |
| 336 | 1 | 0 | 80 | Mute Triangle (flag) |
| 465 | 1 | 1 | 81 | Open Triangle (flag) |

### F1-F4: Position Encoding

Events at the **same musical position** within a bar share identical F1-F4 values.

**Beat number** = F1 top 2 bits (`F1 >> 7`), range 0-3. Confidence: **High**.

**Clock within beat** = lower bits of F1 + top bits of F2. Best formula found:
```python
pos_clock = ((F1 & 0x7F) << 2) | (F2 >> 7)   # 9-bit, 0-511
pos_ticks = beat * 480 + pos_clock
```

This gives 59% monotonicity within segments (vs 51% for 10-bit formula). The most common position (tick 240, beat 0 clock 240) contains Kick1, HHpedal, HHopen — all "beat 1" instruments.

**Position calibration**: tick 240 appears as the primary beat position in 6/10 segments, suggesting an offset where clock 240 ≈ the downbeat.

**F3-F4 role**: Not fully decoded. They are shared by simultaneous events (same as F1-F2), so they encode position-related data. Possibly encode sub-beat timing parameters or groove template data.

### F5: Gate Time

F5 values correlate strongly with expected physical gate durations. At 155 BPM (SGT style), 1 tick ≈ 0.81ms:

| Drum | F5 | Duration | Physical |
|------|----|----------|----------|
| Kick1 | 412 | 332ms | OK (long ring) |
| HH Pedal | 30-43 | 24-35ms | OK (very short) |
| HH Open | 53 | 43ms | OK (short, > closed) |
| Ride1 | 13-43 | 10-35ms | OK (bell tap) |
| Crash1 | 74 | 60ms | OK |
| Crash2 | 116 | 94ms | OK |

Range: 9-432 ticks (7ms to 349ms at 155 BPM).

### Remainder (2 bits) — Part of Velocity

The remainder is the **low 2 bits of the 4-bit velocity code**:
```
vel_code = [F0_bit8 : F0_bit7 : rem_bit1 : rem_bit0]
```

See [Velocity Encoding](#velocity-encoding--solved) for the full mapping.

## Bar Headers

Headers start with byte `0x1A` for standard bars (9-bit field 0 = 53). The first bar may start with `0xDE` or `0x98` (initialization bar).

Unlike [chord bar headers](bar-structure.md), the 11 9-bit fields do NOT encode chord notes. Their structure is not yet decoded. Multiple bars often share identical headers, suggesting the header encodes bar-level parameters (time signature? section type?).

## Velocity Encoding — SOLVED

Velocity is encoded as a **4-bit inverted code** combining F0 flags and the remainder bits:

```
vel_code = [F0_bit8 : F0_bit7 : rem_bit1 : rem_bit0]
MIDI_velocity ≈ 127 - (vel_code × 8)
```

| vel_code | MIDI vel | Dynamic | Example instruments |
|----------|----------|---------|-------------------|
| 0 | 127 | fff | Kick, Crash, Ride |
| 1 | 119 | ff+ | HH open, HH pedal, n109 |
| 2 | 111 | ff | MuTriang |
| 3 | 103 | f+ | HiMidTom, HiBongo, LoConga |
| 4 | 95 | f | HHpedal (soft), HiBongo (soft) |
| 8 | 63 | mp | MuTriang (soft), Crash1 |
| 12 | 31 | pp | OpTriang |
| 13 | 23 | pp- | OpTriang, HiMidTom (ghost) |
| 15 | 7 | pppp | Cabasa, OpTriang (ghost) |

Confidence: **High** — same note (e.g., MuTriang note 80) appears at multiple velocity levels (v2=111, v8=63). OpTriang shows 4 distinct velocity levels (v12, v13, v14, v15) consistent with a decrescendo pattern.

## Event Types

The event stream contains multiple event types, not just note events. Classification is based on F0 field value at R=9:

| Type | F0 at R=9 | Fraction | Description |
|------|-----------|----------|-------------|
| **Note** | lo7 ∈ [13, 87] | 85% (52/61) | Normal drum/note events |
| **Control** | 0x078 (note=120) | 15% (9/61) | Structural markers, cross-track |
| **Null** | 0x000 | BASS only | Padding/end markers |

### Control Events (F0=0x078)

Control events are identified by F0=0x078 (note=120, flags=00) after R=9 derotation. They have these properties:

- **Cross-track identical bytes**: pattern `280f8d83b0d878` appears in BOTH RHY1 and PAD tracks at multiple locations
- **Pattern `3486f2e3e24078`** also shared between RHY1 and PAD
- **Remainder = 0** for 14/17 control events across all tracks
- **Not encoding-specific**: appear in 2543 (15%), 29CB (11%), and 2BE3 (15%)
- **Absent from 1FA3**: chord tracks have 0% control events

#### Sub-sequence terminators (Session 12f)

Control events act as **structural terminators within segments**:
- **11/16 (69%)** are the LAST event in their segment
- **ALL 16** appear at **odd positions** (1, 3, 5, 7, 9, 11)
- In segments with multiple controls, the pattern is: `[N notes] [ctrl] [N notes] [ctrl_final]`
- Example: RHY1/seg6 (10 events) = 3 notes → ctrl → 3 notes → ctrl → 1 note → ctrl

#### F0 value distribution

F0 = 0x1E0 (480) for 14/16 events; 0x1E1 and 0x1E3 are rare variants.
In 9-bit decomposition: `bit8=1, bit7=1, lo7=96` — not a valid drum note.

#### F5 groups (possible terminator type)

| F5 | Binary | Count | Tracks | Role (hypothesis) |
|----|--------|-------|--------|-------------------|
| 0x120 | 100100000 | 5 | RHY1, PAD | Intermediate terminator |
| 0x06C | 001101100 | 5 | RHY1, PAD | Final terminator (often last in segment) |
| 0x036 | 000110110 | 3 | BASS only | BASS-specific final terminator |
| 0x024 | 000100100 | 1 | RHY1 | Rare variant |
| 0x02C | 000101100 | 1 | RHY1 | Rare variant |
| 0x180 | 110000000 | 1 | PAD | Rare variant |

#### BASS control events

BASS has 3 control events, ALL at position e3 (last), ALL with F5=0x036 and rem=2. Only F4 varies between them (0x06F, 0x07C, 0x076) — possibly encoding segment-specific metadata.

### True Accuracy (note events only)

| Model | All events | Note events only | Ground truth |
|-------|-----------|-----------------|--------------|
| Constant R=9 | 40/61 (66%) | 38/52 (73%) | 1/7 (14%) |
| Cumulative R=9×(i+1) | 47/61 (77%) | 44/52 (85%) | **7/7 (100%)** |
| Mixed (cum+R=9 fallback) | 52/61 (85%) | 49/52 (94%) | — |

Confidence: **Proven** — 7/7 perfect match on known_pattern.syx ground truth (note+velocity+tick+gate all exact). The 3 remaining failures in SGT-RHY1 are likely due to control event interference in multi-segment cumulative index computation.

## Usage Contexts

| Context | Track(s) | Description |
|---------|----------|-------------|
| Style mode | RHY1 (slot 0) only | Primary drum track, 6 messages (768B per section) |
| Pattern mode | ALL tracks (D1, D2, PC, BA, C1-C4) | ALL pattern data uses 2543 regardless of voice |

In Pattern mode, chord tracks (C1-C4) also use 2543 encoding, storing absolute note events rather than chord-relative masks.

## Segment Alignment

Segments are NOT always aligned to 7-byte events: `(segment_length - 13) % 7 ≠ 0` for ~50% of segments. Extra bytes (1-3) appear between the last event and the delimiter:

| Segment | Length | Trailing bytes | Content |
|---------|--------|---------------|---------|
| 2 | 57 | 2 | `d878` |
| 5 | 51 | 3 | `4ce63c` |
| 10 | 85 | 2 | `d878` |
| 11 | 85 | 2 | `1cc0` |

Key findings (Session 12f):
- **ALL control events end with byte 0x78** — this is the hallmark of control events
- Trail `d878` = last 2 bytes of most common control event `280f8d83b0d878`
- Trail `78` (1B, BASS) = last byte of any control event
- CHD2/PHR1 share **identical** trails for matching segments (s0: `ff`, s2: `5f60`)
- BASS s5 = `0000` — simple zero padding
- Trailing bytes do NOT concatenate meaningfully with the next segment header
- Most common length: 2 bytes (11/18 segments), followed by 1B (3), 3B (3), 5B (1)

Hypothesis: trailing bytes are segment-level metadata (possibly footer/checksum), not fragmented events. The `0x78` correlation may indicate that the trailing bytes are generated by the same encoding process as control events.

## XG Drum Note Range

The XG Standard Kit maps notes **13-87** only:
- GM range: 35-81 (Kick2 to OpTriang)
- XG extensions: 82=Shaker, 83=JnglBell, 84=BellTree, 85=Castanets, 86=MuSurdo, 87=OpSurdo
- Notes >87 are NOT valid drum sounds in any QY70 kit

Remaining invalid events are primarily [control events](#event-types) (F0=0x078 at R=9). Only 3/52 note events (~6%) remain unexplained after filtering control events.

## Analysis Scripts

- `midi_tools/analyze_2543.py` — Field distribution and cross-correlation analysis
- `midi_tools/analyze_2543_deep.py` — Joint rotation optimization, alternative field widths
- `midi_tools/analyze_2543_compare_r.py` — Side-by-side comparison of rotation values
- `midi_tools/analyze_2543_rotation_model.py` — Constant vs cumulative rotation comparison
- `midi_tools/analyze_2543_anomalies.py` — Analysis of out-of-range note events
- `midi_tools/analyze_2543_alignment.py` — Segment alignment and padding detection
- `midi_tools/analyze_2543_r_sweep_cumulative.py` — R_base sweep for cumulative model
- `midi_tools/analyze_2543_mixed_rotation.py` — Mixed model (cumulative + constant fallback)
- `midi_tools/analyze_2543_trailing_bytes.py` — Trailing byte analysis across all tracks
- `midi_tools/analyze_2543_6byte_header.py` — 6-byte header hypothesis (REJECTED)
- `midi_tools/analyze_2543_continuous_stream.py` — Continuous stream and delimiter alignment
- `midi_tools/analyze_2543_failing_events.py` — Deep analysis of failing note events
- `midi_tools/analyze_cross_encoding_failures.py` — Cross-encoding failure comparison
- `midi_tools/analyze_event_types.py` — Event type classification (Note/Control/Null)
- `midi_tools/analyze_known_pattern.py` — **DEFINITIVE**: brute-force R per event vs ground truth (7/7 proof)
- `midi_tools/analyze_rhy1_global_index.py` — Global vs per-segment index comparison
- `midi_tools/analyze_rhy1_multinote.py` — Cross-bar consistency, position-specific R discovery
- `midi_tools/analyze_rhy1_structure.py` — Raw hex dump, delimiter analysis, R sweep
- `midi_tools/analyze_rhy1_r18.py` — USER vs SGT RHY1 deep comparison
- `midi_tools/analyze_rhy1_position_r.py` — Position-dependent R model, linear formula search
- `midi_tools/analyze_sgt_rhy1_crossbar.py` — SGT cross-bar analysis (different R per style)
- `midi_tools/validate_rhy1_decoder.py` — RHY1 decoder vs playback capture validation

## Test Data

- `ground_truth_style.syx`: RHY1 Section 0, 10 segments, 61 events
- `qy70_dump_20260414_114506.syx`: Pattern mode C1 track, 2 segments, 10 events

See also: [Bitstream](bitstream.md), [Event Fields](event-fields.md), [Decoder Status](decoder-status.md), [Open Questions](open-questions.md)
