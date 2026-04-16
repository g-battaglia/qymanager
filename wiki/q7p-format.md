# Q7P File Format

Binary file format for the [QY700](qy700-device.md) pattern files.

## File Properties

| Property | Value |
|----------|-------|
| Extension | `.Q7P` |
| Size | 3072 bytes (basic) or 5120 bytes (full) |
| Encoding | Raw 8-bit binary |
| Byte order | Big-endian |
| Header magic | `YQ7PAT     V1.00` (16 bytes at 0x000) |

## Complete Structure Map

```
Offset    Size    Description                          Status
────────────────────────────────────────────────────────────
0x000     16      Header "YQ7PAT     V1.00"            Verified
0x010     1       Pattern number (slot)                Verified
0x011     1       Pattern flags                        Verified
0x030     2       Size marker (0x0990 = 2448 BE)       Verified
0x100     32      Section pointers (16 × 2B BE)        Verified
0x120     96      Section config entries (9B each)      Verified
0x188     2       Tempo (BE, ÷10 for BPM)              Verified
0x18A     1       Time signature (0x1C = 4/4)          Verified
0x190     16      Channel assignments (16 tracks)      Verified
0x1DC     8       Track numbers (00-07)                Verified
0x1E4     2       Track enable flags (bitmask)         Verified
0x1E6     16      RESERVED — NOT Bank MSB             ⚠ See bricking
0x1F6     16      RESERVED — NOT Program              ⚠ See bricking
0x206     16      RESERVED — NOT Bank LSB             ⚠ See bricking
0x226     16      Volume (16 tracks)                   Verified
0x246     16      Chorus Send (16 tracks)              Verified
0x256     16      Reverb Send (16 tracks)              Verified
0x276     74      Pan data (multi-section)             Verified
0x360     80      Phrase velocity values               Session 18
0x3B0     712     Velocity/parameter table             Session 18
0x678     48      Sequence config header               Session 18
0x6A8     30      Zero fill                            Verified
0x6C6     32      Velocity LUT block 1 (0x64=vel100)   Session 18
0x6E6     40      Zero fill                            Verified
0x716     64      Velocity LUT block 2 (0x64=vel100)   Session 18
0x756     128     Event data (commands + drum notes)   Session 18
0x7D6     64      Velocity LUT block 3 (0x64=vel100)   Session 18
0x816     64      Zero fill                            Verified
0x856     16      Track flags? (0x03 repeated)         Unknown
0x866     16      Padding (0x40)                       Verified
0x876     10      Pattern name (ASCII)                 Verified
0x9C0     336     Fill area (0xFE bytes)               Verified
0xB10     240     Padding (0xF8 bytes)                 Verified
```

## Section Pointers (0x100)

16 entries of 2-byte big-endian. Effective offset = `pointer_value + 0x100`.
Empty/unused sections use `0xFEFE`.

## Section Config (9 bytes each)

```
F0 00 FB pp 00 tt C0 bb F2
│        │     │     │  └── End marker
│        │     │     └───── Bar count
│        │     └─────────── Track ref
│        └───────────────── Phrase index
└────────────────────────── Start marker
```

## Tempo (0x188)

```python
bpm = struct.unpack(">H", data[0x188:0x18A])[0] / 10.0
```

## Phrase Velocity Area (0x360-0x3B0) — Session 18

80 bytes of per-event velocity values. Range observed: `0x2D`-`0x7C` (45-124). Values outside `0x40` padding suggest real velocity data — NOT the D0/E0 byte-oriented commands expected by the 5120-byte phrase parser.

## Velocity/Parameter Table (0x3B0-0x677) — Session 18

712 bytes. Sparse structure with regions:

| Offset | Content | Notes |
|--------|---------|-------|
| 0x3B0-0x3D0 | `0x7F`/`0x33`/`0x34`/`0x40` | Sparse values |
| 0x3D1-0x3FC | Config params: `0x18 4D 27 4D 34...` | Structured data |
| 0x400-0x677 | `0x5F`/`0x7F`/`0x3F`/`0x20` blocks | Alternating patterns |

Purpose unknown. Possibly per-beat parameters, groove template, or note-attribute lookup.

## Sequence Events (0x678-0x870) — Session 18

504 bytes. **Contains the actual musical note data** for 3072-byte Q7P files. The 5120-byte phrase parser (D0/E0 commands) does NOT apply here.

### Sub-structure

