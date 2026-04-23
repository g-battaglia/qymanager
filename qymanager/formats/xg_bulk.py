"""XG Parameter Change bulk stream ↔ UDM Device bridge.

Parses a stream of Yamaha XG SysEx Parameter-Change messages (Model ID
0x4C) into a UDM Device by applying each message to the relevant block:

- AH=0x00 (System)      → device.system
- AH=0x02 (Effects)     → device.effects.reverb / chorus / variation
- AH=0x08 (Multi Part)  → device.multi_part[AM] (auto-grown)
- AH=0x30/0x31 (Drum 1/2) → device.drum_setup[0/1].notes[AM]

Messages that don't match known XG addresses are preserved in
Device._raw_passthrough so that emit_udm_to_xg_bulk() can re-emit them
byte-identical.

Source of authority: wiki/xg-parameters.md, midi_tools/xg_param.py.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Union

from qymanager.model import (
    ChorusBlock,
    Device,
    DeviceModel,
    DrumNote,
    DrumSetup,
    Effects,
    MultiPart,
    ReverbBlock,
    System,
    VariationBlock,
    Voice,
)


AH_SYSTEM = 0x00
AH_EFFECT = 0x02
AH_MULTI_PART = 0x08
AH_DRUM_SETUP_1 = 0x30
AH_DRUM_SETUP_2 = 0x31


@dataclass
class XGRawMessage:
    """A single XG parameter-change message (for downstream re-emit)."""

    ah: int
    am: int
    al: int
    data: bytes
    raw: bytes


def _split_sysex(blob: bytes) -> list[bytes]:
    msgs: list[bytes] = []
    i = 0
    n = len(blob)
    while i < n:
        if blob[i] == 0xF0:
            j = i + 1
            while j < n and blob[j] != 0xF7:
                j += 1
            if j < n:
                msgs.append(bytes(blob[i : j + 1]))
                i = j + 1
            else:
                break
        else:
            i += 1
    return msgs


@dataclass
class ChannelEvent:
    """Running-status-aware channel event (CC / Program Change / Note etc.)."""

    channel: int  # 0..15
    status: int  # high nibble (0x80..0xE0)
    data1: int
    data2: int  # 0 when the status takes a single data byte


def _scan_channel_events(blob: bytes) -> list[ChannelEvent]:
    """Walk `blob` and yield channel events, skipping SysEx and realtime bytes.

    The QY70 XG PARM OUT stream (and capture JSONs that record it) transmit
    voice setup as plain channel events (`Bn 00 MSB`, `Bn 20 LSB`, `Cn PROG`,
    plus volume / pan / sends). These never become XG Parameter Change
    messages, so `_split_sysex` alone is not enough — we need to consume the
    interleaved channel bytes that live between SysEx frames.
    """
    events: list[ChannelEvent] = []
    i = 0
    n = len(blob)
    running_status: int = 0
    while i < n:
        byte = blob[i]
        if byte == 0xF0:
            while i < n and blob[i] != 0xF7:
                i += 1
            if i < n:
                i += 1  # consume F7
            running_status = 0
            continue
        if 0xF8 <= byte <= 0xFF:
            # Realtime / system common single-byte message — harmless.
            i += 1
            continue
        if 0xF1 <= byte <= 0xF7:
            # System Common (song pos/song sel/tune/F7 stray): consume the
            # payload conservatively. Accurate decoding is unnecessary here
            # because they carry no voice info.
            running_status = 0
            i += 1
            if byte == 0xF2:
                i += 2
            elif byte in (0xF1, 0xF3):
                i += 1
            continue

        if byte >= 0x80:
            status = byte
            i += 1
        elif running_status:
            status = running_status
        else:
            # Stray data byte without running status: skip.
            i += 1
            continue

        high = status & 0xF0
        ch = status & 0x0F
        if high in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            if i + 1 >= n:
                break
            d1, d2 = blob[i], blob[i + 1]
            events.append(ChannelEvent(channel=ch, status=high, data1=d1, data2=d2))
            i += 2
            running_status = status
        elif high in (0xC0, 0xD0):
            if i >= n:
                break
            d1 = blob[i]
            events.append(ChannelEvent(channel=ch, status=high, data1=d1, data2=0))
            i += 1
            running_status = status
        else:
            i += 1
    return events


def _parse_xg_message(msg: bytes) -> Optional[XGRawMessage]:
    if len(msg) < 8:
        return None
    if msg[0] != 0xF0 or msg[-1] != 0xF7:
        return None
    if msg[1] != 0x43:
        return None  # not Yamaha
    if (msg[2] & 0xF0) != 0x10:
        return None  # not Parameter Change (1n)
    if msg[3] != 0x4C:
        return None  # not XG model
    ah, am, al = msg[4], msg[5], msg[6]
    data = bytes(msg[7:-1])
    return XGRawMessage(ah=ah, am=am, al=al, data=data, raw=bytes(msg))


def parse_xg_bulk_to_udm(
    source: Union[bytes, str, Path],
    *,
    device_model: DeviceModel = DeviceModel.QY70,
    base_device: Optional[Device] = None,
) -> Device:
    """Apply a stream of XG Param Change messages to a UDM Device.

    Args:
        source: .syx file path or raw bytes containing XG Param Change stream.
        device_model: Target device model when creating a new Device.
        base_device: If provided, apply XG updates on top of this Device
            (additive). Otherwise create a fresh Device.

    Returns:
        A Device reflecting the cumulative XG parameter changes. Non-XG
        SysEx messages are ignored (but preserved in _raw_passthrough if
        `base_device` is None).

    Raises:
        ValueError: If no XG messages are found in the stream.
    """
    if isinstance(source, (bytes, bytearray)):
        blob = bytes(source)
    else:
        blob = Path(source).read_bytes()

    messages = _split_sysex(blob)
    xg_msgs = [x for x in (_parse_xg_message(m) for m in messages) if x is not None]
    channel_events = _scan_channel_events(blob)

    if not xg_msgs and not channel_events:
        raise ValueError("No XG Parameter Change or channel events found in stream")

    device = base_device if base_device is not None else Device(
        model=device_model,
        effects=Effects(variation=VariationBlock()),
        source_format="xg-bulk",
        _raw_passthrough=blob,
    )
    if device.effects.variation is None:
        device.effects.variation = VariationBlock()

    for msg in xg_msgs:
        _apply_xg_message(device, msg)

    if channel_events:
        _apply_channel_events(device, channel_events)

    return device


def _find_part_for_channel(device: Device, channel_0based: int) -> MultiPart:
    """Return the MultiPart assigned to `channel_0based` (rx_channel match).

    If no part maps to that channel yet, grow `multi_part` until the slot
    exists with `rx_channel = channel_0based` as the default.
    """
    for part in device.multi_part:
        if part.rx_channel == channel_0based:
            return part
    while len(device.multi_part) <= channel_0based:
        idx = len(device.multi_part)
        device.multi_part.append(
            MultiPart(part_index=idx, rx_channel=idx, voice=Voice())
        )
    return device.multi_part[channel_0based]


def _apply_channel_events(device: Device, events: list["ChannelEvent"]) -> None:
    """Fold CC Bank Select / Program Change / Volume / Pan / Sends into parts.

    QY70 XG PARM OUT emits voice assignments as channel events
    (`Bn 00 MSB`, `Bn 20 LSB`, `Cn PROG`, and CC 7/10/91/93 for mixer).
    Replay them in order so later values win.
    """
    for ev in events:
        part = _find_part_for_channel(device, ev.channel)
        if ev.status == 0xB0:
            cc, val = ev.data1 & 0x7F, ev.data2 & 0x7F
            if cc == 0:
                part.voice = replace(part.voice, bank_msb=val)
            elif cc == 32:
                part.voice = replace(part.voice, bank_lsb=val)
            elif cc == 7:
                part.volume = val
            elif cc == 10:
                part.pan = val
            elif cc == 91:
                part.reverb_send = val
            elif cc == 93:
                part.chorus_send = val
            elif cc == 94:
                part.variation_send = val
        elif ev.status == 0xC0:
            part.voice = replace(part.voice, program=ev.data1 & 0x7F)


def _apply_xg_message(device: Device, msg: XGRawMessage) -> None:
    if msg.ah == AH_SYSTEM:
        _apply_system(device.system, msg)
    elif msg.ah == AH_EFFECT:
        _apply_effects(device.effects, msg)
    elif msg.ah == AH_MULTI_PART:
        _apply_multi_part(device, msg)
    elif msg.ah in (AH_DRUM_SETUP_1, AH_DRUM_SETUP_2):
        _apply_drum_setup(device, msg)


def _ensure_drum_setup(device: Device, kit_index: int) -> DrumSetup:
    for ds in device.drum_setup:
        if ds.kit_index == kit_index:
            return ds
    ds = DrumSetup(kit_index=kit_index, notes={})
    device.drum_setup.append(ds)
    return ds


def _apply_drum_setup(device: Device, msg: XGRawMessage) -> None:
    """Fold an XG Drum Setup Parameter Change (AH 0x30/0x31) into UDM.

    AH=0x30 ↔ kit 1, AH=0x31 ↔ kit 2. AM = drum note (13..84). AL =
    per-note field (see XG System Level 1 spec v1.1, table 2-5):

        0x00 pitch_coarse (signed, 0x40 = 0)
        0x01 pitch_fine   (signed, 0x40 = 0)
        0x02 level        (0..127)
        0x03 alt_group    (0..127)
        0x04 pan          (0..127, 0x40 = center)
        0x05 reverb_send  (0..127)
        0x06 chorus_send  (0..127)
        0x07 variation_send (0..127)
        0x0B filter_cutoff (signed)
        0x0C filter_resonance (signed)
        0x0D eg_attack    (signed)
        0x0E eg_decay1    (signed)
        0x0F eg_decay2    (signed)

    Values outside the 13..84 note range or missing data bytes are
    ignored silently — the surrounding raw bytes stay in
    `_raw_passthrough` so XG re-emit is lossless.
    """
    if not msg.data:
        return
    note = msg.am
    if not 13 <= note <= 84:
        return

    kit_index = 0 if msg.ah == AH_DRUM_SETUP_1 else 1
    ds = _ensure_drum_setup(device, kit_index)
    drum_note = ds.notes.get(note) or DrumNote()
    val = msg.data[0] & 0x7F
    signed = val - 0x40  # for signed fields

    if msg.al == 0x00:
        drum_note.pitch_coarse = max(-64, min(63, signed))
    elif msg.al == 0x01:
        drum_note.pitch_fine = max(-64, min(63, signed))
    elif msg.al == 0x02:
        drum_note.level = val
    elif msg.al == 0x03:
        drum_note.alt_group = val
    elif msg.al == 0x04:
        drum_note.pan = val
    elif msg.al == 0x05:
        drum_note.reverb_send = val
    elif msg.al == 0x06:
        drum_note.chorus_send = val
    elif msg.al == 0x07:
        drum_note.variation_send = val
    elif msg.al == 0x0B:
        drum_note.filter_cutoff = max(-64, min(63, signed))
    elif msg.al == 0x0C:
        drum_note.filter_resonance = max(-64, min(63, signed))
    elif msg.al == 0x0D:
        drum_note.eg_attack = max(-64, min(63, signed))
    elif msg.al == 0x0E:
        drum_note.eg_decay1 = max(-64, min(63, signed))
    elif msg.al == 0x0F:
        drum_note.eg_decay2 = max(-64, min(63, signed))
    else:
        return  # unknown AL, don't alloc DrumNote for nothing
    ds.notes[note] = drum_note


def _apply_system(system: System, msg: XGRawMessage) -> None:
    if msg.am != 0x00:
        return
    if msg.al == 0x04 and msg.data:
        system.master_volume = max(0, min(127, msg.data[0]))
    elif msg.al == 0x06 and msg.data:
        raw = msg.data[0]
        system.transpose = raw - 64


def _apply_effects(effects: Effects, msg: XGRawMessage) -> None:
    if msg.am == 0x01:
        # Reverb (0x00-0x1F) / Chorus (0x20-0x3F) / Variation (0x40+)
        if msg.al == 0x00 and msg.data:
            effects.reverb.type_code = max(0, min(10, msg.data[0]))
        elif msg.al == 0x0C and msg.data:
            effects.reverb.return_level = msg.data[0] & 0x7F
        elif msg.al == 0x20 and msg.data:
            effects.chorus.type_code = max(0, min(10, msg.data[0]))
        elif msg.al == 0x2C and msg.data:
            effects.chorus.return_level = msg.data[0] & 0x7F
        elif msg.al == 0x40 and msg.data and effects.variation is not None:
            effects.variation.type_code = max(0, min(42, msg.data[0]))
        elif msg.al == 0x56 and msg.data and effects.variation is not None:
            effects.variation.return_level = msg.data[0] & 0x7F

        if effects.variation is not None:
            effects.variation.params[msg.al] = msg.data[0] if msg.data else 0
        if 0x00 <= msg.al < 0x20:
            effects.reverb.params[msg.al] = msg.data[0] if msg.data else 0
        elif 0x20 <= msg.al < 0x40:
            effects.chorus.params[msg.al] = msg.data[0] if msg.data else 0


def _ensure_part(device: Device, index: int) -> MultiPart:
    while len(device.multi_part) <= index:
        device.multi_part.append(
            MultiPart(
                part_index=len(device.multi_part),
                rx_channel=len(device.multi_part),
                voice=Voice(),
            )
        )
    return device.multi_part[index]


def _apply_multi_part(device: Device, msg: XGRawMessage) -> None:
    if msg.am >= 32:
        return
    part = _ensure_part(device, msg.am)
    if not msg.data:
        return
    value = msg.data[0]

    if msg.al == 0x01:  # Bank MSB
        part.voice = replace(part.voice, bank_msb=value & 0x7F)
    elif msg.al == 0x02:  # Bank LSB
        part.voice = replace(part.voice, bank_lsb=value & 0x7F)
    elif msg.al == 0x03:  # Program
        part.voice = replace(part.voice, program=value & 0x7F)
    elif msg.al == 0x04:  # Rx Channel (0..15 = ch 1..16, 16 = OFF)
        part.rx_channel = value & 0x1F
    elif msg.al == 0x0B:  # Volume
        part.volume = value & 0x7F
    elif msg.al == 0x0E:  # Pan
        part.pan = value & 0x7F
    elif msg.al == 0x11:  # Dry Level (observed in XG PARM OUT)
        part.dry_level = value & 0x7F
    elif msg.al == 0x13:  # Reverb Send
        part.reverb_send = value & 0x7F
    elif msg.al == 0x12:  # Chorus Send
        part.chorus_send = value & 0x7F
    elif msg.al == 0x14:  # Variation Send
        part.variation_send = value & 0x7F
    elif msg.al == 0x23:  # Bend Pitch Control
        part.bend_pitch = min(24, max(0, value - 0x40 + 2))


def emit_udm_to_xg_bulk(device: Device) -> bytes:
    """Re-emit the original XG bulk stream via Device._raw_passthrough.

    A true UDM → XG message stream synthesis is intentionally deferred:
    the bulk capture contains implementation-specific ordering and
    non-UDM data that the editor realtime layer (F5) will re-emit
    parameter-by-parameter when needed.

    Args:
        device: Device with `source_format == 'xg-bulk'`.

    Returns:
        The original raw bytes preserved during parse.

    Raises:
        ValueError: If no raw passthrough is available.
    """
    if not device._raw_passthrough:
        raise ValueError(
            "XG bulk emit requires Device._raw_passthrough; use the "
            "F5 realtime editor to synthesize messages from UDM."
        )
    return bytes(device._raw_passthrough)
