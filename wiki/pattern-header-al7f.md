# QY70 SysEx encoding per AH address

> **Important**: not all QY70 bulk dump sections use Yamaha 7-bit MSB packing.

| AH | Content | Encoding | Notes |
|:---:|---------|----------|-------|
| 0x00 AM=0x00 | Init/close markers | Single-byte param changes | No packing needed |
| 0x00 AM=0x40 | Voice Edit Dump | **7-bit packed** | Confirmed Session 32i — decode normally |
| 0x01 | Song data | **7-bit packed** | Standard Yamaha encoding |
| 0x02 | Pattern data | **7-bit packed** | Standard Yamaha encoding |
| 0x03 | System meta | **7-bit packed** | 32 bytes decoded |
| **0x05** | Pattern name directory | **RAW** | Session 32j — no packing, direct ASCII |
| 0x08 | End-of-dump marker | Single byte | Marker only |

**Why this matters**: parsers must distinguish between `msg.data` (raw payload) and `msg.decoded_data` (7-bit decoded). For AH=0x05, **always use `msg.data`** — applying 7-bit decode garbles the ASCII slot names.

# Pattern Header AL=0x7F — structural map

The pattern header at `AH=0x02 AM=0x7E AL=0x7F` carries metadata for an edit-buffer pattern. It is **640 bytes** in SGT/STYLE2 and **621 bytes** in AMB01 (only difference is the length of the final 128-byte message).

Confidence: **High** for region boundaries and filler patterns. **Medium** for the semantic meaning of variable regions.

## High-level layout (inferred from 3 patterns SGT / AMB01 / STYLE2)

| Offset | Length | Content | Notes |
|--------|--------|---------|-------|
| 0-5 | 6 | Pattern size / type code | Byte 0 varies: SGT=0x5E, AMB01=0x2C, STYLE2=0x6A — looks like per-pattern identifier. Byte 5 always 0x80. |
| 6-13 | 8 | Pattern structure metadata | Bytes 6-13 differ per pattern (contains tempo + time sig candidates). |
| 14-20 | 7 | Common constant block | Identical `00 60 30 98 8c 86 03` across all 3 patterns. Probable ROM pointer / "pattern template end" marker. |
| 21-62 | 42 | Section filler (6×7) | Filled with `be 9f 8f c7 e3 71 78` × 6 (SGT/STYLE2) or `bf df ef f7 fb fd fe` × 6 (AMB01). Likely section-initialization pattern: 6 sections × 7 bytes each. AMB01 has only 1 section populated but still writes 6 filler slots. |
| 63-69 | 7 | Transition | Often ends with `7c 00` (SGT) or `fc 80` (AMB) marker. |
| 70-114 | 45 | **Constants** | These 45 bytes are **byte-identical across all 3 patterns**. Probable global ROM reference / pattern-format version marker. |
| 115-128 | 14 | Variable region #1 | Differs across patterns. SGT=`71 bc 12 89 42 21 10 48 98 0c 06 01 40 03`, AMB=`70 80 00 80 00 00 00 00 00 00 00 00 00 03`, STY=`71 bc 0e 87 41 60 70 38 04 82 81 40 20 43`. Probable pattern-scope meta bitfield. |
| 129-149 | 21 | Mixed | Some constants, some variables. |
| 150-163 | 14 | Variable region #2 | |
| 164-182 | 19 | Variable region #3 | |
| 183-190 | 8 | Mostly constants | |
| 191-620 | 430 | **Big variable block** | 82% byte-level variance between patterns. Contains section-control and sub-pattern structure metadata. |
| 621-639 | 19 | Tail filler | Only present in 640-byte headers; AMB01 stops at 621. |

## What is NOT in this header

Years of reverse-engineering effort have **failed to find** the following items in AL=0x7F:

1. **Bank Select MSB / LSB** (7-bit each, per track)
2. **Program Number** (7-bit, per track)
3. **Volume** (7-bit, per track)
4. **Pan** (7-bit, per track)
5. **Reverb Send, Chorus Send, Variation Send** (per track)