```
0x678-0x6A7  Config header (48 bytes)
0x6A8-0x6C5  Zero fill (30 bytes)
0x6C6-0x6E5  Velocity LUT 1 — 32 × 0x64 (vel=100)
0x6E6-0x715  Zero fill (48 bytes)
0x716-0x755  Velocity LUT 2 — 64 × 0x64 (vel=100)
0x756-0x7D5  Event data — commands + note values (128 bytes)
0x7D6-0x815  Velocity LUT 3 — 64 × 0x64 (vel=100)
0x816-0x855  Zero fill
0x856-0x865  Track flags (16 × 0x03)
0x866-0x875  Padding (16 × 0x40)
```

### Config Header (0x678-0x6A7)

```
40 40 40 40  01 00 12 0A  08 0D 31 40  40 41 00 06
36 4D 6A 00  40 40 00 05  00 00 0D 05  06 83 13 88
13 88 00 4A  00 20 40 40  00 00 00 7F  40 00 00 00
```

Notable values: `0x1388` = 5000 (appears twice, purpose unknown). `0x7F` at 0x6A3 may be note range upper bound.

### Event Data Commands (0x756-0x7D5)

Uses command bytes `>= 0x80`, distinct from the 5120-byte D0/E0 format:

| Command | Meaning (hypothesis) | Confidence |
|---------|---------------------|------------|
| `0x83` | Note group — followed by 1-6 simultaneous GM drum notes, padded with `0x7F` | Medium |
| `0x84` | Timing/step — followed by 1 byte (often `0x1F` = 31) | Low |
| `0x88` | Section end/marker — followed by 1 byte (seen `0x87`) | Low |
| `0x82` | Unknown — seen once after `0x84` | Low |

Example event stream (T01.Q7P USER TMPL):

```
84 1F  83 22 25 26 7F 7F    — step(31?) then BD2+SideStk+Snare1
84 1F  83 26 28 7F 7F 7F    — step(31?) then Snare1+Snare2
84 1F  83 22 28 7F 7F 7F    — step(31?) then BD2+Snare2
2A 2C 2E 7F 7F 7F 7F 7F    — HHclose+HHpedal+HHopen (no command prefix)
88 87 7F 7F 7F 7F 7F 7F    — end marker?
```

### Note Pool / Instrument Table (0x796-0x7D5)

8 groups of 8 bytes, each listing related drum instruments (padded with `0x7F`):

| Group | Notes (hex) | GM Drums |
|-------|-------------|----------|
| 0 | `28 28 24 28 28 28` | Snare2×4, Kick1, Snare2 |
| 1 | `22 22 24 22 22` | BD2×4, Kick1 |
| 2 | `26 26 23 26 26` | Snare1×4, Kick2(35) |
| 3 | `3B 33 35` | Ride2, Ride1, RideBell |
| 4 | `2E 2A` | OpenHH, CloseHH |
| 5 | `3E 3E 21 3E 3E 46 45 52` | MuteConga×4, n33, Maracas, Cabasa, Shaker |
| 6 | `1A 1A 1B 19 1C 1B` | XG: SnareRoll, FingerSnap, HiQ, Slap |
| 7 | `25 25` | SideStick×2 |

Purpose: possibly per-beat instrument assignment (which note variant plays on each beat), or a note palette referenced by the event stream. Confidence: Low.

### Velocity LUT Blocks

Three blocks of `0x64` (100 decimal = default MIDI velocity). Sizes: 32, 64, 64 bytes. Likely per-event velocity assignments — one value per note event.

## 5120-byte Phrase Event Format — Session 23

5120-byte Q7P files contain inline phrase blocks starting at 0x200. Each phrase has a 28-byte header followed by byte-oriented MIDI event commands. **This format is completely different from the 3072-byte 0x83/0x84 command format.**

### Phrase Block Header (28 bytes)

```
Offset  Size  Description
0       12    Name (ASCII, space-padded)
12      2     Marker: 03 1C (normal) or 07 1C (variant)
14      4     00 00 00 7F (note range? always same)
18      2     00 07 (track flags?)
20      2     90 00 (MIDI channel status?)
22      2     00 00 (reserved)
24      2     Tempo × 10, big-endian (e.g., 04 B0 = 120 BPM)
26      2     F0 00 (MIDI data start marker)
28+     var   MIDI events (terminated by F2)
```

### Event Commands (Confidence: High)

