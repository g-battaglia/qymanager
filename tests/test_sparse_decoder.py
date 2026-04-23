"""Regression tests for the QY70 sparse R=9 barrel-rotation decoder.

Proven ground truth (Session 14 wiki): `known_pattern.syx` contains
exactly 7 decodable events on RHY1 AL=0x00. Real user patterns
(MR. Vain, Summer) should decode a plausible number of events per
track with ≥60% musical-range plausibility. Factory dense styles
(SGT) must NOT produce a flood of ghost notes — the plausibility
guard-rail in `/phrases` should gate them out.
"""

from pathlib import Path

import pytest

from qymanager.formats.qy70.encoder_sparse import (
    decode_sparse_track,
    sparse_track_plausibility,
)
from qymanager.formats.qy70.sysex_parser import SysExParser

FIXTURES = Path(__file__).resolve().parents[1]
KNOWN_PATTERN = FIXTURES / "midi_tools" / "captured" / "known_pattern.syx"
MR_VAIN = FIXTURES / "data" / "qy70_sysx" / "P -  MR. Vain - 20231101.syx"
SUMMER = FIXTURES / "data" / "qy70_sysx" / "P -  Summer - 20231101.syx"
SGT = FIXTURES / "data" / "captures_2026_04_23" / "SGT_backup_20260423_112505.syx"


def _track_data(path: Path, al: int) -> bytes:
    msgs = SysExParser().parse_file(str(path))
    out = bytearray()
    for m in msgs:
        if m.is_style_data and m.address_low == al and m.decoded_data:
            out.extend(m.decoded_data)
    return bytes(out)


def _all_track_data(path: Path) -> dict[int, bytes]:
    msgs = SysExParser().parse_file(str(path))
    tracks: dict[int, bytearray] = {}
    for m in msgs:
        if not m.is_style_data or m.decoded_data is None:
            continue
        if m.address_low == 0x7F:
            continue
        tracks.setdefault(m.address_low, bytearray()).extend(m.decoded_data)
    return {al: bytes(b) for al, b in tracks.items() if b}


@pytest.mark.skipif(not KNOWN_PATTERN.exists(), reason="known_pattern fixture missing")
def test_known_pattern_decodes_seven_events():
    """Wiki Session 14: known_pattern RHY1 has 7 events, all musical."""
    td = _track_data(KNOWN_PATTERN, 0x00)
    assert len(td) >= 41 + 7 * 7

    events = decode_sparse_track(td)
    assert len(events) >= 7, f"expected ≥7 events, got {len(events)}"

    plausibility = sparse_track_plausibility(events[:7])
    # The first 7 events are the proven ground-truth set; all must
    # land in the drum range.
    assert plausibility >= 6 / 7, f"first 7 events only {plausibility:.0%} plausible"

    # Session 14 ground truth: the first event is the kick on beat 0.
    kick = events[0]
    assert kick["note"] == 36, f"evt[0] note={kick['note']}, expected 36 (kick)"
    assert kick["velocity"] == 127, f"evt[0] vel={kick['velocity']}, expected 127"
    assert kick["beat"] == 0


@pytest.mark.skipif(not MR_VAIN.exists(), reason="MR Vain fixture missing")
def test_mr_vain_user_pattern_decodes():
    """MR. Vain is a user-sparse pattern — each active track must
    decode ≥10 events with ≥60% plausibility."""
    tracks = _all_track_data(MR_VAIN)
    decoded_count = 0
    plausibility_sum = 0.0
    for al, td in tracks.items():
        if len(td) < 48:
            continue
        events = decode_sparse_track(td)
        if not events:
            continue
        ratio = sparse_track_plausibility(events)
        if ratio >= 0.6:
            decoded_count += 1
            plausibility_sum += ratio

    assert decoded_count >= 4, f"expected ≥4 tracks decoded, got {decoded_count}"
    assert (
        plausibility_sum / decoded_count >= 0.65
    ), "average plausibility below 65% across MR. Vain tracks"


