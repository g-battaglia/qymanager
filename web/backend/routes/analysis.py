from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from qymanager.utils.xg_voices import get_voice_name, get_voice_category

from ..session import get_session

router = APIRouter(tags=["analysis"])


class SyxAnalysisTrack(BaseModel):
    index: int
    name: str
    long_name: str
    channel: int
    has_data: bool
    data_bytes: int
    active_sections: list[str]
    bank_msb: int
    bank_lsb: int
    program: int
    voice_name: str
    voice_source: str
    voice_bit_distance: int | None = None
    volume: int
    pan: int
    reverb_send: int
    chorus_send: int
    variation_send: int
    is_drum_track: bool


class SyxAnalysisSection(BaseModel):
    index: int
    name: str
    has_data: bool
    phrase_bytes: int
    track_bytes: int
    active_tracks: list[int]
    bar_count: int
    beat_count: int


class SyxAnalysisEffect(BaseModel):
    name: str
    msb: int
    lsb: int


class SyxAnalysisStats(BaseModel):
    total_messages: int
    bulk_dump_messages: int
    parameter_messages: int
    valid_checksums: int
    invalid_checksums: int
    total_encoded_bytes: int
    total_decoded_bytes: int


class SyxAnalysisSystem(BaseModel):
    master_tune_cents: int | None = None
    master_volume: int | None = None
    master_attenuator: int | None = None
    transpose: int | None = None
    xg_system_on: bool = False


class SyxAnalysisSlot(BaseModel):
    slot: int
    name: str


class SyxAnalysisDrumNote(BaseModel):
    note: int
    note_name: str
    level: int | None = None
    pan: int | None = None
    reverb_send: int | None = None
    chorus_send: int | None = None
    pitch_coarse: int | None = None
    pitch_fine: int | None = None


class SyxAnalysisDrumKit(BaseModel):
    kit_index: int
    notes: list[SyxAnalysisDrumNote] = Field(default_factory=list)


