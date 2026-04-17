# Unified Data Model (UDM)

**Status**: production — covers System, Multi Part, Drum Setup, Effects, Song, Pattern,
Chord Track, Groove Template, Phrase.
**Introduced**: Sessions 30a–30e (F1–F2 of the integrated plan).

The UDM is the format-agnostic in-memory representation that every parser decodes into
and every emitter encodes from. It lives in `qymanager/model/`. Editor logic, converter
logic, and realtime XG emission all operate on the UDM — never on raw bytes.

Related pages:
- [pattern-editor.md](pattern-editor.md) — the Pipeline-B pattern editor (predates UDM but
  is being progressively migrated onto it).
- [conversion-roadmap.md](conversion-roadmap.md) — pipeline A/B status and how UDM fits
  into the converter.
- [q7p-format.md](q7p-format.md), [blk-format.md](blk-format.md),
  [xg-parameters.md](xg-parameters.md) — format-specific details that parsers consume.

## Schema at a glance

```
Device
├── model: DeviceModel = QY70 | QY700
├── system:     System
├── multi_part: list[MultiPart]      # 16 parts on QY70, 32 on QY700
├── drum_setup: list[DrumSetup]      # 1 kit on QY70, 2 kits on QY700
├── effects:    Effects
│   ├── reverb:    Reverb    (type_code + params)
│   ├── chorus:    Chorus    (type_code + params)
│   └── variation: Variation (type_code + params, QY700 only)
├── songs:      list[Song]           # each with tracks, chord track, tempo changes
├── patterns:   list[Pattern]        # sections, chord track, groove ref
├── phrases:    list[Phrase]         # user phrases (ph_category, ph_type, events)
├── groove_templates: list[GrooveTemplate]
├── fingered_zone: FingeredZone
└── utility_flags: UtilityFlags
```

Enum string values are stable (they appear in serialized UDM JSON and in CLI paths):

| Enum          | Values                                                              |
| ------------- | ------------------------------------------------------------------- |
| `DeviceModel` | `QY70`, `QY700`                                                     |
| `SectionName` | `Main_A..D`, `Fill_AA..DD`, `Fill_CC`, `Fill_DD`, `Intro`, `Ending` |
| `PhraseType`  | `Bypass`, `Bass`, `Chord1`, `Chord2`, `Parallel`                    |
| `VoiceClass`  | `Normal`, `Drum`                                                    |

## Invariants

These invariants are enforced via property tests in `tests/property/test_udm_invariants.py`
and unit tests in `tests/test_udm_schema.py`:

1. **XG roundtrip**: for every XG Parameter Change that hits a supported UDM path,
   `parse_xg_bulk_to_udm(emit(udm)) == udm` for that field.
2. **Transpose centring**: `system.transpose = raw - 64` (raw is the 7-bit XG value).
3. **Bank triplet last-write-wins**: when the same part receives multiple bank/program
   writes, the final state reflects the last write.
4. **`Voice` is frozen**: use `dataclasses.replace(voice, ...)` to mutate. Direct
   attribute assignment raises `FrozenInstanceError`.
5. **Schema validation** is the only range/enum gate: `qymanager.editor.schema.validate()`.
   Internal code trusts the UDM.

## Parsing + emitting

| Format                 | Parse module                                      | Emit module                                 |
| ---------------------- | ------------------------------------------------- | ------------------------------------------- |
| QY700 Q7P              | `qymanager.formats.qy700.q7p_reader`              | `qymanager.formats.qy700.q7p_writer`        |
| QY70 `.syx` (sparse)   | `qymanager.formats.qy70.syx_parser`               | `qymanager.formats.qy70.syx_writer`         |
| XG bulk (any Yamaha)   | `qymanager.formats.xg_bulk.parse_xg_bulk_to_udm`  | `qymanager.editor.ops.make_xg_messages`     |
| Standard MIDI File     | `qymanager.formats.smf.parse_smf_to_udm`          | `qymanager.formats.smf.emit_udm_to_smf`     |

The dispatcher `qymanager.formats.io.load_device(path)` picks the parser from the file
extension; for `.syx` it tries XG bulk first and falls back to QY70 sparse on failure.

## Editor surface

The editor is built on three layers:

1. **`qymanager.editor.schema`** — `validate(path, value)` and `encode_xg(path, value)`.
   Centralised range/enum gate; knows how to map signed UDM values to 7-bit XG bytes
   (transpose, cutoff, resonance, bend pitch).
2. **`qymanager.editor.address_map`** — `resolve_address(path)` returns the `(AH, AM, AL)`
   triple for a UDM path, so the same edit can be written to a file **or** emitted live.
3. **`qymanager.editor.ops`** — `set_field`, `get_field`, `apply_edits`,
   `make_xg_messages`. The auto-grow helpers (`_ensure_part`, `_ensure_kit`,
   `_ensure_note`, `_ensure_variation`) extend the UDM on demand so path-based edits
   never fail on missing containers.

Every CLI command that mutates a device funnels through these layers, so the offline
editor and the realtime XG emitter are literally the same code path with a different
sink (`save_device(path)` vs `RealtimeSession.send_raw_sysex`).

## Lossy conversion policy

`qymanager.converters.lossy_policy.apply_policy(device, target_model, keep, drop)`:

- **Structural normalization** always happens when `target_model` differs (e.g., parts
  17-32 stripped when converting to QY70, Variation dropped when target has no Variation
  block). This is independent of `keep`/`drop`.
- **Warning emission** is controlled by `keep` and `drop`. `keep=[]` (default) warns
  about every dropped/adapted field; listing a field in `keep` silences its warning;
  listing one in `drop` forces a warning even if it would otherwise be silent.

Named groups live in `_NAMED_GROUPS` and use the serialized enum strings
(e.g., `"fill-cc-dd": ["sections.Fill_CC", "sections.Fill_DD"]`).

## Extending the UDM

To add a new format or a new parameter:

1. **Add the field** to the relevant dataclass in `qymanager/model/`.
2. **Extend the schema** in `qymanager/editor/schema.py` with a `Range` or `Enum` entry.
3. **Extend the address map** in `qymanager/editor/address_map.py` with the XG triple.
4. **Wire the parser**: update `xg_bulk._apply_*` and/or the format-specific parser.
5. **Wire the emitter**: `ops.make_xg_messages` will pick it up automatically once the
   path is resolvable.
6. **Test**: unit test in `tests/test_<format>_udm.py`, property test in
   `tests/property/test_udm_invariants.py`.

Confidence: High. The shape has held across F1–F5 with no schema-breaking churn.
