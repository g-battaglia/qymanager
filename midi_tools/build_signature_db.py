"""Extend `data/voice_signature_db.json` by pairing bulk `.syx` files with
`_load.json` capture streams taken at the same moment.

Usage:

    uv run python3 midi_tools/build_signature_db.py \
        --pair NAME data/captures_2026_04_23/FOO_bulk.syx data/captures_2026_04_23/FOO_load.json \
        [--pair NAME2 ... ] \
        [--output data/voice_signature_db.json] \
        [--dry-run]

For each track that has data in the bulk, the script extracts the 10-byte
voice signature at bytes 14-24 of the first section (or first section
that carries data), then resolves the active voice for that track's MIDI
channel (ch = track_index + 9) by replaying `load.json` messages in
order. The resulting `(signature → {msb, lsb, prog, voice_name,
confidence, sample_count, sources})` is merged into the DB.

Unknown/ambiguous signatures (same sig → different voices) lower the
confidence; known stable signatures at confidence 1.0 are preserved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Allow running as a script without `uv run`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qymanager.formats.qy70.sysex_parser import SysExParser
from qymanager.utils.xg_voices import get_voice_name


DEFAULT_DB = ROOT / "data" / "voice_signature_db.json"


def load_bulk_tracks(path: Path) -> Dict[int, bytes]:
    """Return `{al: bytes}` for each track address present in the bulk.

    `al = section_index * 8 + track_index`, so `al & 7` is the track.
    """
    data = path.read_bytes()
    messages = SysExParser().parse_bytes(data)
    track_sections: Dict[int, bytearray] = {}
    for msg in messages:
        if not msg.is_style_data:
            continue
        if msg.decoded_data is None:
            continue
        al = msg.address_low
        if al == 0x7F:
            continue
        buf = track_sections.setdefault(al, bytearray())
        buf.extend(msg.decoded_data)
    return {al: bytes(b) for al, b in track_sections.items() if b}


def load_voice_map(path: Path) -> Dict[int, Dict[str, int]]:
    """Return `{midi_channel_1based: {msb, lsb, prog, volume, pan, rev, cho}}`
    by replaying the pattern-load capture.

    Only CC 0 (Bank MSB), CC 32 (Bank LSB), CC 7/10/91/93, and Program
    Change are interpreted. The last value before the stream ends wins.
    """
    stream = json.loads(path.read_text())
    per_ch: Dict[int, Dict[str, Optional[int]]] = {
        ch: {
            "msb": None,
            "lsb": None,
            "prog": None,
            "volume": None,
            "pan": None,
            "reverb_send": None,
            "chorus_send": None,
        }
        for ch in range(1, 17)
    }
    for msg in stream:
        raw = msg.get("data", "")
        if not raw:
            continue
        try:
            data = bytes.fromhex(raw)
        except ValueError:
            continue
        if not data:
            continue
        status = data[0]
        high = status & 0xF0
        ch = (status & 0x0F) + 1
        if high == 0xC0 and len(data) >= 2:
            per_ch[ch]["prog"] = data[1]
        elif high == 0xB0 and len(data) >= 3:
            cc, val = data[1], data[2]
            if cc == 0:
                per_ch[ch]["msb"] = val
            elif cc == 32:
                per_ch[ch]["lsb"] = val
            elif cc == 7:
                per_ch[ch]["volume"] = val
            elif cc == 10:
                per_ch[ch]["pan"] = val
            elif cc == 91:
                per_ch[ch]["reverb_send"] = val
            elif cc == 93:
                per_ch[ch]["chorus_send"] = val

    resolved: Dict[int, Dict[str, int]] = {}
    for ch, fields in per_ch.items():
        if fields["prog"] is None and fields["msb"] is None and fields["lsb"] is None:
            continue
        resolved[ch] = {
            "msb": fields["msb"] or 0,
            "lsb": fields["lsb"] or 0,
            "prog": fields["prog"] or 0,
            "volume": fields["volume"] if fields["volume"] is not None else 100,
            "pan": fields["pan"] if fields["pan"] is not None else 64,
            "reverb_send": fields["reverb_send"]
            if fields["reverb_send"] is not None
            else 40,
            "chorus_send": fields["chorus_send"]
            if fields["chorus_send"] is not None
            else 0,
        }
    return resolved


def first_signature_per_track(tracks: Dict[int, bytes]) -> Dict[int, str]:
    """`track_idx → sig10_hex` using the first section that carries data.

    Per track a signature is the first 10 bytes at offset 14..24 of the
    track data. A track stored across multiple sections should keep a
    stable voice, so the first occurrence wins.
    """
    out: Dict[int, str] = {}
    for al in sorted(tracks):
        track_idx = al & 7
        if track_idx in out:
            continue
        blob = tracks[al]
        if len(blob) < 24:
            continue
        out[track_idx] = blob[14:24].hex()
    return out


def pair_to_entries(
    name: str,
    bulk_path: Path,
    load_path: Path,
) -> List[Tuple[str, Dict[str, object]]]:
    """Return `[(sig10_hex, entry)]` harvested from this pair."""
    tracks = load_bulk_tracks(bulk_path)
    voices = load_voice_map(load_path)
    sigs = first_signature_per_track(tracks)

    entries: List[Tuple[str, Dict[str, object]]] = []
    for track_idx, sig_hex in sigs.items():
        midi_ch = track_idx + 9
        voice = voices.get(midi_ch)
        if voice is None:
            continue
        msb, lsb, prog = voice["msb"], voice["lsb"], voice["prog"]
        is_drum = msb == 127
        is_sfx = msb == 126 or msb == 64
        if is_drum:
            voice_name = f"Drum Kit {prog}"
        elif is_sfx:
            voice_name = f"SFX Kit {prog}"
        else:
            voice_name = get_voice_name(prog, msb, lsb) or f"Voice {msb}/{lsb}/{prog}"
        entries.append(
            (
                sig_hex,
                {
                    "msb": msb,
                    "lsb": lsb,
                    "prog": prog,
                    "voice_name": voice_name,
                    "volume": voice["volume"],
                    "pan": voice["pan"],
                    "reverb_send": voice["reverb_send"],
                    "chorus_send": voice["chorus_send"],
                    "source": name,
                    "track_index": track_idx,
                    "midi_channel": midi_ch,
                },
            )
        )
    return entries


def merge_into_db(
    db: Dict[str, Dict[str, object]],
    entries: List[Tuple[str, Dict[str, object]]],
) -> Dict[str, int]:
    """Mutate `db` merging new samples. Returns counters."""
    stats = {"added": 0, "reinforced": 0, "conflict": 0, "total": 0}
    for sig, info in entries:
        stats["total"] += 1
        existing = db.get(sig)
        msb, lsb, prog = info["msb"], info["lsb"], info["prog"]
        if existing is None:
            db[sig] = {
                "msb": msb,
                "lsb": lsb,
                "prog": prog,
                "confidence": 1.0,
                "sample_count": 1,
                "voice_name": info["voice_name"],
                "sources": [info["source"]],
            }
            stats["added"] += 1
            continue
        same = (
            existing.get("msb") == msb
            and existing.get("lsb") == lsb
            and existing.get("prog") == prog
        )
        if same:
            existing["sample_count"] = int(existing.get("sample_count", 1)) + 1
            existing.setdefault("sources", [])
            src_list = existing["sources"]
            if isinstance(src_list, list) and info["source"] not in src_list:
                src_list.append(info["source"])
            if not existing.get("voice_name"):
                existing["voice_name"] = info["voice_name"]
            existing["confidence"] = min(1.0, float(existing.get("confidence", 1.0)))
            stats["reinforced"] += 1
        else:
            existing["sample_count"] = int(existing.get("sample_count", 1)) + 1
            existing["confidence"] = max(0.0, float(existing.get("confidence", 1.0)) * 0.5)
            existing.setdefault("alternates", [])
            alt_list = existing["alternates"]
            if isinstance(alt_list, list):
                alt = {
                    "msb": msb,
                    "lsb": lsb,
                    "prog": prog,
                    "voice_name": info["voice_name"],
                    "source": info["source"],
                }
                if alt not in alt_list:
                    alt_list.append(alt)
            stats["conflict"] += 1
    return stats


def pair_to_entries_manual(
    name: str,
    bulk_path: Path,
    voices_by_channel: Dict[int, Dict[str, int]],
) -> List[Tuple[str, Dict[str, object]]]:
    """Same as `pair_to_entries` but voices come from an inline dict.

    Useful when there is no `_load.json` capture but the pattern's voice
    assignments are documented elsewhere (wiki / capture log).
    `voices_by_channel` uses 1-based MIDI channels (9..16 for QY70).
    Each entry: `{msb, lsb, prog, volume?, pan?, reverb_send?, chorus_send?}`.
    """
    tracks = load_bulk_tracks(bulk_path)
    sigs = first_signature_per_track(tracks)

    entries: List[Tuple[str, Dict[str, object]]] = []
    for track_idx, sig_hex in sigs.items():
        midi_ch = track_idx + 9
        voice = voices_by_channel.get(midi_ch)
        if voice is None:
            continue
        msb, lsb, prog = voice["msb"], voice["lsb"], voice["prog"]
        is_drum = msb == 127
        is_sfx = msb == 126 or msb == 64
        if is_drum:
            voice_name = f"Drum Kit {prog}"
        elif is_sfx:
            voice_name = f"SFX Kit {prog}"
        else:
            voice_name = get_voice_name(prog, msb, lsb) or f"Voice {msb}/{lsb}/{prog}"
        entries.append(
            (
                sig_hex,
                {
                    "msb": msb,
                    "lsb": lsb,
                    "prog": prog,
                    "voice_name": voice_name,
                    "volume": voice.get("volume", 100),
                    "pan": voice.get("pan", 64),
                    "reverb_send": voice.get("reverb_send", 40),
                    "chorus_send": voice.get("chorus_send", 0),
                    "source": name,
                    "track_index": track_idx,
                    "midi_channel": midi_ch,
                },
            )
        )
    return entries


def pair_to_entries_embedded(
    name: str, bulk_path: Path
) -> List[Tuple[str, Dict[str, object]]]:
    """Extract (signature, voice) pairs from a bulk that already carries
    an XG Multi Part bulk block inside itself (AH=0x08 AM=part AL=field).

    This is the zero-configuration path: no load.json, no manual
    voices dict. SyxAnalyzer already decodes the embedded XG state
    into `analysis.xg_voices`; we re-use that as ground truth.
    """
    # Local import so the CLI help output doesn't depend on syx_analyzer
    from qymanager.analysis.syx_analyzer import SyxAnalyzer

    tracks = load_bulk_tracks(bulk_path)
    sigs = first_signature_per_track(tracks)

    analysis = SyxAnalyzer().analyze_file(str(bulk_path))
    xg_voices = getattr(analysis, "xg_voices", {}) or {}
    if not xg_voices:
        return []

    entries: List[Tuple[str, Dict[str, object]]] = []
    for track_idx, sig_hex in sigs.items():
        # QY70 track_idx 0..7 ↔ XG Multi Part index 8..15 (ch 9..16)
        part_idx = track_idx + 8
        fields = xg_voices.get(part_idx)
        if not fields:
            continue
        msb = fields.get("bank_msb", 0) or 0
        lsb = fields.get("bank_lsb", 0) or 0
        prog = fields.get("program", 0) or 0
        if msb == 0 and lsb == 0 and prog == 0:
            continue  # empty part
        is_drum = msb == 127
        is_sfx = msb == 126 or msb == 64
        if is_drum:
            voice_name = f"Drum Kit {prog}"
        elif is_sfx:
            voice_name = f"SFX Kit {prog}"
        else:
            voice_name = get_voice_name(prog, msb, lsb) or f"Voice {msb}/{lsb}/{prog}"
        entries.append(
            (
                sig_hex,
                {
                    "msb": msb,
                    "lsb": lsb,
                    "prog": prog,
                    "voice_name": voice_name,
                    "volume": fields.get("volume", 100),
                    "pan": fields.get("pan", 64),
                    "reverb_send": fields.get("reverb", 40),
                    "chorus_send": fields.get("chorus", 0),
                    "source": name,
                    "track_index": track_idx,
                    "midi_channel": track_idx + 9,
                },
            )
        )
    return entries


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pair",
        action="append",
        nargs=3,
        default=[],
        metavar=("NAME", "BULK_SYX", "LOAD_JSON"),
        help="repeatable: source label + bulk .syx + load .json",
    )
    parser.add_argument(
        "--manual",
        action="append",
        nargs=3,
        default=[],
        metavar=("NAME", "BULK_SYX", "VOICES_JSON"),
        help=(
            "repeatable: bulk + a JSON with `{\"9\": {\"msb\":..,\"lsb\":..,"
            "\"prog\":..}, \"10\": ..., ...}` for wiki-documented pairs that "
            "don't have a `_load.json` capture"
        ),
    )
    parser.add_argument(
        "--embedded",
        action="append",
        nargs=2,
        default=[],
        metavar=("NAME", "BULK_SYX"),
        help=(
            "repeatable: a bulk that embeds XG Multi Part block inside "
            "itself (SGT_backup-style). Voice mapping is pulled straight "
            "out of `SyxAnalyzer.xg_voices`, no external ground truth "
            "needed"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DB,
        help="Path to voice_signature_db.json (default: data/voice_signature_db.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the merge plan but do not write the DB",
    )
    args = parser.parse_args(argv)
    if not args.pair and not args.manual and not args.embedded:
        parser.error("need at least one --pair, --manual or --embedded")

    db: Dict[str, Dict[str, object]] = {}
    if args.output.exists():
        try:
            db = json.loads(args.output.read_text())
        except json.JSONDecodeError:
            print(f"! existing {args.output} is not JSON — starting fresh", file=sys.stderr)

    before = len(db)
    totals = {"added": 0, "reinforced": 0, "conflict": 0, "total": 0}
    for name, bulk, load in args.pair:
        entries = pair_to_entries(name, Path(bulk), Path(load))
        s = merge_into_db(db, entries)
        print(
            f"{name:10s} {len(entries):3d} tracks  "
            f"added={s['added']} reinforced={s['reinforced']} conflict={s['conflict']}"
        )
        for k, v in s.items():
            totals[k] = totals.get(k, 0) + v
    for name, bulk in args.embedded:
        entries = pair_to_entries_embedded(name, Path(bulk))
        if not entries:
            print(
                f"! {name}: no embedded XG Multi Part block found in {bulk}",
                file=sys.stderr,
            )
            continue
        s = merge_into_db(db, entries)
        print(
            f"{name:10s} {len(entries):3d} tracks  "
            f"added={s['added']} reinforced={s['reinforced']} conflict={s['conflict']}  [embedded]"
        )
        for k, v in s.items():
            totals[k] = totals.get(k, 0) + v

    for name, bulk, voices_json in args.manual:
        try:
            raw = json.loads(Path(voices_json).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"! {name}: cannot read {voices_json}: {exc}", file=sys.stderr)
            continue
        voices = {
            int(k): v
            for k, v in raw.items()
            if not k.startswith("_") and k.isdigit()
        }
        entries = pair_to_entries_manual(name, Path(bulk), voices)
        s = merge_into_db(db, entries)
        print(
            f"{name:10s} {len(entries):3d} tracks  "
            f"added={s['added']} reinforced={s['reinforced']} conflict={s['conflict']}  [manual]"
        )
        for k, v in s.items():
            totals[k] = totals.get(k, 0) + v

    after = len(db)
    print("---")
    print(f"DB entries: {before} → {after}  (+{after - before})")
    print(
        f"samples seen: {totals['total']}  "
        f"added={totals['added']} reinforced={totals['reinforced']} conflict={totals['conflict']}"
    )

    if args.dry_run:
        print("dry-run: not writing DB")
        return 0

    args.output.write_text(json.dumps(db, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
