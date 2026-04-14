# Decoder Status

Current state of [QY70 bitstream](bitstream.md) decoding as of Session 12 (2026-04-14).

## Per-Encoding Confidence

| Encoding | Preamble | Tracks | Confidence | Beat Accuracy | Key Findings |
|----------|----------|--------|------------|---------------|--------------|
| chord | `1FA3` | CHD2, PHR1, PHR2 | **82%** | **90%** | [R=9](bitstream.md), [beat counter](event-fields.md#f3-beat-counter), [chord mask](event-fields.md#f4-chord-tone-mask), [9E delimiters](bar-structure.md#delimiters) |
| general | `29CB` | RHY2, CHD1, PAD | **38%** | 42-100% | Same R=9 rotation works, beat counter confirmed |
| bass_slot | `2BE3` | BASS | **38%** | 100% | DC delimiters, can switch to general (29CB) |
| drum_primary | `2543` | RHY1 | **61%** | 51% | [9E sub-bars](bar-structure.md#delimiters), msgs 0-4 identical per section |

## What Works

- **Barrel rotation R=9**: confirmed for ALL encoding types
- **Beat counter (F3 lo4)**: 90%+ accuracy for chord and bass tracks
- **Bar delimiters**: DC (bar) and 9E (sub-bar chord change) both recognized
- **F4 chord mask**: 5-bit mask selects from 5 header notes (pattern consistent)
- **Track classification**: preamble-based encoding detection 100% reliable

## What Doesn't Work Yet

- **Bar header chord notes**: 9-bit fields give valid MIDI notes for SGT but >127 values for other patterns. The header encoding is not fully understood — possibly non-linear or uses extended flags for bit 8.
- **F5 timing**: approximate (+16/beat hypothesis) but actual resolution appears to be 8th-note. Values are NOT monotonically increasing within a bar.
- **F4 param4**: 4-bit parameter not decoded (likely velocity/gate/articulation).
- **F0-F2 shift register**: understood conceptually (carries history) but not exploitable for decoding.
- **Drum event structure**: `28 0F` marker in RHY1, only msg 5 differs between sections.

## Improvement History

| Session | Change | Impact |
|---------|--------|--------|
| 6 | R=9 rotation discovered | Core breakthrough |
| 7 | Shift register F0-F2 identified | Structural understanding |
| 8 | F3 beat counter decoded | +40% beat accuracy |
| 10 | Preamble-based classification | 100% track typing |
| 12 | lo4=0 → beat 0, 9E delimiter | 48%→90% beat accuracy, 68%→82% confidence |

## Blocking Issue

Without a .syx file with **known musical content**, bar header decoding cannot be validated. The captured `ground_truth_style.syx` has real data (133 BPM, 7 tracks) but unknown chord progression.

**Next step**: program a simple pattern on the QY70 (e.g., C major chord on CHD2, 4 bars) and capture it. See [Open Questions](open-questions.md).
