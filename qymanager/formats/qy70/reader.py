"""
QY70 SysEx file reader.

Reads .syx files containing QY70 style/pattern bulk dumps and
converts them to the common Pattern model (legacy) or the
Unified Data Model (UDM) Device via parse_syx_to_udm().
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from qymanager.models.pattern import Pattern, PatternSettings
from qymanager.models.section import Section, SectionType
from qymanager.models.track import Track, TrackSettings
from qymanager.formats.qy70.sysex_parser import SysExParser, SysExMessage

from qymanager.model import (
    Device,
    DeviceModel,
    Pattern as UdmPattern,
    PatternTrack,
    Phrase,
    Section as UdmSection,
    SectionName,
    TimeSig,
    Voice,
)
from qymanager.model.event import MidiEvent
from qymanager.model.types import EventKind, PhraseCategory


class QY70Reader:
    """
    Reader for QY70 SysEx pattern files.

    Parses .syx files and constructs Pattern objects from the
    contained bulk dump data.

    AL addressing scheme (confirmed from QY70 SGT dump):
        AL = section_index * 8 + track_index
        Section 0 (Intro):   AL 0x00-0x07 (8 tracks)
        Section 1 (Main A):  AL 0x08-0x0F
        Section 2 (Main B):  AL 0x10-0x17
        Section 3 (Fill AB): AL 0x18-0x1F
        Section 4 (Fill BA): AL 0x20-0x27
        Section 5 (Ending):  AL 0x28-0x2F
        Header:              AL 0x7F

    Example:
        pattern = QY70Reader.read("style.syx")
        print(f"Pattern: {pattern.name}, Tempo: {pattern.tempo}")
    """

    # Section index to SectionType mapping (index 0-5, NOT AL address)
    SECTION_MAP = {
        0: SectionType.INTRO,
        1: SectionType.MAIN_A,
        2: SectionType.MAIN_B,
        3: SectionType.FILL_AB,
        4: SectionType.FILL_BA,
        5: SectionType.ENDING,
    }

    # Number of tracks per section
    TRACKS_PER_SECTION = 8

    def __init__(self):
        self.parser = SysExParser()
        self._raw_messages: List[SysExMessage] = []
        self._section_data: Dict[int, bytearray] = {}

    @classmethod
    def read(cls, filepath: Union[str, Path]) -> Pattern:
        """
        Read a QY70 SysEx file and return a Pattern.

        Args:
            filepath: Path to .syx file

        Returns:
            Parsed Pattern object
        """
        reader = cls()
        return reader.parse_file(filepath)

    def parse_file(self, filepath: Union[str, Path]) -> Pattern:
        """
        Parse a SysEx file.

        Args:
            filepath: Path to .syx file

        Returns:
            Parsed Pattern object
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()

        return self.parse_bytes(data)

    def parse_bytes(self, data: bytes) -> Pattern:
        """
        Parse SysEx data from bytes.

        Args:
            data: Raw SysEx file contents

        Returns:
            Parsed Pattern object
        """
        # Parse SysEx messages
        self._raw_messages = self.parser.parse_bytes(data)

        # Group messages by section
        self._organize_messages()

        # Build pattern from messages
        pattern = self._build_pattern()
        pattern.source_format = "qy70"
        pattern._raw_data = data

        return pattern

    def _organize_messages(self) -> None:
        """Organize messages by section index."""
        self._section_data = {}

        for msg in self._raw_messages:
            if msg.is_style_data and msg.decoded_data:
                section_idx = msg.address_low

                if section_idx not in self._section_data:
                    self._section_data[section_idx] = bytearray()

                self._section_data[section_idx].extend(msg.decoded_data)

    def _build_pattern(self) -> Pattern:
        """Build Pattern object from parsed data."""
        pattern = Pattern.create_empty()

        # Parse header/config section (0x7F)
        if 0x7F in self._section_data:
            self._parse_header(pattern, bytes(self._section_data[0x7F]))

        # Parse each section
        for section_idx, section_type in self.SECTION_MAP.items():
            section = self._parse_section(section_idx, section_type)
            if section:
                pattern.sections[section_type] = section

        return pattern

    def _parse_header(self, pattern: Pattern, data: bytes) -> None:
        """
        Parse pattern header/config data.

        Args:
            pattern: Pattern to update
            data: Decoded header data
        """
        if len(data) < 20:
            return

        # Extract tempo (typically at offset 0x0A-0x0B)
        # This needs reverse engineering of the exact format
        # For now, use defaults
        pattern.settings.tempo = 120

        # Name parsing would go here
        # pattern.name = data[offset:offset+10].decode('ascii', errors='replace')

    def _parse_section(self, section_idx: int, section_type: SectionType) -> Optional[Section]:
        """
        Parse a single section from bulk dump data.

        Each section has 8 tracks stored at:
            AL = section_idx * 8 + track_idx  (track_idx 0-7)

        Args:
            section_idx: Section index (0-5)
            section_type: Type of section

        Returns:
            Parsed Section or None if no data
        """
        # Collect per-track data for this section using correct AL addressing
        track_data_map: Dict[int, bytes] = {}
        has_any_data = False

        for track_idx in range(self.TRACKS_PER_SECTION):
            al = section_idx * self.TRACKS_PER_SECTION + track_idx
            data = self._section_data.get(al)
            if data and len(data) > 0:
                track_data_map[track_idx] = bytes(data)
                has_any_data = True

        if not has_any_data:
            # Return empty section
            return Section.create_empty(section_type)

        section = Section(
            section_type=section_type,
            enabled=True,
            length_measures=4,  # Default, needs parsing
            tracks=[],
        )

        # Parse track data
        section.tracks = self._parse_tracks(track_data_map)

        # Store combined raw data for the section
        combined = bytearray()
        for track_idx in range(self.TRACKS_PER_SECTION):
            if track_idx in track_data_map:
                combined.extend(track_data_map[track_idx])
        section._raw_data = bytes(combined)

        return section

    def _parse_tracks(self, track_data_map: Dict[int, bytes]) -> List[Track]:
        """
        Parse track data from section dump.

        Args:
            track_data_map: Dict mapping track_idx (0-7) to decoded track data

        Returns:
            List of 8 Track objects
        """
        tracks = []

        # Create 8 tracks, using available data where present
        for i in range(self.TRACKS_PER_SECTION):
            has_data = i in track_data_map and len(track_data_map[i]) > 0
            track = Track(number=i + 1, enabled=has_data, settings=TrackSettings())
            if has_data:
                track._raw_data = track_data_map[i]
            tracks.append(track)

        return tracks

    @classmethod
    def can_read(cls, filepath: Union[str, Path]) -> bool:
        """
        Check if a file can be read as QY70 SysEx.

        Args:
            filepath: Path to check

        Returns:
            True if file appears to be valid QY70 SysEx
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return False

        try:
            with open(filepath, "rb") as f:
                header = f.read(16)

            # Check for SysEx start and Yamaha ID
            if len(header) < 4:
                return False

            return (
                header[0] == 0xF0  # SysEx start
                and header[1] == 0x43  # Yamaha
                and header[3] == 0x5F  # QY70 model ID
            )
        except Exception:
            return False


# QY70 section layout confirmed via SGT dump + hardware capture (Session 32).
# AL = section_index * 8 + track_index. Sections 0..5 match the on-device
# playback positions (Intro, Main A, Main B, Fill AB, Fill BA, Ending).
_QY70_SECTION_MAP: dict[int, SectionName] = {
    0: SectionName.INTRO,
    1: SectionName.MAIN_A,
    2: SectionName.MAIN_B,
    3: SectionName.FILL_AB,
    4: SectionName.FILL_BA,
    5: SectionName.ENDING,
}


# QY70 PATT OUT mapping verified 2026-04-23 via hardware playback capture.
# track_index 0..7 → MIDI channel 9..16 (0-indexed 8..15). The old
# `track_idx < 2 ? 9 : track_idx` logic produced wrong channels for
# tracks 2-7.
_QY70_TRACK_CHANNELS = [8, 9, 10, 11, 12, 13, 14, 15]


def parse_syx_to_udm(data: bytes) -> Device:
    """Parse QY70 .syx bulk dump data into a UDM Device.

    Delegates structural parsing to `SyxAnalyzer` (which already resolves
    tempo, section map, track channels, and voice confidence via the
    signature DB / class fallback) and translates the result into UDM.
    Sparse fields that the bulk does not carry (real XG Bank/LSB/Prog,
    CC volume/pan/sends) stay at Voice() / 100 / 64 / 40 / 0 defaults
    unless a later merge-capture fills them in.

    Raw bytes are preserved in `Device._raw_passthrough` so that
    `emit_udm_to_syx` and `/api/devices/{id}/syx-analysis` can re-read
    them byte-for-byte.

    Args:
        data: Raw .syx file contents.

    Returns:
        Device with model=QY70 containing one Pattern.

    Raises:
        ValueError: If data contains no valid QY70 bulk-dump messages.
    """
    from qymanager.analysis.syx_analyzer import SyxAnalyzer

    parser = SysExParser()
    messages = parser.parse_bytes(data)

    style_messages = [
        m for m in messages if m.is_style_data and m.decoded_data is not None
    ]
    if not style_messages:
        raise ValueError("No QY70 style-data bulk-dump messages found")

    section_data: dict[int, bytearray] = {}
    for msg in style_messages:
        al = msg.address_low
        if al not in section_data:
            section_data[al] = bytearray()
        if msg.decoded_data is not None:
            section_data[al].extend(msg.decoded_data)

    analysis = SyxAnalyzer().analyze_bytes(data, name="parse_syx_to_udm")

    pattern_name = analysis.pattern_name or ""
    if not pattern_name and 0x7F in section_data:
        header_bytes = bytes(section_data[0x7F])
        for start in range(min(len(header_bytes), 32)):
            chunk = header_bytes[start : start + 10]
            if all(0x20 <= b < 0x7F for b in chunk) and len(chunk) == 10:
                pattern_name = chunk.decode("ascii").rstrip()
                break

    time_sig_num, time_sig_den = analysis.time_signature or (4, 4)

    udm_pattern = UdmPattern(
        index=0,
        name=pattern_name[:10] if pattern_name else "",
        tempo_bpm=float(analysis.tempo) if analysis.tempo else 120.0,
        measures=4,
        time_sig=TimeSig(numerator=time_sig_num, denominator=time_sig_den),
    )

    # Per-track voice hints resolved by the analyzer (DB signature hits at
    # confidence 1.0 + class fallback). Keyed by track_index 0..7.
    track_voices: dict[int, Voice] = {}
    track_volumes: dict[int, int] = {}
    track_pans: dict[int, int] = {}
    track_revs: dict[int, int] = {}
    track_chos: dict[int, int] = {}
    for t in analysis.qy70_tracks:
        if not t.has_data:
            continue
        # Only trust DB-resolved voices: class fallback puts the
        # category name in voice_name but leaves msb/lsb/prog at 0.
        is_db_resolved = (
            t.voice_name
            and "(DB)" in t.voice_name
            and (t.bank_msb != 0 or t.bank_lsb != 0 or t.program != 0)
        )
        if is_db_resolved:
            track_voices[t.number - 1] = Voice(
                bank_msb=t.bank_msb & 0x7F,
                bank_lsb=t.bank_lsb & 0x7F,
                program=t.program & 0x7F,
            )
        track_volumes[t.number - 1] = t.volume
        track_pans[t.number - 1] = t.pan
        track_revs[t.number - 1] = t.reverb_send
        track_chos[t.number - 1] = t.chorus_send

    seen_section_indices: set[int] = set()
    for al in section_data:
        if al == 0x7F:
            continue
        seen_section_indices.add(al // 8)

    for sec_idx in sorted(seen_section_indices):
        section_name = _QY70_SECTION_MAP.get(sec_idx)
        if section_name is None:
            continue

        udm_tracks: list[PatternTrack] = []
        for track_idx in range(8):
            al = sec_idx * 8 + track_idx
            has_data = al in section_data and len(section_data[al]) > 0
            udm_tracks.append(
                PatternTrack(
                    midi_channel=_QY70_TRACK_CHANNELS[track_idx],
                    voice=track_voices.get(track_idx, Voice()),
                    mute=not has_data,
                    volume=track_volumes.get(track_idx, 100),
                    pan=track_pans.get(track_idx, 64),
                    reverb_send=track_revs.get(track_idx, 40),
                    chorus_send=track_chos.get(track_idx, 0),
                )
            )

        udm_pattern.sections[section_name] = UdmSection(
            name=section_name,
            tracks=udm_tracks,
            enabled=True,
        )

    device = Device(
        model=DeviceModel.QY70,
        patterns=[udm_pattern],
        source_format="syx",
        _raw_passthrough=data,
    )

    # Populate phrases_user from the sparse decoder when tracks clear the
    # plausibility guard (≥ 60 %). Dense factory styles collapse below
    # this threshold and stay out of phrases_user to avoid ghost notes.
    from qymanager.formats.qy70.encoder_sparse import (
        decode_sparse_track,
        sparse_track_plausibility,
    )

    phrase_index = 0
    for al in sorted(section_data):
        if al == 0x7F:
            continue
        td = bytes(section_data[al])
        if len(td) < 48:
            continue
        events = decode_sparse_track(td)
        if not events or sparse_track_plausibility(events) < 0.6:
            continue
        track_idx = al & 0x7
        sec_idx = al >> 3
        sec_name = _QY70_SECTION_MAP.get(sec_idx)
        section_label = sec_name.value if sec_name else f"sec{sec_idx}"
        track_label = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"][track_idx]
        channel = _QY70_TRACK_CHANNELS[track_idx]
        midi_events = [
            MidiEvent(
                tick=int(ev["tick"]),
                channel=int(channel),
                kind=EventKind.NOTE_ON,
                data1=int(ev["note"]),
                data2=int(ev["velocity"]),
            )
            for ev in events
            if not ev.get("ctrl")
        ]
        if not midi_events:
            continue
        device.phrases_user.append(
            Phrase(
                index=phrase_index,
                name=f"{section_label}·{track_label}",
                category=PhraseCategory.DA,
                events=midi_events,
            )
        )
        phrase_index += 1

    return device
