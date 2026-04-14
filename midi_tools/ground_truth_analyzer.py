#!/usr/bin/env python3
"""Ground Truth Analyzer for QY70 Reverse Engineering.

Compares captured QY70 SysEx bulk dumps against known musical content
to validate bitstream decoding hypotheses. Uses the proven chord decoder
from event_decoder.py.

Usage:
    # Analyze all non-empty tracks:
    python3 midi_tools/ground_truth_analyzer.py captured/ground_truth_A.syx

    # Validate CHD2 against expected C major chord:
    python3 midi_tools/ground_truth_analyzer.py file.syx --expected-chord C4,E4,G4

    # Analyze specific section/track:
    python3 midi_tools/ground_truth_analyzer.py file.syx --section 0 --track 4

Expected test patterns (program on QY70, capture via UTILITY → MIDI → Bulk Dump):
    Pattern A: Solo CHD2, C major, 4 bars, 4/4, 120 BPM
    Pattern B: Solo CHD2, Am, 4 bars
    Pattern C: Solo RHY1, kick (note 36) on beat 1
    Pattern D: Main A=C major, Main B=G major on CHD2
"""

import sys
import os
import argparse
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse the proven decoder
from midi_tools.event_decoder import (
    decode_track,
    nn,
    DecodedTrack,
    SECTION_NAMES,
    TRACK_NAMES,
    ENCODING_CHORD,
    ENCODING_GENERAL,
    ENCODING_BASS_SLOT,
    ENCODING_DRUM_PRIMARY,
)
from qymanager.formats.qy70.sysex_parser import SysExParser
from qymanager.utils.yamaha_7bit import encode_7bit


NOTE_NAMES_MAP = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


def note_name_to_midi(name: str) -> int:
    """Parse 'C4', 'G#3', 'Eb2' to MIDI number."""
    name = name.strip()
    for length in (2, 1):
        note_str = name[:length]
        rest = name[length:]
        if note_str in NOTE_NAMES_MAP and rest.lstrip("-").isdigit():
            octave = int(rest)
            return (octave + 1) * 12 + NOTE_NAMES_MAP[note_str]
    raise ValueError(f"Cannot parse note: {name}")


def extract_tempo(syx_path: str) -> Optional[int]:
    """Extract tempo from QY70 header."""
    parser = SysExParser()
    with open(syx_path, "rb") as f:
        msgs = parser.parse_bytes(f.read())

    header = bytearray()
    for m in msgs:
        if m.is_style_data and m.address_low == 0x7F and m.decoded_data:
            header.extend(m.decoded_data)

    if len(header) < 7:
        return None

    encoded = encode_7bit(bytes(header[:7]))
    if not encoded:
        return None

    range_byte = encoded[0]
    offset_byte = header[0]
    bpm = (range_byte * 95 - 133) + offset_byte
    return bpm if 30 <= bpm <= 300 else None


def count_active_tracks(syx_path: str) -> dict:
    """Count tracks with data vs empty tracks."""
    parser = SysExParser()
    with open(syx_path, "rb") as f:
        msgs = parser.parse_bytes(f.read())

    tracks = {}
    for m in msgs:
        if m.is_style_data and m.decoded_data and 0 <= m.address_low <= 0x2F:
            al = m.address_low
            if al not in tracks:
                tracks[al] = 0
            tracks[al] += len(m.decoded_data)

    return tracks


def validate_chord_track(
    track: DecodedTrack,
    expected_notes: Optional[List[int]] = None,
) -> dict:
    """Validate a decoded chord track against expected notes."""
    report = {
        "section": track.section_name,
        "track": track.track_name,
        "encoding": track.encoding_type,
        "confidence": track.confidence,
        "bars": len(track.bars),
        "events": track.total_events,
        "chord_match": None,
        "beat_accuracy": None,
        "all_chords": [],
        "details": [],
    }

    for bar in track.bars:
        bar_info = {
            "bar": bar.bar_index,
            "notes": bar.chord_notes,
            "names": bar.chord_names,
            "confidence": bar.confidence,
            "events": len(bar.events),
        }
        report["all_chords"].append(bar_info)

    # Beat accuracy: % of events with valid one-hot beat counter
    total_beats = 0
    valid_beats = 0
    for bar in track.bars:
        for evt in bar.events:
            total_beats += 1
            if evt.beat_number >= 0:
                valid_beats += 1
    if total_beats > 0:
        report["beat_accuracy"] = valid_beats / total_beats

    # Note selection: % of events that select at least 1 note
    events_with_notes = sum(
        1 for bar in track.bars for evt in bar.events if evt.selected_notes
    )
    if track.total_events > 0:
        report["note_selection"] = events_with_notes / track.total_events

    # Validate against expected chord
    if expected_notes and track.bars:
        expected_set = set(expected_notes)
        matches = 0
        for bar in track.bars:
            found_set = set(bar.chord_notes)
            if expected_set.issubset(found_set):
                matches += 1
                report["details"].append(
                    f"Bar {bar.bar_index}: MATCH — {bar.chord_names} "
                    f"contains {[nn(n) for n in expected_notes]}"
                )
            else:
                overlap = expected_set & found_set
                missing = expected_set - found_set
                report["details"].append(
                    f"Bar {bar.bar_index}: PARTIAL — {bar.chord_names} "
                    f"found={[nn(n) for n in overlap]}, "
                    f"missing={[nn(n) for n in missing]}"
                )
        report["chord_match"] = matches / len(track.bars)

    return report