class SyxAnalysisResponse(BaseModel):
    available: bool
    source_format: str
    format_type: str | None = None
    pattern_name: str | None = None
    filesize: int = 0
    data_density: float = 0.0
    active_section_count: int = 0
    section_total: int = 6
    active_track_count: int = 0
    track_total: int = 8
    tempo: int | None = None
    time_signature: str | None = None
    reverb: SyxAnalysisEffect | None = None
    chorus: SyxAnalysisEffect | None = None
    variation: SyxAnalysisEffect | None = None
    tracks: list[SyxAnalysisTrack] = Field(default_factory=list)
    sections: list[SyxAnalysisSection] = Field(default_factory=list)
    stats: SyxAnalysisStats | None = None
    system: SyxAnalysisSystem | None = None
    pattern_directory: list[SyxAnalysisSlot] = Field(default_factory=list)
    drum_kits: list[SyxAnalysisDrumKit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    note: str | None = None


class VoiceResolveRequest(BaseModel):
    bank_msb: int = 0
    bank_lsb: int = 0
    program: int = 0
    channel: int = 1


class VoiceResolveResponse(BaseModel):
    name: str
    category: str
    is_drum: bool
    is_sfx: bool


class PhraseEventModel(BaseModel):
    tick: int
    channel: int
    kind: str
    data1: int
    data2: int
    note_name: str | None = None
    velocity: int | None = None


class PhraseModel(BaseModel):
    name: str
    tempo: int
    note_count: int
    event_count: int
    events: list[PhraseEventModel]


class PhrasesResponse(BaseModel):
    source: str
    phrases: list[PhraseModel]
    note: str | None = None


_NN_TAG_RE = re.compile(r"\(NN\s+d=(\d+)\)\s*$")


def _split_voice_tag(voice_name: str) -> tuple[str, str, int | None]:
    """Split `"Dance Kit (DB)"` → (`"Dance Kit"`, `"db"`, None).

    SyxAnalyzer suffixes voice names with confidence tags:
      - "(DB)"                       → signature-DB exact match (tier 1)
      - "(NN d=N)"                   → nearest-neighbour match (tier 1.5)
      - "(class)"                    → short drum class match
      - "(class — exact via XG query)"  → chord/bass/sfx class match
    Names without a tag are treated as resolved from real XG state.

    Returns a 3-tuple `(clean_name, source, bit_distance)` where
    `bit_distance` is populated only for the NN case.
    """
    if not voice_name:
        return ("", "none", None)
    stripped = voice_name.strip()
    if stripped.endswith("(DB)"):
        return (stripped[: -len("(DB)")].strip(), "db", None)
    m = _NN_TAG_RE.search(stripped)
    if m:
        return (stripped[: m.start()].strip(), "nn", int(m.group(1)))
    idx = stripped.rfind("(class")
    if idx != -1 and stripped.endswith(")"):
        return (stripped[:idx].strip(), "class", None)
    return (stripped, "xg", None)


@router.get("/devices/{did}/syx-analysis", response_model=SyxAnalysisResponse)
def get_device_syx_analysis(did: str) -> SyxAnalysisResponse:
    device = get_session().get(did)
    if device is None:
        raise HTTPException(404, "Device not found")

    source = getattr(device, "source_format", None) or "unknown"
    if source != "syx":
        return SyxAnalysisResponse(
            available=False,
            source_format=source,
            note=f"SyX analysis is only available for .syx files (source={source}).",
        )

    raw = getattr(device, "_raw_passthrough", None)
    if not raw:
        return SyxAnalysisResponse(
            available=False,
            source_format=source,
            note="No raw SysEx bytes retained for this device.",
        )

    from qymanager.analysis.syx_analyzer import SyxAnalyzer

    filename = get_session().get_filename(did) or "uploaded.syx"
    try:
        analysis = SyxAnalyzer().analyze_bytes(raw, name=filename)
    except Exception as exc:
        return SyxAnalysisResponse(
            available=False,
            source_format=source,
            note=f"SyX analysis failed: {exc}",
        )

    pattern_name = analysis.pattern_name or ""
    if not pattern_name and filename:
        from pathlib import Path as _P

        stem = _P(filename).stem
        if " - " in stem:
            parts = [p.strip() for p in stem.split(" - ") if p.strip()]
            if len(parts) >= 2:
                pattern_name = parts[1]
            else:
                pattern_name = stem
        else:
            pattern_name = stem

    tracks: list[SyxAnalysisTrack] = []
    for idx, t in enumerate(analysis.qy70_tracks):
        clean_name, voice_source, voice_bit_distance = _split_voice_tag(t.voice_name)
        long_name = ""
        try:
            long_name = SyxAnalyzer.TRACK_LONG_NAMES[idx]
        except (IndexError, AttributeError):
            pass
        tracks.append(
            SyxAnalysisTrack(
                index=idx,
                name=t.name,
                long_name=long_name,
                channel=t.channel,
                has_data=t.has_data,
                data_bytes=t.data_bytes,
                active_sections=list(t.active_sections or []),
                bank_msb=t.bank_msb,
                bank_lsb=t.bank_lsb,
                program=t.program,
                voice_name=clean_name,
                voice_source=voice_source if t.has_data else "none",
                voice_bit_distance=voice_bit_distance if t.has_data else None,
                volume=t.volume,
                pan=t.pan,
                reverb_send=t.reverb_send,
                chorus_send=t.chorus_send,
                variation_send=t.variation_send,
                is_drum_track=t.is_drum_track,
            )
        )

    sections: list[SyxAnalysisSection] = []
    for s in analysis.qy70_sections:
        sections.append(
            SyxAnalysisSection(
                index=s.index,
                name=s.name,
                has_data=s.has_data,
                phrase_bytes=s.phrase_bytes,
                track_bytes=s.track_bytes,
                active_tracks=list(s.active_tracks or []),
                bar_count=s.bar_count,
                beat_count=s.beat_count,
            )
        )

    time_sig = f"{analysis.time_signature[0]}/{analysis.time_signature[1]}" if analysis.time_signature else None

    warnings: list[str] = []
    any_db = any(t.voice_source == "db" for t in tracks)
    any_class = any(t.voice_source == "class" for t in tracks)
    if any_db or any_class:
        parts = []
        if any_db:
            parts.append("(DB) tracks are matched against a 23-signature database")
        if any_class:
            parts.append("(class) tracks only expose their category (drum/bass/chord)")
        warnings.append(
            "Voice info is partial. This .syx carries an opaque ROM index for voices, not raw Bank/Program. "
            + " · ".join(parts)
            + ". Capture XG state alongside the bulk for full voice resolution."
        )

    system_info: SyxAnalysisSystem | None = None
    xg_sys = getattr(analysis, "xg_system", {}) or {}
    if xg_sys:
        if any(xg_sys.get(f"master_tune_nibble_{i}") is not None for i in range(4)):
            mt_nibbles = [xg_sys.get(f"master_tune_nibble_{i}") or 0 for i in range(4)]
            word = (
                (mt_nibbles[0] << 12)
                | (mt_nibbles[1] << 8)
                | (mt_nibbles[2] << 4)
                | mt_nibbles[3]
            )
            master_tune_cents = max(-100, min(100, int(round((word - 0x0400) * 0.05))))
        else:
            master_tune_cents = None
        transpose_raw = xg_sys.get("master_transpose")
        transpose = (transpose_raw - 64) if transpose_raw is not None else None
        system_info = SyxAnalysisSystem(
            master_tune_cents=master_tune_cents,
            master_volume=xg_sys.get("master_volume"),
            master_attenuator=xg_sys.get("master_attenuator"),
            transpose=transpose,
            xg_system_on=bool(xg_sys.get("xg_system_on", False)),
        )

    slots: list[SyxAnalysisSlot] = []
    pdir = getattr(analysis, "pattern_directory", None) or {}
    for slot_idx, name in sorted(pdir.items()):
        if isinstance(name, str) and name.strip():
            slots.append(SyxAnalysisSlot(slot=slot_idx, name=name.strip()))

    drum_kits: list[SyxAnalysisDrumKit] = []
    xg_drum_setup = getattr(analysis, "xg_drum_setup", None) or {}
    # Expected shape: {kit_index: {note: {"level": v, "pan": v, ...}}}
    for kit_index, notes_dict in sorted(xg_drum_setup.items()):
        if not isinstance(notes_dict, dict):
            continue
        note_entries: list[SyxAnalysisDrumNote] = []
        for note_num, fields in sorted(notes_dict.items()):
            if not isinstance(fields, dict):
                continue
            note_entries.append(
                SyxAnalysisDrumNote(
                    note=note_num,
                    note_name=GM_DRUM_NOTES.get(note_num, _note_name(note_num)),
                    level=fields.get("level"),
                    pan=fields.get("pan"),
                    reverb_send=fields.get("reverb_send"),
                    chorus_send=fields.get("chorus_send"),
                    pitch_coarse=fields.get("pitch_coarse"),
                    pitch_fine=fields.get("pitch_fine"),
                )
            )
        if note_entries:
            drum_kits.append(
                SyxAnalysisDrumKit(kit_index=kit_index, notes=note_entries)
            )

    return SyxAnalysisResponse(
        available=True,
        source_format=source,
        format_type=analysis.format_type,
        pattern_name=pattern_name or None,
        system=system_info,
        pattern_directory=slots,
        drum_kits=drum_kits,
        filesize=analysis.filesize,
        data_density=analysis.data_density,
        active_section_count=analysis.active_section_count,
        section_total=len(analysis.qy70_sections) or 6,
        active_track_count=analysis.active_track_count,
        track_total=len(analysis.qy70_tracks) or 8,
        tempo=analysis.tempo,
        time_signature=time_sig,
        reverb=SyxAnalysisEffect(
            name=analysis.reverb_type,
            msb=analysis.reverb_type_msb,
            lsb=analysis.reverb_type_lsb,
        ),
        chorus=SyxAnalysisEffect(
            name=analysis.chorus_type,
            msb=analysis.chorus_type_msb,
            lsb=analysis.chorus_type_lsb,
        ),
        variation=SyxAnalysisEffect(
            name=analysis.variation_type,
            msb=analysis.variation_type_msb,
            lsb=analysis.variation_type_lsb,
        ),
        tracks=tracks,
        sections=sections,
        stats=SyxAnalysisStats(
            total_messages=analysis.total_messages,
            bulk_dump_messages=analysis.bulk_dump_messages,
            parameter_messages=analysis.parameter_messages,
            valid_checksums=analysis.valid_checksums,
            invalid_checksums=analysis.invalid_checksums,
            total_encoded_bytes=analysis.total_encoded_bytes,
            total_decoded_bytes=analysis.total_decoded_bytes,
        ),
        warnings=warnings,
    )


@router.post("/resolve-voice", response_model=VoiceResolveResponse)
def resolve_voice(req: VoiceResolveRequest) -> VoiceResolveResponse:
    name = get_voice_name(
        program=req.program,
        bank_msb=req.bank_msb,
        bank_lsb=req.bank_lsb,
        channel=req.channel,
    )
    category = get_voice_category(req.program) if not (req.channel == 10 or req.bank_msb == 127) else "Drum Kit"
    is_drum = req.channel == 10 or req.bank_msb == 127
    is_sfx = req.bank_msb == 64
    return VoiceResolveResponse(name=name, category=category, is_drum=is_drum, is_sfx=is_sfx)


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# General MIDI drum kit note names (channel 10). Standard across XG and GM.
GM_DRUM_NOTES: dict[int, str] = {
    27: "Laser",
    28: "Whip",
    29: "Scratch Push",
    30: "Scratch Pull",
    31: "Stick",
    32: "Square Click",
    33: "Metronome Click",
    34: "Metronome Bell",
    35: "Kick 2",
    36: "Kick 1",
    37: "Side Stick",
    38: "Snare 1",
    39: "Hand Clap",
    40: "Snare 2",
    41: "Low Tom 2",
    42: "Closed Hat",
    43: "Low Tom 1",
    44: "Pedal Hat",
    45: "Mid Tom 2",
    46: "Open Hat",
    47: "Mid Tom 1",
    48: "High Tom 2",
    49: "Crash 1",
    50: "High Tom 1",
    51: "Ride 1",
    52: "Chinese Cymbal",
    53: "Ride Bell",
    54: "Tambourine",
    55: "Splash",
    56: "Cowbell",
    57: "Crash 2",
    58: "Vibraslap",
    59: "Ride 2",
    60: "High Bongo",
    61: "Low Bongo",
    62: "Mute Hi Conga",
    63: "Open Hi Conga",
    64: "Low Conga",
    65: "High Timbale",
    66: "Low Timbale",
    67: "High Agogo",
    68: "Low Agogo",
    69: "Cabasa",
    70: "Maracas",
    71: "Short Whistle",
    72: "Long Whistle",
    73: "Short Guiro",
    74: "Long Guiro",
    75: "Claves",
    76: "High Wood Block",
    77: "Low Wood Block",
    78: "Mute Cuica",
    79: "Open Cuica",
    80: "Mute Triangle",
    81: "Open Triangle",
    82: "Shaker",
    83: "Jingle Bell",
    84: "Bell Tree",
    85: "Castanets",
    86: "Mute Surdo",
    87: "Open Surdo",
}


def _note_name(note: int) -> str:
    octave = note // 12 - 1
    return f"{NOTE_NAMES[note % 12]}{octave}"


def _drum_note_name(note: int) -> str:
    """GM drum name for channel-10 note numbers; falls back to pitch."""
    return GM_DRUM_NOTES.get(note, _note_name(note))


@router.get("/devices/{did}/phrases", response_model=PhrasesResponse)
def get_device_phrases(did: str) -> PhrasesResponse:
    device = get_session().get(did)
    if device is None:
        raise HTTPException(404, "Device not found")

    raw = getattr(device, "_raw_passthrough", None)
    if not raw:
        return PhrasesResponse(
            source=device.source_format,
            phrases=[],
            note="No raw file data available for phrase extraction.",
        )

    source = device.source_format or "unknown"

    if source == "q7p":
        return _parse_q7p_phrases(raw)
    elif source == "syx":
        return _parse_syx_phrases(raw, device)
    else:
        return PhrasesResponse(
            source=source,
            phrases=[],
            note=f"Phrase extraction not implemented for {source} format.",
        )


def _parse_q7p_phrases(raw: bytes) -> PhrasesResponse:
    from qymanager.formats.qy700.phrase_parser import parse_q7p_phrases

    blocks = parse_q7p_phrases(raw)
    phrases: list[PhraseModel] = []

    for block in blocks:
        events: list[PhraseEventModel] = []
        for ev in block.events:
            if ev.event_type in ("drum", "note", "alt_note"):
                events.append(
                    PhraseEventModel(
                        tick=ev.delta,
                        channel=10 if ev.event_type == "drum" else 0,
                        kind=ev.event_type,
                        data1=ev.note,
                        data2=ev.velocity,
                        note_name=_note_name(ev.note),
                        velocity=ev.velocity if ev.velocity > 0 else None,
                    )
                )
        phrases.append(
            PhraseModel(
                name=block.name,
                tempo=block.tempo,
                note_count=block.note_count,
                event_count=len(block.events),
                events=events,
            )
        )

    note = None
    if not phrases:
        note = "No phrase blocks detected in this Q7P file."
    elif all(p.note_count == 0 for p in phrases):
        note = "Phrase blocks found but contain no note events."

    return PhrasesResponse(source="q7p", phrases=phrases, note=note)


def _parse_syx_phrases(raw: bytes, device: object) -> PhrasesResponse:
    from qymanager.analysis.syx_analyzer import SyxAnalyzer
    from qymanager.formats.qy70.sysex_parser import SysExParser
    from qymanager.formats.qy70.encoder_sparse import (
        decode_sparse_track,
        sparse_track_plausibility,
    )

    parser = SysExParser()
    messages = parser.parse_bytes(raw)
    if not messages:
        return PhrasesResponse(
            source="syx", phrases=[], note="No SysEx messages found in this file.",
        )

    section_data: dict[int, bytearray] = {}
    for msg in messages:
        if not msg.is_style_data or msg.decoded_data is None:
            continue
        if msg.address_low == 0x7F:
            continue
        section_data.setdefault(msg.address_low, bytearray()).extend(msg.decoded_data)

    analysis = SyxAnalyzer().analyze_bytes(raw, name="phrases")
    track_labels = SyxAnalyzer.TRACK_NAMES  # D1, D2, PC, BA, C1..C4
    default_channels = SyxAnalyzer.DEFAULT_CHANNELS  # 9..16

    phrases: list[PhraseModel] = []
    decoded_tracks = 0
    plausibility_sum = 0.0

    for al in sorted(section_data):
        td = bytes(section_data[al])
        if len(td) < 48:
            continue
        track_idx = al & 0x7
        sec_idx = al >> 3
        sec_name = SyxAnalyzer.STYLE_SECTION_NAMES[sec_idx] if sec_idx < len(SyxAnalyzer.STYLE_SECTION_NAMES) else f"sec{sec_idx}"
        track_label = track_labels[track_idx] if track_idx < len(track_labels) else f"T{track_idx}"

        events = decode_sparse_track(td)
        if not events:
            continue
        ratio = sparse_track_plausibility(events)
        # Guard-rail: plausible only when ≥60% of events land in the drum
        # / melodic note range. Factory dense styles collapse well below
        # this threshold (~15-25% random chance).
        if ratio < 0.6:
            continue

        channel = default_channels[track_idx] if track_idx < len(default_channels) else 0
        is_drum = track_idx < 2 or channel == 10
        phrase_events: list[PhraseEventModel] = []
        for ev in events:
            if ev["ctrl"]:
                continue
            name = _drum_note_name(ev["note"]) if is_drum else _note_name(ev["note"])
            phrase_events.append(
                PhraseEventModel(
                    tick=int(ev["tick"]),
                    channel=int(channel - 1),
                    kind="drum" if is_drum else "note",
                    data1=int(ev["note"]),
                    data2=int(ev["velocity"]),
                    note_name=name,
                    velocity=int(ev["velocity"]) if ev["velocity"] > 0 else None,
                )
            )

        if not phrase_events:
            continue

        phrases.append(
            PhraseModel(
                name=f"{sec_name} · {track_label}",
                tempo=analysis.tempo or 120,
                note_count=len(phrase_events),
                event_count=len(events),
                events=phrase_events,
            )
        )
        decoded_tracks += 1
        plausibility_sum += ratio

    if not phrases:
        return PhrasesResponse(
            source="syx",
            phrases=[],
            note=(
                "No user-sparse tracks decoded. This file likely contains factory "
                "dense encoding (SGT / style bulk), which fails the R=9 barrel-"
                "rotation decoder (see wiki/decoder-status.md Session 19/20). "
                "Pattern structure and voice assignments remain available in the "
                "main device view; note decoding for dense styles requires the "
                "Pipeline B capture path."
            ),
        )

    avg_ratio = plausibility_sum / max(1, decoded_tracks)
    note = (
        f"Decoded {decoded_tracks} user-sparse track{'s' if decoded_tracks != 1 else ''} "
        f"via R=9×(i+1) barrel rotation (avg plausibility {avg_ratio*100:.0f}%). "
        "Proven on known_pattern.syx 7/7 (Session 14) and validated against user "
        "patterns like MR. Vain. Dense factory styles are skipped because their "
        "encoding is not solved (see wiki/decoder-status.md)."
    )
    return PhrasesResponse(source="syx", phrases=phrases, note=note)
