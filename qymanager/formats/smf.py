"""Standard MIDI File (SMF) ↔ UDM Device bridge.

Uses the `mido` library to parse/emit .mid files (format 0 or 1) into a
UDM Device whose `.songs[0]` contains one SongTrack per MIDI track, with
MidiEvents populated from note_on/note_off/CC/PC/PB/NRPN messages.
Tempo is taken from the first set_tempo meta event (default 120 BPM).
Time signature from the first time_signature meta event (default 4/4).

Dense/sparse Q7P patterns are out of scope — this is for MIDI-style song
data. For Q7P-specific conversion use the qy700 reader/writer modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import mido

from qymanager.model import (
    Device,
    DeviceModel,
    EventKind,
    MidiEvent,
    Song,
    SongTrack,
    SongTrackKind,
    TimeSig,
)


_MIDO_KIND_MAP: dict[str, EventKind] = {
    "note_on": EventKind.NOTE_ON,
    "note_off": EventKind.NOTE_OFF,
    "control_change": EventKind.CC,
    "program_change": EventKind.PROG_CHANGE,
    "pitchwheel": EventKind.PB,
}


def parse_smf_to_udm(
    source: Union[bytes, str, Path],
    *,
    device_model: DeviceModel = DeviceModel.QY70,
) -> Device:
    """Parse an SMF file (path or bytes) into a UDM Device.

    Args:
        source: File path or raw .mid bytes.
        device_model: Target device model for the returned Device.

    Returns:
        Device with `songs=[Song(...)]` where each MIDI track becomes a
        SongTrack. Absolute ticks preserved.

    Raises:
        ValueError: If the bytes are not a valid SMF or mido fails to load.
    """
    if isinstance(source, (bytes, bytearray)):
        import io

        mid = mido.MidiFile(file=io.BytesIO(bytes(source)))
    else:
        mid = mido.MidiFile(str(source))

    ticks_per_beat = mid.ticks_per_beat or 480

    tempo_bpm = 120.0
    ts_numer = 4
    ts_denom = 4
    song_name = ""

    udm_tracks: list[SongTrack] = []

    for track_idx, track in enumerate(mid.tracks):
        abs_tick = 0
        events: list[MidiEvent] = []
        track_channel: Optional[int] = None

        for msg in track:
            abs_tick += msg.time
            if msg.is_meta:
                if msg.type == "set_tempo" and tempo_bpm == 120.0:
                    tempo_bpm = round(60_000_000.0 / msg.tempo, 3)
                elif msg.type == "time_signature":
                    ts_numer = msg.numerator
                    ts_denom = msg.denominator
                elif msg.type == "track_name" and not song_name and track_idx == 0:
                    song_name = (msg.name or "")[:10]
                continue

            kind = _MIDO_KIND_MAP.get(msg.type)
            if kind is None:
                continue

            channel = getattr(msg, "channel", 0) & 0x0F
            if track_channel is None:
                track_channel = channel

            if kind == EventKind.NOTE_ON:
                data1 = msg.note
                data2 = msg.velocity
                if data2 == 0:
                    kind = EventKind.NOTE_OFF
            elif kind == EventKind.NOTE_OFF:
                data1 = msg.note
                data2 = msg.velocity
            elif kind == EventKind.CC:
                data1 = msg.control
                data2 = msg.value
            elif kind == EventKind.PROG_CHANGE:
                data1 = msg.program
                data2 = 0
            elif kind == EventKind.PB:
                pitch_14 = max(0, min(16383, msg.pitch + 8192))
                data1 = pitch_14 & 0x7F
                data2 = (pitch_14 >> 7) & 0x7F
            else:
                continue

            events.append(
                MidiEvent(
                    tick=abs_tick,
                    channel=channel,
                    kind=kind,
                    data1=max(0, min(127, data1)),
                    data2=max(0, min(127, data2)),
                )
            )

        if events:
            udm_tracks.append(
                SongTrack(
                    index=track_idx,
                    kind=SongTrackKind.SEQ,
                    events=events,
                    midi_channel=track_channel,
                )
            )

    song = Song(
        index=0,
        name=song_name,
        tempo_bpm=tempo_bpm,
        time_sig=TimeSig(numerator=ts_numer, denominator=ts_denom),
        tracks=udm_tracks,
    )

    raw: Optional[bytes]
    if isinstance(source, (bytes, bytearray)):
        raw = bytes(source)
    else:
        with open(source, "rb") as f:
            raw = f.read()

    return Device(
        model=device_model,
        songs=[song],
        source_format="smf",
        _raw_passthrough=raw,
    )


def emit_udm_to_smf(device: Device, path: Optional[Union[str, Path]] = None) -> bytes:
    """Serialize the first Song of a Device into a Standard MIDI File.

    Emits format 1: track 0 = conductor (tempo + time-sig), tracks 1+ =
    one per SongTrack, events sorted by absolute tick. Always writes
    note_off messages (never zero-velocity note_on). Does NOT rely on
    Device._raw_passthrough — produces a fresh SMF from the UDM song.

    Args:
        device: Device with at least one Song.
        path: Optional output path; if provided the MIDI file is saved.

    Returns:
        Raw SMF bytes.

    Raises:
        ValueError: If device has no songs.
    """
    if not device.songs:
        raise ValueError("Device has no songs to emit as SMF")
    song = device.songs[0]

    mid = mido.MidiFile(type=1, ticks_per_beat=480)

    conductor = mido.MidiTrack()
    tempo_us = int(round(60_000_000.0 / max(song.tempo_bpm, 1.0)))
    conductor.append(mido.MetaMessage("set_tempo", tempo=tempo_us, time=0))
    conductor.append(
        mido.MetaMessage(
            "time_signature",
            numerator=song.time_sig.numerator,
            denominator=song.time_sig.denominator,
            time=0,
        )
    )
    if song.name:
        conductor.insert(0, mido.MetaMessage("track_name", name=song.name[:10], time=0))
    mid.tracks.append(conductor)

    for song_track in song.tracks:
        track = mido.MidiTrack()
        sorted_events = sorted(song_track.events, key=lambda e: e.tick)
        prev_tick = 0
        for ev in sorted_events:
            delta = max(0, ev.tick - prev_tick)
            prev_tick = ev.tick
            msg = _midi_event_to_mido(ev, delta)
            if msg is not None:
                track.append(msg)
        mid.tracks.append(track)

    import io

    buf = io.BytesIO()
    mid.save(file=buf)
    raw = buf.getvalue()

    if path is not None:
        with open(path, "wb") as f:
            f.write(raw)

    return raw


def _midi_event_to_mido(ev: MidiEvent, delta: int) -> Optional[mido.Message]:
    if ev.kind == EventKind.NOTE_ON:
        return mido.Message(
            "note_on",
            channel=ev.channel,
            note=ev.data1,
            velocity=ev.data2,
            time=delta,
        )
    if ev.kind == EventKind.NOTE_OFF:
        return mido.Message(
            "note_off",
            channel=ev.channel,
            note=ev.data1,
            velocity=ev.data2,
            time=delta,
        )
    if ev.kind == EventKind.CC:
        return mido.Message(
            "control_change",
            channel=ev.channel,
            control=ev.data1,
            value=ev.data2,
            time=delta,
        )
    if ev.kind == EventKind.PROG_CHANGE:
        return mido.Message(
            "program_change",
            channel=ev.channel,
            program=ev.data1,
            time=delta,
        )
    if ev.kind == EventKind.PB:
        pitch_14 = (ev.data2 << 7) | ev.data1
        pitch_signed = pitch_14 - 8192
        return mido.Message("pitchwheel", channel=ev.channel, pitch=pitch_signed, time=delta)
    return None
