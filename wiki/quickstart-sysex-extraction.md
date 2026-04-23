# Quickstart: extract everything from a QY70 SysEx

This guide shows the fastest path to get **all data** from a QY70 pattern.

## Workflow decision tree

```
Do you have the QY70 connected via MIDI?
│
├── YES  → Workflow A: live capture  (recommended — best results)
│         • Load the pattern on the QY70
│         • Run: uv run python3 midi_tools/capture_complete.py -o full.syx
│         • Run: uv run qymanager info full.syx
│
└── NO   → Do you have an existing .syx + capture JSON?
          │
          ├── YES → Workflow B: merge captures
          │         • Run: uv run qymanager merge bulk.syx capture.json -o full.syx
          │         • Run: uv run qymanager info full.syx
          │
          └── NO   → Workflow C: fallback (partial)
                    • Run: uv run qymanager info pattern.syx
                    • Voice class (drum/bass/chord) reliable
                    • Bank/LSB/Prog only via signature DB (23 trained entries)
                    • Volume/Pan/FX default to XG init
                    • Run: uv run qymanager audit pattern.syx
                      (reports exactly what's extractable)
```

## One-liner for each scenario

**Live hardware** (produces full info):
```bash
uv run python3 midi_tools/capture_complete.py -o out.syx && \
uv run qymanager info out.syx
```

**Merge existing captures**:
```bash
uv run qymanager merge bulk.syx capture.json -o out.syx && \
uv run qymanager info out.syx
```

**Inspect what a .syx contains**:
```bash
uv run qymanager audit file.syx
```

**Multi-slot bulk file** (BULK OUT → All):
```bash
uv run qymanager bulk-summary bulk_all.syx
```

**Focus on XG state only**:
```bash
uv run qymanager xg inspect file.syx
```

## What's in a full .syx from workflow A or B

After `qymanager info full.syx` you see:

| Section | Content |
|---------|---------|
| Header | File, format, status, active tracks/sections |
| Timing | Tempo (from raw bytes), time signature (assumed) |
| Global Effects | Reverb/Chorus/Variation type (via XG Effects) |
| XG System | Master Vol/Transpose/Tune + init flags |
| XG Drum Setup | Per-note drum customizations (16 params × 128 notes) |
| Voice Edit Dumps | User voice edits (if captured) |
| Pattern Directory | Slot names (AH=0x05) |
| Style Sections | Intro/MainA/B/FillAB/BA/Ending status |
| Track Configuration | 8 tracks × Voice/Vol/Pan/Rev/Cho |
| Extended XG | Dry Level, Filter Cutoff, Note Shift (if customized) |
| SysEx Message Statistics | Byte counts, checksum validity |

## Workflow C caveats

If you only have the pattern bulk (no XG state):

- **Voice class** (drum/bass/chord category): reliable via B17-B20 signature
- **Voice MSB/LSB/Prog**: best-effort via signature DB:
  - Unambiguous signatures (conf=1.0): correct Bank/LSB/Prog
  - Ambiguous signatures: falls back to class default
- **Volume/Pan/Reverb/Chorus**: not available — shows XG init defaults
- **Global Effects**: defaults (Hall 1 / Chorus 1 / No Variation)
- **XG Drum Setup**: not available

The pattern bulk encodes voice via a **ROM-internal index** that cannot be
decoded to Bank/LSB/Prog without firmware access. This is architectural,
not a missing feature of the tool.

## Structural reference

- [pattern-header-al7f.md](pattern-header-al7f.md) — 640B header structure map
- [voice-extraction-workflow.md](voice-extraction-workflow.md) — detailed workflows
- [xg-multi-part.md](xg-multi-part.md) — XG parameter definitions
- [sysex-format.md](sysex-format.md) — QY70 SysEx format reference
