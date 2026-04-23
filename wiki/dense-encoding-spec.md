# Dense Encoding Spec — Working Document

> Work-in-progress spec derived from differential analysis of Summer GT + factory styles.
> Target: bit-exact encoding/decoding of dense patterns (factory styles + complex user patterns).

## Current knowledge (Session 32+)

### Confirmed: Beat-template bytes invariant (MAIN bars)

Per-beat, specific byte positions are **invariant across MAIN bars** (excluding FILL bar 3) in Summer RHY1:

| Beat | Invariant positions | Hex values | Interpretation |
|------|---------------------|------------|----------------|
| 1 | B2, B3 | `97 06` | Beat 1 groove template (strikes K+H+H @ 0,0,1) |
| 2 | B1, B2 | `ae 8d` | Beat 2 groove template (strikes S+H+H @ 0,0,1) |
| 3 | B0, B4, B5, B6 | `8c __ __ __ 05 61 50` | Beat 3 template (strikes H+K+H @ 0,1,1) — **4 bytes fixed** |
| 4 | — | (none) | Beat 4 variable (bar 4 has 4th strike, outlier) |

### Bit-level invariants (MAIN bars, excl bar 3)

| Beat | Invariant bits | Mask |
|------|----------------|------|
| 1 | 48/56 | 0xfd9fffff7f737f |
| 2 | 39/56 | 0xbffffffc836370 |
| 3 | 49/56 | 0xffde9fa7ffffff |
| 4 | 25/56 | 0xbcfe88f4300330 |

Beat 3 has **49/56 bits constant** → only 7 bits variable across bars 1,2,4,5. These 7 bits must encode the bar-to-bar variation (velocity humanization + possibly bar_index).

### Confirmed: Bar 3 is FILL / MAIN_B

Bar 3 shows byte-level divergence from bars 1,2,4,5 in ALL beat positions. Consistent with QY70 "Fill" section or MAIN B variant.

### Confirmed: Alternating bar types A/B

Pattern structure = `[A B FILL A' B']` where:
- Bars 1, 4 share encoding patterns (TYPE A) — downbeat emphasis
- Bars 2, 5 share encoding patterns (TYPE B) — beat-2 emphasis
- Bar 3 is FILL

Example (beat 1 event bytes 0-1):
- Bar 1: `1d 34` (TYPE A)
- Bar 4: `1d 14` (TYPE A — byte 1 varies)
- Bar 2: `1f 74` (TYPE B)
- Bar 5: `1f 34` (TYPE B — byte 1 varies)

Byte 0 bit 1 = 0 (TYPE A) or 1 (TYPE B).

### OPEN: Bits that vary between "identical" strikes

Bar 1 and Bar 5 beat 1 have **identical captured strikes** (K36v127+H42v122@0+H42v116@1) but bytes differ:
- Bar 1: `1d 34 97 06 c0 62 aa`
- Bar 5: `1f 34 97 06 40 ee 2a`

6 bits flip: B0b1, B4b7, B5b2, B5b3, B5b7, B6b7.

Possible explanations:
1. **Micro-timing**: MIDI capture quantized to 8th-notes lost sub-tick offsets encoded in the bitstream
2. **Bar index**: event stores which bar within the 5-bar pattern it belongs to
3. **Groove humanization seed**: QY70 applies per-bar vel variation from seed
4. **Section tag**: bars belong to logical section (A vs B vs A' vs B')

### Summer 4-byte period for beat 3

For beat 3 MAIN bars, only middle 3 bytes (B1, B2, B3) vary:

| Bar | B1 B2 B3 | Strikes (GT) |
|-----|----------|--------------|
| 1 | `a5 27 85` | v118, v124, v112 |
| 2 | `a4 67 dd` | v121, v126, v116 |
| 4 | `a4 47 cd` | v122, v121, v116 |
| 5 | `84 67 d5` | v118, v124, v112 |

Bars 1 and 5 **identical GT strikes** but 3-byte diff = 24 bits. Most of those 24 bits must be "bar index" or micro-timing.

### Hypothesis: Event = [groove_template_ID, bar_index_or_micro]

Based on 49/56 bits constant in beat 3 and identical-strike divergence:
- **~49 bits**: groove_template_ID (determines strike pattern, notes, approximate velocity)
- **~7 bits**: bar_index or micro-timing (varies per bar within pattern)

This must be tested with controlled probes. The "groove template" might be a lookup into ROM, or a hash of musical params (chord, section, beat).

## SGT 664B shared codebook analysis (Session 32)

**Confirmed byte-exact**: all 6 SGT sections share bytes 0-691 (divergence at byte 692).
- Bytes 0-23: track header (24B)
- Bytes 24-27: preamble `25 43 60 00`
- Bytes 28-691: **664B shared content** (purpose UNRESOLVED)
- Bytes 692-767: 76B section-specific

**Autocorrelation on 664B codebook** (Session 32):
- Period **42** dominates (79 matches, 12.70%) — consistent with SGT 42B super-cycle
- Period 28 secondary (37 matches)
- Period 14 (34 matches)
- 2-3 byte repeating blocks = 40% coverage (likely structural repeats)

