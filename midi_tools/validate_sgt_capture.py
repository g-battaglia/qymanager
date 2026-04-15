#!/usr/bin/env python3
"""Validate QY70 event decoders against SGT playback capture.

Compares decoded bitstream events from QY70_SGT.syx against
real MIDI output captured from QY70 hardware (sgt_full_capture.json).

Channel → Slot mapping (Style PATT OUT 9~16):
    ch9  → slot 0 (RHY1)  — 2543 drum encoding
    ch10 → slot 1 (RHY2)  — 29CB general encoding
    ch11 → slot 5 (PAD)   — 29CB general encoding
    ch12 → slot 2 (BASS)  — 2BE3 bass encoding
    ch14 → slot 4 (CHD2)  — 1FA3 chord encoding
    ch15 → slot 6 (PHR1)  — 1FA3 chord encoding

Usage:
    .venv/bin/python3 midi_tools/validate_sgt_capture.py
"""

import json
import sys
import os
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from midi_tools.event_decoder import (
    decode_track, decode_drum_event, get_track_data, extract_bars,
    classify_encoding, decode_header_notes, header_to_midi_notes,
    ENCODING_CHORD, ENCODING_DRUM_PRIMARY, ENCODING_GENERAL, ENCODING_BASS_SLOT,
    SECTION_NAMES, TRACK_NAMES,
)

SYX_PATH = "tests/fixtures/QY70_SGT.syx"
CAPTURE_PATH = "midi_tools/captured/sgt_full_capture.json"

# Channel → (slot, label)
CHANNEL_SLOT_MAP = {
    "9":  (0, "RHY1"),
    "10": (1, "RHY2"),
    "11": (5, "PAD"),
    "12": (2, "BASS"),
    "14": (4, "CHD2"),
    "15": (6, "PHR1"),
}


def load_capture():
    """Load captured MIDI data."""
    with open(CAPTURE_PATH) as f:
        return json.load(f)


def decode_all_sections_drum(syx_path, slot):
    """Decode drum events across all sections using decode_drum_event."""
    all_notes = []
    all_velocities = []

    for section in range(6):
        data = get_track_data(syx_path, section, slot)
        if len(data) < 28:
            continue

        preamble, bars = extract_bars(data)
        encoding = classify_encoding(preamble)

        for bar_idx, (header, events) in enumerate(bars):
            note_idx = 0
            for evt_idx, evt in enumerate(events):
                result = decode_drum_event(evt, evt_idx, note_idx)
                if result is None:
                    continue
                if result["type"] == "note":
                    all_notes.append(result["note"])
                    all_velocities.append(result["velocity"])
                    note_idx += 1
                elif result["type"] == "control":
                    pass  # Don't increment note_idx

    return all_notes, all_velocities


def decode_all_sections_chord(syx_path, slot):
    """Decode chord events across all sections using decode_track."""
    all_notes = []
    all_velocities = []

    for section in range(6):
        dt = decode_track(syx_path, section, slot)
        if dt is None:
            continue

        for bar in dt.bars:
            for evt in bar.events:
                if evt.selected_notes:
                    all_notes.extend(evt.selected_notes)
                    # Velocity from f4_param4
                    vel = min(127, max(40, 40 + evt.f4_param4 * 6))
                    all_velocities.extend([vel] * len(evt.selected_notes))

    return all_notes, all_velocities


def decode_all_sections_general(syx_path, slot):
    """Decode general/bass events across all sections."""
    all_notes = []
    all_velocities = []

    for section in range(6):
        data = get_track_data(syx_path, section, slot)
        if len(data) < 28:
            continue

        preamble, bars = extract_bars(data)

        for bar_idx, (header, events) in enumerate(bars):
            note_idx = 0
            for evt_idx, evt in enumerate(events):
                result = decode_drum_event(evt, evt_idx, note_idx)
                if result is None:
                    continue
                if result["type"] == "note":
                    all_notes.append(result["note"])
                    all_velocities.append(result["velocity"])
                    note_idx += 1

    return all_notes, all_velocities


