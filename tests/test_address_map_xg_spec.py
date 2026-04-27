"""Regression tests: address_map AL values match the XG System Level 1 spec.

Cross-references wiki/xg-multi-part.md and wiki/xg-drum-setup.md.
"""

import pytest

from qymanager.editor.address_map import resolve_address


class TestMultiPartALSpec:
    """Every Multi Part field resolves to the correct (AH=0x08, AM=part, AL) per XG spec."""

    @pytest.mark.parametrize(
        "field, expected_al",
        [
            ("element_reserve", 0x00),
            ("voice.bank_msb", 0x01),
            ("voice.bank_lsb", 0x02),
            ("voice.program", 0x03),
            ("rx_channel", 0x04),
            ("mono_poly", 0x05),
            ("key_on_assign", 0x06),
            ("part_mode", 0x07),
            ("note_shift", 0x08),
            ("detune", 0x09),
            ("volume", 0x0B),
            ("velocity_sense_depth", 0x0C),
            ("velocity_sense_offset", 0x0D),
            ("pan", 0x0E),
            ("note_limit_low", 0x0F),
            ("note_limit_high", 0x10),
            ("dry_level", 0x11),
            ("chorus_send", 0x12),
            ("reverb_send", 0x13),
            ("variation_send", 0x14),
            ("vibrato_rate", 0x15),
            ("vibrato_depth", 0x16),
            ("vibrato_delay", 0x17),
            ("cutoff", 0x18),
            ("resonance", 0x19),
            ("eg_attack", 0x1A),
            ("eg_decay", 0x1B),
            ("eg_release", 0x1C),
            ("mw_pitch_control", 0x1D),
            ("mw_filter_control", 0x1E),
            ("mw_amplitude_control", 0x1F),
            ("mw_lfo_pitch_depth", 0x20),
            ("mw_lfo_filter_depth", 0x21),
            ("mw_lfo_amplitude_depth", 0x22),
            ("bend_pitch", 0x23),
            ("bend_filter_control", 0x24),
            ("bend_amplitude_control", 0x25),
            ("bend_lfo_pitch_depth", 0x26),
            ("bend_lfo_filter_depth", 0x27),
            ("bend_lfo_amplitude_depth", 0x28),
            ("rx_pitch_bend", 0x30),
            ("rx_channel_aftertouch", 0x31),
            ("rx_program_change", 0x32),
            ("rx_control_change", 0x33),
            ("rx_poly_aftertouch", 0x34),
            ("rx_note_messages", 0x35),
            ("rx_rpn", 0x36),
            ("rx_nrpn", 0x37),
            ("rx_modulation", 0x38),
            ("rx_volume", 0x39),
            ("rx_pan", 0x3A),
            ("rx_expression", 0x3B),
            ("rx_hold_pedal", 0x3C),
            ("rx_portamento", 0x3D),
            ("rx_sostenuto", 0x3E),
            ("rx_soft_pedal", 0x3F),
            ("rx_bank_select", 0x40),
            ("scale_tuning_c", 0x41),
            ("scale_tuning_cs", 0x42),
            ("scale_tuning_b", 0x4C),
            ("cat_pitch_control", 0x4D),
            ("cat_lfo_amplitude_depth", 0x52),
            ("pat_pitch_control", 0x53),
            ("pat_lfo_amplitude_depth", 0x58),
            ("ac1_cc_number", 0x59),
            ("ac1_lfo_amplitude_depth", 0x5F),
            ("ac2_cc_number", 0x60),
            ("ac2_lfo_amplitude_depth", 0x66),
            ("portamento_switch", 0x67),
            ("portamento_time", 0x68),
            ("pitch_eg_initial_level", 0x69),
            ("pitch_eg_attack_time", 0x6A),
            ("pitch_eg_release_level", 0x6B),
            ("pitch_eg_release_time", 0x6C),
            ("velocity_limit_low", 0x6D),
            ("velocity_limit_high", 0x6E),
        ],
    )
    def test_multi_part_al(self, field, expected_al):
        result = resolve_address(f"multi_part[0].{field}")
        assert result is not None, f"field {field} not mapped"
        ah, am, al = result
        assert ah == 0x08
        assert am == 0
        assert al == expected_al, f"{field}: expected AL=0x{expected_al:02X}, got 0x{al:02X}"

    def test_cutoff_part3(self):
        assert resolve_address("multi_part[3].cutoff") == (0x08, 3, 0x18)

    def test_no_same_note_number_key(self):
        assert resolve_address("multi_part[0].same_note_number_key") is None


class TestDrumNoteALSpec:
    """Drum note fields resolve to the correct AL per XG drum setup spec."""

    @pytest.mark.parametrize(
        "field, expected_al",
        [
            ("pitch_coarse", 0x00),
            ("pitch_fine", 0x01),
            ("level", 0x02),
            ("alt_group", 0x03),
            ("pan", 0x04),
            ("reverb_send", 0x05),
            ("chorus_send", 0x06),
            ("variation_send", 0x07),
            ("key_assign", 0x08),
            ("note_off_mode", 0x09),
            ("filter_cutoff", 0x0B),
            ("filter_resonance", 0x0C),
            ("eg_attack", 0x0D),
            ("eg_decay1", 0x0E),
            ("eg_decay2", 0x0F),
        ],
    )
    def test_drum_note_al(self, field, expected_al):
        result = resolve_address(f"drum_setup[0].notes[36].{field}")
        assert result is not None, f"field {field} not mapped"
        ah, am, al = result
        assert ah == 0x30
        assert am == 36
        assert al == expected_al, f"{field}: expected AL=0x{expected_al:02X}, got 0x{al:02X}"