Tried approaches:
- Direct byte sequence search (MSB, LSB, Prog) — zero matches across 8 tracks × 3 patterns
- Byte permutation search — zero matches
- Yamaha 7-bit unpack at all offsets — zero XG-compatible structure
- 9-bit field extraction at every bit start 0-49 — zero correlation
- Cross-pattern byte-position correlation — zero positions where bytes track with voice variations
- Rotation at every R value 0-56 — zero
- Strided block search (stride 2-32, looking for per-track blocks) — zero

**Conclusion (High confidence)**: voice identification is done by the QY70 via an **opaque ROM-internal index** that is encoded here but cannot be decoded to Bank/LSB/Program without:
- Firmware ROM dump from the QY70 chip, or
- Yamaha proprietary documentation.

## What IS in this header

- **Tempo**: encoded in bytes 12-13 area (current decoder in `syx_analyzer._extract_tempo_from_raw` gets this correctly).
- **Time signature**: not yet decoded (decoder returns 4/4 default).
- **Pattern name / style index**: byte 0 varies per pattern. Not yet mapped to style catalog.
- **Section structure**: which sections are active, roughly reflected in the 21-62 filler block count.
- **Section transition**: likely in the 191-620 big variable block, not individually decoded.

## Per-track voice metadata (partial, in track data B14-B23)

The 28-byte track header prefix at `AL=0x00..0x2F` (not this AL=0x7F) contains a **10-byte "voice metadata" field** at offsets B14-B23:

| Offset | Content | Semantics |
|--------|---------|-----------|
| B14-B16 | 3 bytes | Voice variant/config bits. Correlates weakly with bank variant. |
| B17-B20 | 4 bytes | **Voice class signature** (HIGH confidence) |
| B21-B23 | 3 bytes | Stream-state flags, not voice. |

### Voice class signatures (B17-B20)

| Signature hex | Class | Default MSB | Known examples |
|---------------|-------|-------------|----------------|
| `f8 80 8e 83` | Drum (GM Standard Kit family) | 127 | SGT D1/D2/PC drum kits |
| `f8 80 8f 90` | Drum SFX Kit | 126 | AMB01 C4 Drum SFX |
| `78 00 07 12` | Bass voice | 0 | SGT BA Slap Bass 2, AMB01 BA Fretless |
| `78 00 0f 10` | Chord/Melodic voice | 0 | SGT C1/C3/C4, AMB01 C1/C2/C3, STYLE2 C1/C2/C3/C4 |
| `78 00 0e 03` | Chord variant | 0 | — |
| `78 00 07 10` | Chord-short | 0 | — |
| `0b b5 8a 7b` | XG extended | variable | — |

These signatures tell you the voice **class** (drum/bass/chord) but NOT the specific voice within the class. The 10-byte B14-B23 fingerprint is partially unique (see `data/voice_signature_db.json` for the 23 signatures mapped from our 3 reference patterns), but **not bijective** — the same signature can correspond to multiple voices.

## How to get full voice info

1. **Capture the XG stream when the pattern loads** (`midi_tools/capture_playback.py --all`) — records all `Model 4C` Parameter Change messages plus channel events (CC 0/32, Program Change). This contains Bank MSB/LSB/Program for each of the 8 parts.

2. **Query XG Multi Part after the pattern is loaded** (`midi_tools/capture_complete.py`) — sends `F0 43 20 4C 08 PP 00 F7` for each part `PP` (0-15), receives 41-byte Multi Part Bulk responses. This gives full voice + mixer state.

3. **Merge bulk + XG into one .syx** — `capture_complete.py` does this automatically. The resulting file, when passed to `qymanager info`, shows complete voice info (via `syx_analyzer._parse_xg_multi_part`).

## Related pages

- [bitstream.md](bitstream.md) — per-event R rotation inside track data
- [decoder-status.md](decoder-status.md) — overall confidence per format component
- [session-32f-captures.md](session-32f-captures.md) — the 3 reference patterns used for signature DB
