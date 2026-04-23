"""Core types and enums for the Unified Data Model."""

from dataclasses import dataclass
from enum import Enum


class DeviceModel(str, Enum):
    QY70 = "qy70"
    QY700 = "qy700"


class MidiSync(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    AUTO = "auto"


class MonoPoly(str, Enum):
    MONO = "mono"
    POLY = "poly"


class KeyOnAssign(str, Enum):
    SINGLE = "single"
    MULTI = "multi"


class NoteOffMode(str, Enum):
    STANDARD = "standard"
    HOLD = "hold"


class SectionName(str, Enum):
    INTRO = "Intro"
    MAIN_A = "Main_A"
    MAIN_B = "Main_B"
    MAIN_C = "Main_C"
    MAIN_D = "Main_D"
    FILL_AA = "Fill_AA"
    FILL_BB = "Fill_BB"
    FILL_CC = "Fill_CC"
    FILL_DD = "Fill_DD"
    FILL_AB = "Fill_AB"
    FILL_BA = "Fill_BA"
    ENDING = "Ending"


class PhraseCategory(str, Enum):
    DA = "Da"
    DB = "Db"
    FA = "Fa"
    FB = "Fb"
    PC = "PC"
    BA = "Ba"
    BB = "Bb"
    GA = "Ga"
    GB = "Gb"
    GR = "GR"
    KC = "KC"
    KR = "KR"
    PD = "PD"
    BR = "BR"
    SE = "SE"


class PhraseType(str, Enum):
    BYPASS = "Bypass"
    BASS = "Bass"
    CHORD1 = "Chord1"
    CHORD2 = "Chord2"
    PARALLEL = "Parallel"


class SongTrackKind(str, Enum):
    SEQ = "Seq"
    CHORD = "Chord"
    TEMPO = "Tempo"
    SCENE = "Scene"
    PATTERN = "Pattern"
    CONTROL = "Control"
    BEAT = "Beat"
    CLICK = "Click"
    META = "Meta"


class EventKind(str, Enum):
    NOTE_ON = "NoteOn"
    NOTE_OFF = "NoteOff"
    CC = "CC"
    PROG_CHANGE = "ProgChange"
    PB = "PB"
    NRPN = "NRPN"
    SYSEX = "SysEx"


class TransposeRule(str, Enum):
    BYPASS = "Bypass"
    BASS = "Bass"
    CHORD1 = "Chord1"
    CHORD2 = "Chord2"
    PARALLEL = "Parallel"


@dataclass(frozen=True)
class TimeSig:
    numerator: int = 4
    denominator: int = 4

    def __post_init__(self) -> None:
        if self.numerator < 1 or self.numerator > 32:
            raise ValueError(f"numerator must be 1-32, got {self.numerator}")
        if self.denominator not in (1, 2, 4, 8, 16, 32):
            raise ValueError(f"denominator must be power-of-2, got {self.denominator}")

    @property
    def beats_per_measure(self) -> int:
        return self.numerator

    @property
    def ticks_per_beat(self) -> int:
        return (480 * 4) // self.denominator

    @property
    def ticks_per_measure(self) -> int:
        return self.numerator * self.ticks_per_beat
