"""Unit tests for UDM schema: validation, defaults, serialization."""

import pytest

from qymanager.model import (
    DeviceModel,
    EventKind,
    PhraseType,
    SectionName,
    TimeSig,
    TransposeRule,
    Voice,
    ChordEntry,
    ChordTrack,
    Device,
    DrumNote,
    DrumSetup,
    Effects,
    FingeredZone,
    GrooveStep,
    GrooveTemplate,
    MidiEvent,
    MultiPart,
    Pattern,
    PatternTrack,
    Phrase,
    PhraseCategory,
    ReverbBlock,
    Section,
    Song,
    SongTrack,
    System,
    UtilityFlags,
    VariationBlock,
)
from qymanager.model.types import MidiSync
from qymanager.model.serialization import device_to_json, udm_to_dict, validate_device


class TestTimeSig:
    def test_defaults(self):
        ts = TimeSig()
        assert ts.numerator == 4
        assert ts.denominator == 4

    def test_valid(self):
        ts = TimeSig(3, 4)
        assert ts.beats_per_measure == 3
        assert ts.ticks_per_beat == 480
        assert ts.ticks_per_measure == 1440

    def test_invalid_numerator(self):
        with pytest.raises(ValueError):
            TimeSig(0, 4)

    def test_invalid_denominator(self):
        with pytest.raises(ValueError):
            TimeSig(4, 3)

    def test_frozen(self):
        ts = TimeSig(4, 4)
        with pytest.raises(AttributeError):
            ts.numerator = 3


class TestVoice:
    def test_defaults(self):
        v = Voice()
        assert v.bank_msb == 0
        assert v.bank_lsb == 0
        assert v.program == 0
        assert not v.is_drum

    def test_drum_kit(self):
        v = Voice(bank_msb=127, program=0)
        assert v.is_drum

    def test_invalid_bank_msb(self):
        with pytest.raises(ValueError):
            Voice(bank_msb=128)

    def test_invalid_program(self):
        with pytest.raises(ValueError):
            Voice(program=-1)


class TestMidiEvent:
    def test_defaults(self):
        e = MidiEvent()
        assert e.tick == 0
        assert e.kind == EventKind.NOTE_ON
        assert e.is_note

    def test_note_properties(self):
        e = MidiEvent(tick=480, channel=0, kind=EventKind.NOTE_ON, data1=60, data2=100)
        assert e.note == 60
        assert e.velocity == 100

    def test_invalid_channel(self):
        with pytest.raises(ValueError):
            MidiEvent(channel=16)

    def test_invalid_tick(self):
        with pytest.raises(ValueError):
            MidiEvent(tick=-1)


class TestSystem:
    def test_defaults(self):
        s = System()
        assert s.master_tune == 0
        assert s.master_volume == 100
        assert s.midi_sync == MidiSync.INTERNAL
        assert s.device_id == 0

    def test_valid_range(self):
        s = System(master_tune=-100, master_volume=127, transpose=24, device_id=15)
        assert len(s.validate()) == 0

    def test_invalid_master_tune(self):
        s = System(master_tune=101)
        errs = s.validate()
        assert len(errs) == 1
        assert "master_tune" in errs[0]

    def test_invalid_transpose(self):
        s = System(transpose=25)
        errs = s.validate()
        assert len(errs) == 1

    def test_invalid_device_id(self):
        s = System(device_id=16)
        errs = s.validate()
        assert len(errs) == 1


class TestMultiPart:
    def test_defaults(self):
        mp = MultiPart()
        assert mp.volume == 100
        assert mp.pan == 64
        assert mp.voice == Voice()

    def test_valid(self):
        mp = MultiPart(part_index=15, rx_channel=10)
        assert len(mp.validate()) == 0

    def test_invalid_part_index(self):
        mp = MultiPart(part_index=32)
        errs = mp.validate()
        assert len(errs) == 1

    def test_invalid_volume(self):
        mp = MultiPart(volume=128)
        errs = mp.validate()
        assert len(errs) == 1

    def test_invalid_cutoff(self):
        mp = MultiPart(cutoff=64)
        errs = mp.validate()
        assert len(errs) == 1


class TestDrumSetup:
    def test_defaults(self):
        ds = DrumSetup()
        assert ds.kit_index == 0
        assert ds.notes == {}

    def test_valid_note(self):
        dn = DrumNote(level=100, pan=64)
        ds = DrumSetup(kit_index=0, notes={36: dn})
        assert len(ds.validate()) == 0

    def test_invalid_note_key(self):
        ds = DrumSetup(notes={5: DrumNote()})
        errs = ds.validate()
        assert any("note key" in e for e in errs)


class TestEffects:
    def test_defaults(self):
        fx = Effects()
        assert fx.reverb.type_code == 0
        assert fx.chorus.type_code == 0
        assert fx.variation is None

    def test_qy700_with_variation(self):
        fx = Effects(variation=VariationBlock())
        assert len(fx.validate()) == 0

    def test_invalid_reverb_type(self):
        fx = Effects(reverb=ReverbBlock(type_code=11))
        errs = fx.validate()
        assert len(errs) == 1


class TestPatternTrack:
    def test_defaults(self):
        pt = PatternTrack()
        assert pt.midi_channel == 0
        assert pt.transpose_rule == TransposeRule.BYPASS
        assert pt.voice == Voice()

    def test_invalid_channel(self):
        pt = PatternTrack(midi_channel=16)
        assert len(pt.validate()) == 1


class TestSection:
    def test_defaults(self):
        s = Section()
        assert s.name == SectionName.MAIN_A
        assert s.enabled

    def test_with_tracks(self):
        tracks = [PatternTrack(), PatternTrack(volume=80)]
        s = Section(name=SectionName.MAIN_B, tracks=tracks)
        assert len(s.tracks) == 2