def print_report(report: dict, verbose: bool = True):
    """Print a track validation report."""
    enc = report["encoding"].upper()
    conf = report["confidence"] * 100

    print(f"  {report['section']} / {report['track']}  "
          f"|  {enc}  |  Confidence: {conf:.0f}%")
    print(f"  Bars: {report['bars']}  Events: {report['events']}")

    if report["beat_accuracy"] is not None:
        print(f"  Beat accuracy: {report['beat_accuracy']*100:.0f}%")
    if report.get("note_selection") is not None:
        print(f"  Note selection: {report['note_selection']*100:.0f}%")
    if report["chord_match"] is not None:
        print(f"  Chord match: {report['chord_match']*100:.0f}%")

    if verbose:
        for chord_info in report["all_chords"]:
            notes_str = ", ".join(chord_info["names"])
            print(f"    Bar {chord_info['bar']}: [{notes_str}] "
                  f"({chord_info['events']} events, {chord_info['confidence']*100:.0f}%)")

        for detail in report["details"]:
            print(f"    {detail}")


def main():
    parser = argparse.ArgumentParser(
        description="Ground Truth Analyzer for QY70 SysEx captures"
    )
    parser.add_argument("syx_file", help="Path to .syx file")
    parser.add_argument(
        "--expected-chord",
        help="Expected chord notes (e.g., 'C4,E4,G4' or '60,64,67')",
    )
    parser.add_argument("--section", type=int, help="Analyze only this section (0-5)")
    parser.add_argument("--track", type=int, help="Analyze only this track (0-7)")
    parser.add_argument("--quiet", action="store_true", help="Compact output")
    args = parser.parse_args()

    # Parse expected notes
    expected_notes = None
    if args.expected_chord:
        parts = args.expected_chord.split(",")
        try:
            expected_notes = [int(p) for p in parts]
        except ValueError:
            expected_notes = [note_name_to_midi(p) for p in parts]

    syx_path = args.syx_file

    # File info
    print(f"{'='*65}")
    print(f"  Ground Truth Analysis: {os.path.basename(syx_path)}")
    print(f"{'='*65}")

    tempo = extract_tempo(syx_path)
    if tempo:
        print(f"  Tempo: {tempo} BPM")

    active = count_active_tracks(syx_path)
    print(f"  Active tracks: {len(active)} AL entries")

    if expected_notes:
        print(f"  Expected chord: {[nn(n) for n in expected_notes]} "
              f"(MIDI: {expected_notes})")
    print()

    # Decode and analyze
    sections = [args.section] if args.section is not None else range(6)
    tracks_to_check = [args.track] if args.track is not None else range(8)

    reports = []
    for section_idx in sections:
        for track_idx in tracks_to_check:
            al = section_idx * 8 + track_idx
            if al not in active:
                continue

            decoded = decode_track(syx_path, section_idx, track_idx)
            if decoded is None:
                continue

            report = validate_chord_track(decoded, expected_notes)
            reports.append(report)

            print(f"{'─'*65}")
            print_report(report, verbose=not args.quiet)
            print()

    # Summary
    if reports:
        print(f"{'='*65}")
        print(f"  SUMMARY: {len(reports)} tracks decoded")

        chord_reports = [r for r in reports if r["encoding"] == "chord"]
        general_reports = [r for r in reports if r["encoding"] == "general"]
        other_reports = [r for r in reports
                         if r["encoding"] not in ("chord", "general")]

        if chord_reports:
            avg_conf = sum(r["confidence"] for r in chord_reports) / len(chord_reports)
            avg_beat = sum(r["beat_accuracy"] or 0 for r in chord_reports) / len(chord_reports)
            print(f"  Chord tracks ({len(chord_reports)}): "
                  f"avg confidence={avg_conf*100:.0f}%, "
                  f"avg beat accuracy={avg_beat*100:.0f}%")

        if general_reports:
            avg_conf = sum(r["confidence"] for r in general_reports) / len(general_reports)
            print(f"  General tracks ({len(general_reports)}): "
                  f"avg confidence={avg_conf*100:.0f}%")

        if other_reports:
            for r in other_reports:
                print(f"  {r['encoding']} ({r['track']}): "
                      f"confidence={r['confidence']*100:.0f}%")

        if expected_notes:
            matched = [r for r in reports if r.get("chord_match") is not None]
            if matched:
                avg_match = sum(r["chord_match"] for r in matched) / len(matched)
                print(f"  Chord match vs expected: {avg_match*100:.0f}%")

        print(f"{'='*65}")


if __name__ == "__main__":
    main()
