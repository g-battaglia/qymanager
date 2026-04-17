"""
QY700 Q7P file reader.

Reads .Q7P binary files and converts them to the common Pattern model (legacy)
or the Unified Data Model (UDM) Device.
"""

from pathlib import Path
from typing import Union

from qymanager.models.pattern import Pattern
from qymanager.models.section import Section, SectionType
from qymanager.models.track import Track, TrackSettings
from qymanager.formats.qy700.binary_parser import Q7PParser, Q7PHeader

from qymanager.model import (
    Device,
    DeviceModel,
    Pattern as UdmPattern,
    Section as UdmSection,
    PatternTrack,
    SectionName,
    TimeSig,
    Voice,
)
from qymanager.analysis.q7p_analyzer import Q7PAnalyzer

_Q7P_SECTION_ORDER: list[SectionName] = [
    SectionName.MAIN_A,
    SectionName.MAIN_B,
    SectionName.MAIN_C,
    SectionName.MAIN_D,
    SectionName.FILL_AA,
    SectionName.FILL_BB,
    SectionName.FILL_CC,
    SectionName.FILL_DD,
]


class QY700Reader:
    """
    Reader for QY700 Q7P pattern files.

    Parses .Q7P binary files and constructs Pattern objects.

    Example:
        pattern = QY700Reader.read("pattern.Q7P")
        print(f"Pattern: {pattern.name}, Tempo: {pattern.tempo}")
    """

    # Q7P section index to SectionType mapping
    SECTION_MAP = {
        0: SectionType.INTRO,
        1: SectionType.MAIN_A,
        2: SectionType.MAIN_B,
        3: SectionType.FILL_AB,
        4: SectionType.FILL_BA,
        5: SectionType.ENDING,
    }

    def __init__(self):
        self.parser = Q7PParser()
        self._raw_data: bytes = b""

    @classmethod
    def read(cls, filepath: Union[str, Path]) -> Pattern:
        """
        Read a Q7P file and return a Pattern.

        Args:
            filepath: Path to .Q7P file

        Returns:
            Parsed Pattern object
        """
        reader = cls()
        return reader.parse_file(filepath)

    def parse_file(self, filepath: Union[str, Path]) -> Pattern:
        """
        Parse a Q7P file.

        Args:
            filepath: Path to .Q7P file

        Returns:
            Parsed Pattern object
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            self._raw_data = f.read()

        return self.parse_bytes(self._raw_data)

    def parse_bytes(self, data: bytes) -> Pattern:
        """
        Parse Q7P data from bytes.

        Args:
            data: Raw Q7P file contents

        Returns:
            Parsed Pattern object
        """
        self._raw_data = data

        # Parse with binary parser
        header, sections = self.parser.parse_bytes(data)

        # Build pattern from parsed data
        pattern = self._build_pattern(header)
        pattern.source_format = "qy700"
        pattern._raw_data = data

        return pattern

    def _build_pattern(self, header: Q7PHeader) -> Pattern:
        """
        Build Pattern object from parsed data.

        Args:
            header: Parsed Q7P header

        Returns:
            Pattern object
        """
        pattern = Pattern()

        # Extract pattern name from template name area
        name = self.parser.get_template_name()
        if name:
            pattern.name = name.ljust(10)[:10]
        else:
            pattern.name = "PATTERN   "

        # Extract tempo
        pattern.settings.tempo = self.parser.get_tempo()

        # Pattern number
        pattern.number = header.pattern_number

        # Parse each section
        volumes = self.parser.get_track_volumes()
        channels = self.parser.get_channel_assignments()

        for idx, section_type in self.SECTION_MAP.items():
            section = self._build_section(idx, section_type, volumes, channels)
            pattern.sections[section_type] = section

        return pattern

    def _build_section(
        self, index: int, section_type: SectionType, volumes: list, channels: list
    ) -> Section:
        """
        Build a Section from parsed data.

        Args:
            index: Section index
            section_type: Type of section
            volumes: Volume values for tracks
            channels: Channel assignments

        Returns:
            Section object
        """
        section = Section(
            section_type=section_type,
            enabled=True,
            length_measures=4,  # Default
            tracks=[],
        )

        # Create 8 tracks
        for track_num in range(8):
            track = Track(
                number=track_num + 1,
                enabled=True,
                settings=TrackSettings(
                    channel=channels[track_num] if track_num < len(channels) else track_num + 1,
                    volume=volumes[track_num] if track_num < len(volumes) else 100,
                ),
            )
            section.tracks.append(track)

        return section

    @classmethod
    def can_read(cls, filepath: Union[str, Path]) -> bool:
        """
        Check if a file can be read as Q7P.

        Args:
            filepath: Path to check

        Returns:
            True if file appears to be valid Q7P
        """
        filepath = Path(filepath)

        if not filepath.exists():
            return False

        try:
            with open(filepath, "rb") as f:
                header = f.read(16)

            return header == b"YQ7PAT     V1.00"
        except Exception:
            return False

    @classmethod
    def get_file_info(cls, filepath: Union[str, Path]) -> dict:
        """
        Get basic information about a Q7P file without full parsing.

        Args:
            filepath: Path to .Q7P file

        Returns:
            Dictionary with file info
        """
        filepath = Path(filepath)

        with open(filepath, "rb") as f:
            data = f.read()

        info: dict[str, object] = {
            "valid": False,
            "size": len(data),
            "expected_size": 3072,
        }

        if len(data) >= 16:
            info["header"] = data[:16].decode("ascii", errors="replace")
            info["valid"] = data[:16] == b"YQ7PAT     V1.00"

        if len(data) >= 0x878:
            # Template name at offset 0x870
            name = data[0x870:0x87A]
            info["template_name"] = name.decode("ascii", errors="replace").rstrip()

        return info


def parse_q7p_to_udm(data: bytes) -> Device:
    """Parse Q7P binary data into a UDM Device.

    Uses Q7PAnalyzer for byte-level extraction, maps to UDM dataclasses.
    Stores raw bytes in Device._raw_passthrough for lossless roundtrip.

    Args:
        data: Raw Q7P file contents (3072 or 5120 bytes).

    Returns:
        Device with model=QY700 containing one Pattern.

    Raises:
        ValueError: If data is not a valid Q7P file.
    """
    if len(data) < 16 or data[:16] != b"YQ7PAT     V1.00":
        raise ValueError("Invalid Q7P header")

    analyzer = Q7PAnalyzer()
    analysis = analyzer.analyze_bytes(data)

    if not analysis.valid:
        raise ValueError("Q7P analysis failed: invalid file structure")

    ts_num, ts_den = analysis.time_signature
    pattern = UdmPattern(
        index=analysis.pattern_number,
        name=analysis.pattern_name[:10] if analysis.pattern_name else "",
        tempo_bpm=round(analysis.tempo, 1),
        measures=4,
        time_sig=TimeSig(numerator=ts_num, denominator=ts_den),
    )

    bank_msbs = _extract_voice_param(analyzer, "_get_bank_msb")
    bank_lsbs = _extract_voice_param(analyzer, "_get_bank_lsb")
    programs = _extract_voice_param(analyzer, "_get_programs")

    for sec_info in analysis.sections:
        if not sec_info.enabled:
            continue
        sec_idx = sec_info.index
        if sec_idx >= len(_Q7P_SECTION_ORDER):
            break

        section_name = _Q7P_SECTION_ORDER[sec_idx]
        udm_tracks: list[PatternTrack] = []

        num_tracks = min(len(sec_info.tracks), 16)
        for ti in range(num_tracks):
            trk = sec_info.tracks[ti]
            udm_tracks.append(
                PatternTrack(
                    midi_channel=max(0, min(15, trk.channel - 1)),
                    voice=Voice(
                        bank_msb=bank_msbs[ti] if ti < len(bank_msbs) else 0,
                        bank_lsb=bank_lsbs[ti] if ti < len(bank_lsbs) else 0,
                        program=programs[ti] if ti < len(programs) else 0,
                    ),
                    pan=trk.pan,
                    volume=trk.volume,
                    reverb_send=trk.reverb_send,
                    chorus_send=trk.chorus_send,
                )
            )

        pattern.sections[section_name] = UdmSection(
            name=section_name,
            tracks=udm_tracks,
            enabled=True,
        )

    device = Device(
        model=DeviceModel.QY700,
        patterns=[pattern],
        source_format="q7p",
        _raw_passthrough=data,
    )
    return device


def _extract_voice_param(analyzer: Q7PAnalyzer, method_name: str) -> list[int]:
    method = getattr(analyzer, method_name, None)
    if method and callable(method):
        result: list[int] = method()
        return result
    return [0] * 16
