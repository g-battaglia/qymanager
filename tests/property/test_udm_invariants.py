"""Property tests: UDM invariants + editor encoding roundtrip (F11)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from qymanager.editor.address_map import build_xg_parameter_change
from qymanager.editor.ops import set_field
from qymanager.editor.schema import encode_xg, validate
from qymanager.formats.xg_bulk import parse_xg_bulk_to_udm
from qymanager.model import Device, DeviceModel


midi_byte = st.integers(min_value=0, max_value=127)
device_number = st.integers(min_value=0, max_value=15)
part_index = st.integers(min_value=0, max_value=15)
transpose_val = st.integers(min_value=-24, max_value=24)


@given(volume=midi_byte)
def test_master_volume_applied_via_xg(volume: int) -> None:
    msg = build_xg_parameter_change(0x00, 0x00, 0x04, volume)
    device = parse_xg_bulk_to_udm(msg)
    assert device.system.master_volume == volume


@given(raw=midi_byte)
def test_transpose_offset_roundtrip(raw: int) -> None:
    msg = build_xg_parameter_change(0x00, 0x00, 0x06, raw)
    device = parse_xg_bulk_to_udm(msg)
    assert device.system.transpose == raw - 64


@given(part=part_index, volume=midi_byte)
def test_multi_part_volume(part: int, volume: int) -> None:
    msg = build_xg_parameter_change(0x08, part, 0x0B, volume)
    device = parse_xg_bulk_to_udm(msg)
    assert device.multi_part[part].volume == volume


@given(part=part_index, msb=midi_byte, lsb=midi_byte, prog=midi_byte)
def test_bank_triplet(part: int, msb: int, lsb: int, prog: int) -> None:
    stream = b"".join(
        [
            build_xg_parameter_change(0x08, part, 0x01, msb),
            build_xg_parameter_change(0x08, part, 0x02, lsb),
            build_xg_parameter_change(0x08, part, 0x03, prog),
        ]
    )
    device = parse_xg_bulk_to_udm(stream)
    voice = device.multi_part[part].voice
    assert voice.bank_msb == msb and voice.bank_lsb == lsb and voice.program == prog


@given(transpose=transpose_val)
def test_encode_xg_transpose_is_7bit(transpose: int) -> None:
    byte = encode_xg("system.transpose", transpose)
    assert 0 <= byte <= 127


@given(value=midi_byte, dev=device_number)
def test_build_xg_parameter_change_shape(value: int, dev: int) -> None:
    msg = build_xg_parameter_change(0x00, 0x00, 0x04, value, device=dev)
    assert len(msg) == 9
    assert msg[0] == 0xF0 and msg[-1] == 0xF7
    assert msg[2] == (0x10 | dev) and msg[3] == 0x4C
    assert msg[7] == value


@given(volume=midi_byte)
def test_set_field_stores_value(volume: int) -> None:
    device = Device(model=DeviceModel.QY70)
    set_field(device, "system.master_volume", volume)
    assert device.system.master_volume == volume
    assert device.validate() == []


@given(transpose=transpose_val)
def test_validate_schema_passes_in_range(transpose: int) -> None:
    assert validate("system.transpose", transpose) == transpose


@settings(max_examples=50)
@given(
    parts=st.lists(
        st.tuples(part_index, midi_byte, midi_byte, midi_byte),
        min_size=1,
        max_size=8,
    )
)
def test_batch_bank_program_preserves_last_write(parts):
    stream = b""
    for pidx, msb, lsb, prog in parts:
        stream += build_xg_parameter_change(0x08, pidx, 0x01, msb)
        stream += build_xg_parameter_change(0x08, pidx, 0x02, lsb)
        stream += build_xg_parameter_change(0x08, pidx, 0x03, prog)
    device = parse_xg_bulk_to_udm(stream)
    # For each part index, the LAST write wins
    last_by_part: dict[int, tuple[int, int, int]] = {}
    for pidx, msb, lsb, prog in parts:
        last_by_part[pidx] = (msb, lsb, prog)
    for pidx, (msb, lsb, prog) in last_by_part.items():
        v = device.multi_part[pidx].voice
        assert v.bank_msb == msb and v.bank_lsb == lsb and v.program == prog