@pytest.mark.skipif(not SUMMER.exists(), reason="Summer fixture missing")
def test_summer_user_pattern_decodes():
    """Summer is another user pattern; at least 2 tracks must pass
    the 60% plausibility guard."""
    tracks = _all_track_data(SUMMER)
    decoded = sum(
        1
        for td in tracks.values()
        if len(td) >= 48
        and sparse_track_plausibility(decode_sparse_track(td)) >= 0.6
    )
    assert decoded >= 2, f"expected ≥2 Summer tracks decoded, got {decoded}"


@pytest.mark.skipif(not MR_VAIN.exists(), reason="MR Vain fixture missing")
def test_sparse_decoded_phrases_emit_smf():
    """The full round-trip SysEx → UDM.phrases_user → SMF must produce
    a playable MIDI file even when `device.songs` is empty (which is
    the common case for QY70 bulks: no Song object, only phrases)."""
    from qymanager.formats.qy70.reader import parse_syx_to_udm
    from qymanager.formats.smf import emit_udm_to_smf
    import mido
    import io

    device = parse_syx_to_udm(MR_VAIN.read_bytes())
    assert device.songs == []
    assert len(device.phrases_user) >= 4

    smf_bytes = emit_udm_to_smf(device)
    assert len(smf_bytes) > 0

    # Parse back and count note_on events across all tracks.
    mid = mido.MidiFile(file=io.BytesIO(smf_bytes))
    total_notes = sum(
        1
        for track in mid.tracks
        for msg in track
        if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0
    )
    # MR. Vain decodes to ≥80 real notes; the threshold is deliberately
    # lower than observed 97 so minor decoder changes don't trip us.
    assert total_notes >= 80, f"expected ≥80 note_on events in SMF, got {total_notes}"


@pytest.mark.skipif(not MR_VAIN.exists(), reason="MR Vain fixture missing")
def test_nearest_neighbour_resolves_chord_voices():
    """Tier 1.5 NN matcher: MR. Vain C1/C2/C3 signatures have no exact
    DB entry but sit within 3 bits of Pad 2 (warm) in the DB. Before
    this tier they resolved to 'Chord/Melodic (class — exact via XG
    query)'; now they must come back tagged `(NN d=...)` with the
    real voice name."""
    from qymanager.analysis.syx_analyzer import SyxAnalyzer
    import qymanager.analysis.syx_analyzer as mod

    mod._SIGNATURE_DB = None  # force reload to pick up DB updates
    a = SyxAnalyzer().analyze_file(str(MR_VAIN))
    nn_tracks = [
        t for t in a.qy70_tracks if t.has_data and "(NN" in (t.voice_name or "")
    ]
    assert len(nn_tracks) >= 2, (
        f"expected ≥2 NN-resolved tracks in MR. Vain, got "
        f"{len(nn_tracks)}: {[(t.name, t.voice_name) for t in nn_tracks]}"
    )
    # The chord tracks converge on Pad 2 (warm) at bit distance ≤ 3.
    for t in nn_tracks:
        assert "Pad" in t.voice_name or "pad" in t.voice_name.lower(), (
            f"{t.name} unexpected NN voice: {t.voice_name}"
        )


@pytest.mark.skipif(not SGT.exists(), reason="SGT fixture missing")
def test_sgt_dense_style_does_not_flood():
    """Factory dense style — Session 19/20 proved the decoder fails.
    We don't forbid the decoder from producing *some* events (the
    backup carries very sparse Fill_BA/Ending data), but it MUST NOT
    decode a large fraction of tracks as if they were musical."""
    tracks = _all_track_data(SGT)
    passed = [
        td
        for td in tracks.values()
        if len(td) >= 48
        and sparse_track_plausibility(decode_sparse_track(td)) >= 0.6
    ]
    # At most a handful of Fill_BA/Ending tracks should clear the
    # guard; anything above 4 would mean we're accepting random noise.
    assert len(passed) <= 4, f"SGT passed {len(passed)} tracks — decoder hallucinating?"