**Section trailing analysis (76B per section)**:
- Sec0 (MAIN A): structured musical events
- Sec1 (MAIN B): contains repeating `71 78 be 9f 8f c7 e3` pattern (7B × 4 repeats = drum fill/roll)
- Sec2/Sec3: mostly empty markers `bf df ef f7 fb fd fe` = unprogrammed sections
- Sec4/Sec5: structured data (ENDING variants)

**Interpretation**: the 664B codebook contains **the full MAIN A drum pattern** (dense-encoded). Other sections REFERENCE this codebook and override via their 76B suffix.

## Summer vs SGT encoding divergence (Session 32)

**Summer templates do NOT match SGT bitstream** — tested via byte-level pattern scan.

Summer (dense-user pattern) has 4 unique strike templates across 20 events:
| Signature | Count | Invariant bits | Fingerprint |
|-----------|-------|----------------|-------------|
| [n36@0, n42@0, n42@1] | 5 | 30/56 | 0x1d108400006220 |
| [n36@1, n42@0, n42@1] | 5 | 34/56 | 0x8c840784010000 |
| [n38@0, n42@0, n42@1] | 9 | 11/56 | 0x00068080000030 |
| [n38@0, n38@1, n42@0, n42@1] | 1 | 56/56 | 0x0a4eed81c4ccf6 |

**SGT scan results**: only the LOOSE template (11 invariant bits) matches SGT at offset 440 — but this is likely random (probability ~1 in 2048 per window × 4600 windows = ~2 expected by chance).

**Tight templates (30/34 invariant bits)**: 0 matches in SGT. Probability of random match at 30 bits = 1 in 10^9 × 4600 windows = 0.

**Conclusion**: Summer (dense-user) and SGT (dense-factory) use **different encoding schemes**, despite both using `2543` preamble and being "dense" by note-per-bar criterion.

## Three distinct encoding regimes (Session 32 consolidated)

| Regime | Example | Events/bar | Zero bytes | Encoder status |
|--------|---------|------------|------------|----------------|
| **Sparse** | known_pattern.syx | 7 (1 per note) | ~33% | **SOLVED**: R=9×(i+1), 7/7 proof |
| **Dense-user** | Summer (ground_truth_style) | 4 (lane per instrument) | ~0% | **Partially mapped**: template library built (4 entries) |
| **Dense-factory** | SGT, factory styles | ~6 per super-cycle | ~0-2% | **BLOCKED**: no ground truth mapping per event |

## Beat 3 variable bits analysis (Session 32)

For Summer beat 3 events across MAIN bars (1,2,4,5), 7 bits vary. Extracted values:
| Bar | Variable bits (7) | Strikes vels |
|-----|-------------------|--------------|
| 1 | 1101000 (104) | [118, 124, 112] |
| 2 | 1011111 (95) | [121, 126, 116] |
| 4 | 1010101 (85) | [122, 121, 116] |
| 5 | 0011110 (30) | [118, 124, 112] |

**Bars 1 and 5 have IDENTICAL GT strikes but different var values (104 vs 30)**.

Interpretation: those 7 bits do NOT encode bar index directly. Hypotheses:
- Micro-timing offset (not captured in GT 8th-note quantization)
- Internal groove humanization seed
- Per-strike velocity fine-tuning beyond vel_code granularity

## TYPE-A/B pattern encoding (Session 32)

Summer bars form alternating pairs:
- Bars 1, 4: TYPE A (shared encoding bits)
- Bars 2, 5: TYPE B
- Bar 3: FILL

TYPE flag encoded across 3 correlated bit positions (byte 0 bit 1, byte 4 bit 7, byte 6 bit 7 in beat 1 events). Multi-bit redundancy or rotation-scattered single flag.

## Next steps (autonomous path)

1. **Sparse encoder integration**: already works (`midi_tools/roundtrip_test.py`). Integrate into UDM → QY70 bytes pipeline.
2. **Dense-user template library**: expand from Summer GT (4 templates) to 100+ by capturing more user patterns.
3. **SGT 76B suffix decoding**: section-specific events might be direct enough to parse — Sec1 fill pattern already visible as `71 78 be 9f 8f c7 e3` repeated.
4. **Hardware probe matrix (F1)**: needs user STORE interaction per probe (slots currently empty on hardware).
5. **Alternative RE via capture**: Pipeline B already production-ready, bypasses dense encoding.

## Known non-trivial facts (from STATUS.md + log.md)

- Sparse encoding PROVEN: R=9×(i+1) cumulative, 6×9-bit fields, 7/7 on known_pattern.syx
- Dense encoding: velocity IMPOSSIBILITY — n42v32 requires F0=426 which no event produces at any rotation
- SGT has 692-byte shared prefix across all 6 sections, 42B super-cycle = 6 events per cycle
- Summer RHY1 track = 384 bytes: 13B×6 headers = 78B + 20 events × 7B = 140B + trailing = ~166B metadata

## Active research tools

- `midi_tools/analyze_summer_bit_attribution.py` — bit invariant analyzer (Session 32)
- `midi_tools/analyze_rhy1_position_r.py` — position-dependent R model search
- `midi_tools/analyze_summer_beat_pattern.py` — beat pattern analysis
- `midi_tools/summer_ground_truth_full.py` — ground truth captor

## Strategy

Pure offline analysis has hit ceiling after 29+ sessions. Moving to **Differential Ground Truth Matrix (DGTM)**: generate minimal-delta patterns on hardware, diff dumps byte-level, isolate each encoding dimension.