Verified from DECAY.Q7P analysis (Session 23). Notes use **standard GM numbering**.

| Command | Size | Format | Description |
|---------|------|--------|-------------|
| `D0` | 4 | `D0 [vel] [GM_note] [gate]` | Drum/percussion note |
| `D1` | 4 | `D1 [vel] [GM_note] [gate]` | Drum note variant (e.g., rim) |
| `DC`-`DF` | 4 | same as D0 | Drum variants (ghost/accent?) |
| `E0` | 5 | `E0 [gate] [param] [GM_note] [vel]` | Melody note (chords, bass) |
| `C1` | 3 | `C1 [note] [vel_or_gate]` | Short note (arpeggios, ticks) |
| `A0`-`AF` | 2 | `Ax [value]` | Delta time: `(x-0xA0)*128+value` ticks |
| `BA` | 2 | `BA [value]` | Control/sustain + small delta |
| `BB` | 2 | `BB [value]` | Release/damper + small delta |
| `BC` | 2 | `BC [param]` | Control change |
| `BE` | 2 | `BE [param]` | Note off / all notes off |
| `F0 00` | 2 | marker | Start of MIDI data |
| `F2` | 1 | marker | End of phrase |
| `0x40` | - | padding | Padding to next block boundary |

### Delta Time Formula

**delta_ticks = (cmd - 0xA0) × 128 + value** at **ppqn = 480**

Examples:
- `A0 78` = 0×128+120 = **120 ticks** (16th note)
- `A1 70` = 1×128+112 = **240 ticks** (8th note)
- `A3 60` = 3×128+96 = **480 ticks** (quarter note)
- `A5 50` = 5×128+80 = **720 ticks** (dotted quarter)
- `AD 10` = 13×128+16 = **1680 ticks** (3.5 beats)

### Verified Note Mapping (from DECAY.Q7P)

| Phrase | Event | Byte 2 (GM note) | GM Instrument | Confidence |
|--------|-------|-------------------|---------------|------------|
| kick | D0 | 0x24 = 36 | Bass Drum 1 | High |
| hi hats | D0 | 0x2A/0x2E = 42/46 | Closed/Open HH | High |
| tom | D0 | 0x29/0x30/0x2F = 41/48/47 | Floor/Mid Toms | High |
| rim | D1 | 0x25 = 37 | Side Stick | High |
| piano pad | E0 | 0x30/0x34/0x37 = 48/52/55 | C3/E3/G3 (C major) | High |
| bass | E0 | 0x24/0x29 = 36/41 | C2/F2 | High |
| dream bells | C1 | 0x5B/0x58/0x54 = 91/88/84 | G6/E6/C6 arpeggio | High |

### Chord Pattern Structure

Phrases without delta events represent chord progressions. Notes are stacked (simultaneous) and groups are separated by `BE 00` (note off). Example from "piano pad":

```
E0 1E 00 37 7F   → G3 vel=127  ┐
E0 1E 00 34 7F   → E3 vel=127  ├ C major chord
E0 1E 00 30 7F   → C3 vel=127  ┘
BE 00            → release
E0 1E 00 35 7F   → F3 vel=127  ┐
E0 1E 00 39 7F   → A3 vel=127  ├ F major chord
E0 1E 00 30 7F   → C3 vel=127  ┘
BE 00            → release
F2               → end
```

The pattern duration (4 bars) is divided equally among chord groups by the playback engine.

## T01.Q7P vs TXX.Q7P — Session 18

Both are 3072-byte files. **Phrase data and sequence events are IDENTICAL.** Differences are only in metadata:

| Area | T01 | TXX |
|------|-----|-----|
| Pattern number (0x010) | `0x02` | `0x01` |
| Section pointers (0x102+) | 1 section only | 4 sections |
| Section configs (0x129+) | Garbage/overflow after S0 | 4 valid configs (phrases 0-3, tracks 0-3, 4 bars each) |
| Name (0x876) | "USER TMPL " | "USER TMPL " |

TXX is a multi-section template (4 phrases × 4 tracks × 4 bars). T01 is single-section.

## Critical Safety Note

Offsets `0x1E6`, `0x1F6`, `0x206` were hypothesized as Bank MSB/Program/Bank LSB but are ALL ZERO in both test files. Writing non-zero values here caused [QY700 bricking](bricking.md). These areas must NOT be written to.

See [Format Mapping](format-mapping.md) for QY70 ↔ QY700 correspondence.