def compare_notes(decoded_notes, captured_unique, label):
    """Compare decoded note set against captured note set."""
    if not decoded_notes:
        print(f"  ⚠ No decoded notes")
        return

    decoded_unique = sorted(set(decoded_notes))
    decoded_counter = Counter(decoded_notes)
    captured_set = set(captured_unique)
    decoded_set = set(decoded_unique)

    # Note-level metrics
    intersection = decoded_set & captured_set
    only_decoded = decoded_set - captured_set
    only_captured = captured_set - decoded_set

    precision = len(intersection) / len(decoded_set) if decoded_set else 0
    recall = len(intersection) / len(captured_set) if captured_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"  Decoded unique notes:  {decoded_unique}")
    print(f"  Captured unique notes: {sorted(captured_unique)}")
    print(f"  Total decoded events:  {len(decoded_notes)}")
    print(f"  Intersection:          {sorted(intersection)}")
    if only_decoded:
        print(f"  Only in decoded:       {sorted(only_decoded)} (false positives)")
    if only_captured:
        print(f"  Only in captured:      {sorted(only_captured)} (missed)")
    print(f"  Precision: {precision:.1%}  Recall: {recall:.1%}  F1: {f1:.1%}")

    # Per-note breakdown
    print(f"\n  Per-note decoded counts:")
    for note in sorted(decoded_counter):
        marker = "✓" if note in captured_set else "✗"
        print(f"    {marker} note {note:3d}: {decoded_counter[note]:4d} events")

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "decoded_unique": decoded_unique,
        "captured_unique": sorted(captured_unique),
        "intersection": sorted(intersection),
        "false_positives": sorted(only_decoded),
        "missed": sorted(only_captured),
    }


def validate_channel(ch_str, capture_data, syx_path):
    """Validate one channel's decoder against capture."""
    slot, label = CHANNEL_SLOT_MAP[ch_str]
    ch_data = capture_data["channels"].get(ch_str)
    if not ch_data:
        print(f"  No capture data for ch{ch_str}")
        return None

    captured_unique = ch_data["unique_notes"]
    captured_count = ch_data["note_count"]

    print(f"\n{'='*65}")
    print(f"  {label} (slot {slot}) — ch{ch_str} — {captured_count} captured notes")
    print(f"{'='*65}")

    # Determine decoder based on slot
    data = get_track_data(syx_path, 0, slot)
    if len(data) < 28:
        print(f"  ⚠ No SysEx data for slot {slot} section 0")
        # Try other sections
        for s in range(1, 6):
            data = get_track_data(syx_path, s, slot)
            if len(data) >= 28:
                break

    if len(data) < 28:
        print(f"  ⚠ No SysEx data for slot {slot} in any section")
        return None

    preamble = data[24:28]
    encoding = classify_encoding(preamble)
    print(f"  Encoding: {encoding} (preamble {preamble[:2].hex()})")

    if encoding == ENCODING_DRUM_PRIMARY:
        notes, vels = decode_all_sections_drum(syx_path, slot)
    elif encoding == ENCODING_CHORD:
        notes, vels = decode_all_sections_chord(syx_path, slot)
    elif encoding in (ENCODING_GENERAL, ENCODING_BASS_SLOT):
        notes, vels = decode_all_sections_general(syx_path, slot)
    else:
        print(f"  ⚠ Unknown encoding, trying drum decoder")
        notes, vels = decode_all_sections_drum(syx_path, slot)

    result = compare_notes(notes, captured_unique, label)

    # Section breakdown
    print(f"\n  Per-section breakdown:")
    for section in range(6):
        sec_data = get_track_data(syx_path, section, slot)
        if len(sec_data) < 28:
            continue
        _, bars = extract_bars(sec_data)
        total_evts = sum(len(evts) for _, evts in bars)
        print(f"    {SECTION_NAMES[section]:10s}: {len(bars)} bars, {total_evts} raw events")

    return result


def main():
    print("=" * 65)
    print("  SGT CAPTURE VALIDATION")
    print(f"  SysEx: {SYX_PATH}")
    print(f"  Capture: {CAPTURE_PATH}")
    print("=" * 65)

    capture = load_capture()
    results = {}

    for ch_str in ["9", "10", "12", "14", "15", "11"]:
        if ch_str in CHANNEL_SLOT_MAP:
            result = validate_channel(ch_str, capture, SYX_PATH)
            if result:
                slot, label = CHANNEL_SLOT_MAP[ch_str]
                results[label] = result

    # Summary
    print(f"\n\n{'='*65}")
    print(f"  SUMMARY")
    print(f"{'='*65}")
    print(f"  {'Track':<8} {'Precision':>10} {'Recall':>8} {'F1':>8} {'FP':>4} {'Miss':>4}")
    print(f"  {'-'*46}")
    for label, r in results.items():
        fp = len(r["false_positives"])
        miss = len(r["missed"])
        print(f"  {label:<8} {r['precision']:>9.0%} {r['recall']:>7.0%} {r['f1']:>7.0%} {fp:>4} {miss:>4}")


if __name__ == "__main__":
    main()
