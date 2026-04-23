# Voice extraction from SysEx — complete workflow

This page documents how to extract **all** pattern information (including voice assignments) from a QY70 via SysEx capture. It answers: *"What exactly is in a .syx file, and how do I get everything I need out of it?"*

## Summary: what the QY70 exposes via SysEx

| Address | Content | Size | In "BULK OUT All" |
|---------|---------|:----:|:----:|
| `AH=0x02 AM=0x7E AL=0x00..0x2F` | Pattern event streams (8 tracks × 6 sections) | 128-768 B per track | ✓ |
| `AH=0x02 AM=0x7E AL=0x7F` | Pattern header (tempo, section structure) | 640 B | ✓ |
| `AH=0x02 AM=0x00..0x3F AL=...` | User pattern **slots** (U01-U64 stored) | varies | ✓ |
| `AH=0x01 AM=0x00 AL=...` | **Song** data (8 songs × structure) | ~870 B | ✓ |
| `AH=0x03 AM=0x00 AL=0x00` | System meta (Master Tune/Volume) | 32 B | ✓ |
| `AH=0x05 AM=0x7E AL=...` | Pattern name directory (20 user slots) | 320 B | ✗ |
| `Model 0x4C AH=0x08 AM=0x00..0x0F` | **XG Multi Part** (Bank/LSB/Prog/Vol/Pan/Fx per part) | 41 B/part × 16 | ✗ |

**"BULK OUT All" captures 5 of 7 address types.** The pattern name directory and XG Multi Part state must be requested separately.

## Structural finding — voice encoding in pattern bulk

The pattern header at `AL=0x7F` (640 bytes) contains a 99-byte "mixer parameters" region (offsets 0x1B9-0x21B) and a 14-byte "voice/bank config" region (0x0C6-0x0D2). **Neither region contains byte- or bit-encoded Bank MSB/LSB/Program numbers.** After 7+ iterations of systematic analysis (direct search, permutation, 7-bit unpack, 9-bit fields, strided blocks, brute-force bit extraction at every offset with every width), the conclusion is:

> The voice is stored via an **opaque ROM-internal index**. Without Yamaha firmware documentation or ROM dump, voice MSB/LSB/Prog cannot be decoded from the pattern bulk alone.

See [pattern-header-al7f.md](pattern-header-al7f.md) for the structural map of the 640B header.

## Three workflows for "everything from SysEx"

### A — Live capture (recommended)

Use `midi_tools/capture_complete.py`. This connects to the QY70 via MIDI, performs the Init handshake, then requests all four address types: pattern bulk, pattern name directory, system meta, and XG Multi Part per part. All responses are saved into one `.syx` file.

```bash
uv run python3 midi_tools/capture_complete.py -o complete.syx
uv run qymanager info complete.syx
```

The resulting file, when opened with `qymanager info`, shows the complete voice info (Bank MSB/LSB/Prog/Vol/Pan/Rev/Chor) for all 8 tracks plus the pattern name from the directory.

### B — Merge pre-existing captures

If you already have a pattern bulk `.syx` and a separate load-capture JSON (from `capture_xg_stream.py` or similar), merge them:

```bash
uv run python3 midi_tools/load_json_to_syx.py load.json \
    -o complete.syx \
    --merge-with pattern.syx
uv run qymanager info complete.syx
```

The JSON is flattened into raw MIDI bytes (CC, PC, SysEx) and prepended/appended to the bulk. `syx_analyzer._parse_xg_multi_part` scans raw bytes for both Model 4C Parameter Change messages and channel events, producing the same result as workflow A.

### C — Pattern-only fallback (partial)

If you only have the pattern bulk (`BULK OUT → Pattern`), voice info is partial:
- **Voice class** (drum/bass/chord) — 100% reliable via B17-B20 class signature
- **Bank MSB/LSB/Prog** — via `data/voice_signature_db.json` lookup, reliable only when confidence = 1.0 (single-voice signatures). For ambiguous signatures (multiple voices share the same 10-byte fingerprint), falls back to class default.
- **Vol/Pan/Rev/Chor** — not available, shown as XG defaults (100, center, 40, 0).

A yellow warning in the `qymanager info` output marks this fallback and suggests running the capture_complete.py workflow.

## Verifying a workflow end-to-end

The integration test `tests/test_voice_extraction_pipeline.py::test_xg_merge_gives_full_voice_info` merges AMB01_bulk.syx + AMB01_load.json and verifies all 8 tracks recover their exact Bank/LSB/Prog values. This is CI-enforced.

## Useful companion tools

- `midi_tools/bulk_all_summary.py <file>` — list populated pattern slots inside a BULK_ALL .syx (AH=0x02 AM=0x00-0x3F). Complements `qymanager info` which targets single-pattern files.
- `midi_tools/load_json_to_syx.py` — convert a capture JSON to raw .syx bytes; use `--merge-with` to prepend a pattern bulk.

## Related pages

- [pattern-header-al7f.md](pattern-header-al7f.md) — the 640B header structural map
- [xg-multi-part.md](xg-multi-part.md) — XG Multi Part Bulk format (41 B per part)
- [sysex-format.md](sysex-format.md) — Yamaha 7-bit SysEx encoding
- [decoder-status.md](decoder-status.md) — per-component RE confidence
