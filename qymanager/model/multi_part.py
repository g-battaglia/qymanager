"""Multi Part parameters."""

from dataclasses import dataclass

from qymanager.model.types import MonoPoly, KeyOnAssign
from qymanager.model.voice import Voice


@dataclass
class MultiPart:
    part_index: int = 0
    rx_channel: int = 0
    voice: Voice = None  # type: ignore[assignment]
    volume: int = 100
    pan: int = 64
    reverb_send: int = 40
    chorus_send: int = 0
    variation_send: int = 0
    cutoff: int = 0
    resonance: int = 0
    eg_attack: int = 0
    eg_decay: int = 0
    eg_release: int = 0
    mono_poly: MonoPoly = MonoPoly.POLY
    key_on_assign: KeyOnAssign = KeyOnAssign.MULTI
    dry_level: int = 0x40
    bend_pitch: int = 2

    # AL 0x00
    element_reserve: int = 2
    # AL 0x07
    part_mode: int = 0
    # AL 0x08 (-24..+24)
    note_shift: int = 0
    # AL 0x09+0x0A (2-byte, -128..+127 = -12.8..+12.7 Hz)
    detune: int = 0
    # AL 0x0C-0x0D
    velocity_sense_depth: int = 64
    velocity_sense_offset: int = 64
    # AL 0x0F-0x10
    note_limit_low: int = 0
    note_limit_high: int = 127
    # AL 0x15-0x17 (Vibrato, -64..+63)
    vibrato_rate: int = 0
    vibrato_depth: int = 0
    vibrato_delay: int = 0
    # AL 0x1D-0x22 (MW Control)
    mw_pitch_control: int = 0
    mw_filter_control: int = 0
    mw_amplitude_control: int = 0
    mw_lfo_pitch_depth: int = 10
    mw_lfo_filter_depth: int = 0
    mw_lfo_amplitude_depth: int = 0
    # AL 0x24-0x28 (Bend extended)
    bend_filter_control: int = 0
    bend_amplitude_control: int = 0
    bend_lfo_pitch_depth: int = 0
    bend_lfo_filter_depth: int = 0
    bend_lfo_amplitude_depth: int = 0

    # Block 2: Receive Switches (AL 0x30-0x40)
    rx_pitch_bend: bool = True
    rx_channel_aftertouch: bool = True
    rx_program_change: bool = True
    rx_control_change: bool = True
    rx_poly_aftertouch: bool = True
    rx_note_messages: bool = True
    rx_rpn: bool = True
    rx_nrpn: bool = True
    rx_modulation: bool = True
    rx_volume: bool = True
    rx_pan: bool = True
    rx_expression: bool = True
    rx_hold_pedal: bool = True
    rx_portamento: bool = True
    rx_sostenuto: bool = True
    rx_soft_pedal: bool = True
    rx_bank_select: bool = True

    # Block 3: Scale Tuning (AL 0x41-0x4C, -64..+63 cent per note)
    scale_tuning_c: int = 0
    scale_tuning_cs: int = 0
    scale_tuning_d: int = 0
    scale_tuning_ds: int = 0
    scale_tuning_e: int = 0
    scale_tuning_f: int = 0
    scale_tuning_fs: int = 0
    scale_tuning_g: int = 0
    scale_tuning_gs: int = 0
    scale_tuning_a: int = 0
    scale_tuning_as: int = 0
    scale_tuning_b: int = 0

    # Block 4: CAT Control (AL 0x4D-0x52)
    cat_pitch_control: int = 0
    cat_filter_control: int = 0
    cat_amplitude_control: int = 0
    cat_lfo_pitch_depth: int = 0
    cat_lfo_filter_depth: int = 0
    cat_lfo_amplitude_depth: int = 0

    # Block 5: PAT Control (AL 0x53-0x58)
    pat_pitch_control: int = 0
    pat_filter_control: int = 0
    pat_amplitude_control: int = 0
    pat_lfo_pitch_depth: int = 0
    pat_lfo_filter_depth: int = 0
    pat_lfo_amplitude_depth: int = 0

    # Block 6: AC1/AC2 (AL 0x59-0x66)
    ac1_cc_number: int = 16
    ac1_pitch_control: int = 0
    ac1_filter_control: int = 0
    ac1_amplitude_control: int = 0
    ac1_lfo_pitch_depth: int = 0
    ac1_lfo_filter_depth: int = 0
    ac1_lfo_amplitude_depth: int = 0
    ac2_cc_number: int = 17
    ac2_pitch_control: int = 0
    ac2_filter_control: int = 0
    ac2_amplitude_control: int = 0
    ac2_lfo_pitch_depth: int = 0
    ac2_lfo_filter_depth: int = 0
    ac2_lfo_amplitude_depth: int = 0

    # Block 7: Portamento & Pitch EG (AL 0x67-0x6E)
    portamento_switch: bool = False
    portamento_time: int = 0
    pitch_eg_initial_level: int = 0
    pitch_eg_attack_time: int = 0
    pitch_eg_release_level: int = 0
    pitch_eg_release_time: int = 0
    velocity_limit_low: int = 1
    velocity_limit_high: int = 127

    def __post_init__(self) -> None:
        if self.voice is None:
            object.__setattr__(self, "voice", Voice())

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0 <= self.part_index <= 31:
            errors.append(f"part_index must be 0-31, got {self.part_index}")
        if not 0 <= self.rx_channel <= 16:
            errors.append(f"rx_channel must be 0-16, got {self.rx_channel}")
        for name, val, lo, hi in [
            ("volume", self.volume, 0, 127),
            ("pan", self.pan, 0, 127),
            ("reverb_send", self.reverb_send, 0, 127),
            ("chorus_send", self.chorus_send, 0, 127),
            ("variation_send", self.variation_send, 0, 127),
            ("dry_level", self.dry_level, 0, 127),
            ("bend_pitch", self.bend_pitch, 0, 24),
            ("element_reserve", self.element_reserve, 0, 32),
            ("part_mode", self.part_mode, 0, 3),
            ("velocity_sense_depth", self.velocity_sense_depth, 0, 127),
            ("velocity_sense_offset", self.velocity_sense_offset, 0, 127),
            ("note_limit_low", self.note_limit_low, 0, 127),
            ("note_limit_high", self.note_limit_high, 0, 127),
            ("mw_lfo_pitch_depth", self.mw_lfo_pitch_depth, 0, 127),
            ("mw_lfo_filter_depth", self.mw_lfo_filter_depth, 0, 127),
            ("mw_lfo_amplitude_depth", self.mw_lfo_amplitude_depth, 0, 127),
            ("ac1_cc_number", self.ac1_cc_number, 0, 95),
            ("ac2_cc_number", self.ac2_cc_number, 0, 95),
            ("portamento_time", self.portamento_time, 0, 127),
            ("velocity_limit_low", self.velocity_limit_low, 1, 127),
            ("velocity_limit_high", self.velocity_limit_high, 1, 127),
        ]:
            if not lo <= val <= hi:
                errors.append(f"{name} must be {lo}-{hi}, got {val}")
        for name, val in [
            ("cutoff", self.cutoff),
            ("resonance", self.resonance),
            ("eg_attack", self.eg_attack),
            ("eg_decay", self.eg_decay),
            ("eg_release", self.eg_release),
            ("vibrato_rate", self.vibrato_rate),
            ("vibrato_depth", self.vibrato_depth),
            ("vibrato_delay", self.vibrato_delay),
            ("mw_filter_control", self.mw_filter_control),
            ("mw_amplitude_control", self.mw_amplitude_control),
            ("bend_filter_control", self.bend_filter_control),
            ("bend_amplitude_control", self.bend_amplitude_control),
            ("bend_lfo_pitch_depth", self.bend_lfo_pitch_depth),
            ("bend_lfo_filter_depth", self.bend_lfo_filter_depth),
            ("bend_lfo_amplitude_depth", self.bend_lfo_amplitude_depth),
            ("cat_filter_control", self.cat_filter_control),
            ("cat_amplitude_control", self.cat_amplitude_control),
            ("pat_filter_control", self.pat_filter_control),
            ("pat_amplitude_control", self.pat_amplitude_control),
            ("ac1_filter_control", self.ac1_filter_control),
            ("ac1_amplitude_control", self.ac1_amplitude_control),
            ("ac2_filter_control", self.ac2_filter_control),
            ("ac2_amplitude_control", self.ac2_amplitude_control),
            ("pitch_eg_initial_level", self.pitch_eg_initial_level),
            ("pitch_eg_attack_time", self.pitch_eg_attack_time),
            ("pitch_eg_release_level", self.pitch_eg_release_level),
            ("pitch_eg_release_time", self.pitch_eg_release_time),
        ]:
            if not -64 <= val <= 63:
                errors.append(f"{name} must be -64..+63, got {val}")
        for name, val in [
            ("note_shift", self.note_shift),
            ("mw_pitch_control", self.mw_pitch_control),
            ("cat_pitch_control", self.cat_pitch_control),
            ("pat_pitch_control", self.pat_pitch_control),
            ("ac1_pitch_control", self.ac1_pitch_control),
            ("ac2_pitch_control", self.ac2_pitch_control),
        ]:
            if not -24 <= val <= 24:
                errors.append(f"{name} must be -24..+24, got {val}")
        for name, val in [
            ("scale_tuning_c", self.scale_tuning_c),
            ("scale_tuning_cs", self.scale_tuning_cs),
            ("scale_tuning_d", self.scale_tuning_d),
            ("scale_tuning_ds", self.scale_tuning_ds),
            ("scale_tuning_e", self.scale_tuning_e),
            ("scale_tuning_f", self.scale_tuning_f),
            ("scale_tuning_fs", self.scale_tuning_fs),
            ("scale_tuning_g", self.scale_tuning_g),
            ("scale_tuning_gs", self.scale_tuning_gs),
            ("scale_tuning_a", self.scale_tuning_a),
            ("scale_tuning_as", self.scale_tuning_as),
            ("scale_tuning_b", self.scale_tuning_b),
        ]:
            if not -64 <= val <= 63:
                errors.append(f"{name} must be -64..+63, got {val}")
        return errors