class TestChordEntry:
    def test_defaults(self):
        ce = ChordEntry()
        assert ce.root == 0
        assert ce.root_name == "C"
        assert ce.chord_type_name == "MAJ"

    def test_invalid_root(self):
        with pytest.raises(ValueError):
            ChordEntry(root=12)

    def test_minor_chord(self):
        ce = ChordEntry(root=9, chord_type=1)
        assert ce.root_name == "A"
        assert ce.chord_type_name == "MIN"


class TestPattern:
    def test_defaults(self):
        p = Pattern()
        assert p.tempo_bpm == 120.0
        assert p.measures == 4
        assert p.time_sig == TimeSig()
        assert isinstance(p.chord_track, ChordTrack)

    def test_valid(self):
        p = Pattern(tempo_bpm=140.0, measures=8, name="TEST")
        assert len(p.validate()) == 0

    def test_invalid_tempo(self):
        p = Pattern(tempo_bpm=10.0)
        errs = p.validate()
        assert any("tempo_bpm" in e for e in errs)

    def test_name_too_long(self):
        p = Pattern(name="ABCDEFGHIJK")
        errs = p.validate()
        assert any("name too long" in e for e in errs)


class TestPhrase:
    def test_defaults(self):
        ph = Phrase()
        assert ph.category == PhraseCategory.DA
        assert ph.phrase_type == PhraseType.BYPASS
        assert ph.note_count == 0

    def test_with_events(self):
        events = [
            MidiEvent(tick=0, kind=EventKind.NOTE_ON, data1=60, data2=100),
            MidiEvent(tick=480, kind=EventKind.NOTE_OFF, data1=60, data2=0),
        ]
        ph = Phrase(events=events)
        assert ph.note_count == 1


class TestGrooveTemplate:
    def test_defaults(self):
        gt = GrooveTemplate()
        assert len(gt.steps) == 16
        assert all(s.timing_offset == 100 for s in gt.steps)

    def test_valid(self):
        gt = GrooveTemplate(steps=[GrooveStep() for _ in range(16)])
        assert len(gt.validate()) == 0

    def test_wrong_step_count(self):
        gt = GrooveTemplate(steps=[GrooveStep()])
        errs = gt.validate()
        assert any("16 steps" in e for e in errs)


class TestDevice:
    def test_qy70_defaults(self):
        d = Device(model=DeviceModel.QY70)
        assert d.is_qy70
        assert not d.is_qy700
        assert d.max_parts == 16
        assert d.max_sections == 6

    def test_qy700_defaults(self):
        d = Device(model=DeviceModel.QY700)
        assert d.is_qy700
        assert d.max_parts == 32
        assert d.max_sections == 8

    def test_empty_validate(self):
        d = Device()
        assert len(d.validate()) == 0

    def test_validate_cascades(self):
        d = Device(system=System(master_tune=200))
        errs = d.validate()
        assert len(errs) == 1
        assert "master_tune" in errs[0]


class TestSerialization:
    def test_device_to_json(self):
        d = Device(model=DeviceModel.QY70, system=System(master_volume=80))
        json_str = device_to_json(d)
        assert '"model": "qy70"' in json_str
        assert '"master_volume": 80' in json_str

    def test_udm_to_dict_enum(self):
        d = udm_to_dict(MidiSync.INTERNAL)
        assert d == "internal"

    def test_udm_to_dict_time_sig(self):
        d = udm_to_dict(TimeSig(3, 4))
        assert d == {"numerator": 3, "denominator": 4}

    def test_udm_to_dict_device(self):
        d = Device(model=DeviceModel.QY700)
        result = udm_to_dict(d)
        assert result["model"] == "qy700"
        assert "system" in result
        assert "_raw_passthrough" not in result

    def test_validate_device_function(self):
        d = Device(system=System(transpose=99))
        errs = validate_device(d)
        assert len(errs) == 1


class TestSong:
    def test_defaults(self):
        s = Song()
        assert s.tempo_bpm == 120.0
        assert len(s.validate()) == 0

    def test_with_tracks(self):
        st = SongTrack(index=0)
        s = Song(tracks=[st])
        assert len(s.tracks) == 1


class TestFingeredZone:
    def test_defaults(self):
        fz = FingeredZone()
        assert len(fz.validate()) == 0

    def test_invalid_range(self):
        fz = FingeredZone(low_note=80, high_note=60)
        errs = fz.validate()
        assert len(errs) == 1


class TestUtilityFlags:
    def test_defaults(self):
        uf = UtilityFlags()
        assert uf.click_velocity == 100
        assert len(uf.validate()) == 0

    def test_invalid_velocity(self):
        uf = UtilityFlags(click_velocity=128)
        errs = uf.validate()
        assert len(errs) == 1


class TestEnums:
    def test_section_names(self):
        # QY700 MAIN_A..D + FILL_AA..DD (8) plus QY70-specific INTRO,
        # FILL_AB, FILL_BA, ENDING (4) = 12.
        assert len(SectionName) == 12

    def test_phrase_categories(self):
        assert len(PhraseCategory) == 15

    def test_phrase_types(self):
        assert len(PhraseType) == 5

    def test_chord_types_count(self):
        from qymanager.model.pattern import CHORD_TYPES

        assert len(CHORD_TYPES) == 28

    def test_chord_roots_count(self):
        from qymanager.model.pattern import CHORD_ROOTS

        assert len(CHORD_ROOTS) == 12

    def test_event_kinds(self):
        assert EventKind.NOTE_ON.value == "NoteOn"

    def test_transpose_rules(self):
        assert len(TransposeRule) == 5
