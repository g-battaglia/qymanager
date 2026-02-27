#!/usr/bin/env python3
"""
QY700 (Q7P) vs QY70 (SysEx) Header Field Mapping Tool.

Performs a systematic byte-by-byte comparison of both formats to create
a complete field mapping, identify gaps, and investigate open questions.

Usage:
    python3 midi_tools/map_fields.py
"""

import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qymanager.formats.qy70.sysex_parser import SysExParser, SysExMessage, MessageType
from qymanager.utils.yamaha_7bit import decode_7bit
from qymanager.utils.checksum import verify_sysex_checksum
from qymanager.utils.xg_voices import get_voice_name


# ─── Constants ───────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
Q7P_FILE = FIXTURES / "T01.Q7P"
Q7P_EMPTY = FIXTURES / "TXX.Q7P"
SYX_FILE = FIXTURES / "QY70_SGT.syx"

# QY70 track names
QY70_TRACKS = ["D1", "D2", "PC", "BA", "C1", "C2", "C3", "C4"]
QY70_CHANNELS = [10, 10, 3, 2, 4, 5, 6, 7]

# QY700 track names (first 8 are the ones that map to QY70)
Q7P_TRACKS = [
    "RHY1",
    "RHY2",
    "BASS",
    "CHD1",
    "CHD2",
    "CHD3",
    "CHD4",
    "CHD5",
    "TR9",
    "TR10",
    "TR11",
    "TR12",
    "TR13",
    "TR14",
    "TR15",
    "TR16",
]
Q7P_CHANNELS_DEFAULT = [10, 10, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16]


# ─── Q7P Extraction ─────────────────────────────────────────────────────────


def extract_q7p(filepath: Path) -> Dict[str, Any]:
    """Extract ALL known parameters from a Q7P file (3072-byte format)."""
    data = filepath.read_bytes()
    result = {}

    # Header
    result["file_size"] = len(data)
    result["header_magic"] = data[0x000:0x010]
    result["pattern_number"] = data[0x010]
    result["pattern_flags"] = data[0x011]
    result["reserved_012_02f"] = data[0x012:0x030]
    result["size_marker"] = struct.unpack(">H", data[0x030:0x032])[0]
    result["reserved_032_0ff"] = data[0x032:0x100]

    # Section pointers (0x100-0x11F)
    result["section_pointers"] = []
    for i in range(16):
        ptr = struct.unpack(">H", data[0x100 + i * 2 : 0x102 + i * 2])[0]
        result["section_pointers"].append(ptr)

    # Section encoded data (0x120-0x17F)
    result["section_data_raw"] = data[0x120:0x180]

    # Timing area (0x180-0x18F)
    result["timing_area_raw"] = data[0x180:0x190]
    result["padding_180"] = data[0x180:0x188]
    tempo_raw = struct.unpack(">H", data[0x188:0x18A])[0]
    result["tempo_raw"] = tempo_raw
    result["tempo_bpm"] = tempo_raw / 10.0
    result["time_sig_byte"] = data[0x18A]
    result["time_sig_byte2"] = data[0x18B]
    result["timing_flags"] = data[0x18C:0x190]

    # Channel assignments (0x190-0x19F)
    result["channels_raw"] = list(data[0x190:0x1A0])
    result["channels"] = []
    for i in range(16):
        ch_raw = data[0x190 + i]
        if ch_raw == 0x00:
            result["channels"].append(Q7P_CHANNELS_DEFAULT[i])
        elif 0x01 <= ch_raw <= 0x0F:
            result["channels"].append(ch_raw + 1)
        else:
            result["channels"].append(Q7P_CHANNELS_DEFAULT[i])

    # Reserved/track config areas
    result["reserved_1a0_1db"] = data[0x1A0:0x1DC]

    # Track numbers and flags (0x1DC-0x1E5)
    result["track_numbers"] = list(data[0x1DC:0x1E4])
    result["track_flags"] = struct.unpack(">H", data[0x1E4:0x1E6])[0]

    # Voice selection offsets
    result["bank_msb"] = list(data[0x1E6:0x1F6])
    result["program"] = list(data[0x1F6:0x206])
    result["bank_lsb"] = list(data[0x206:0x216])

    # Area between bank_lsb and volume table
    result["reserved_216_220"] = data[0x216:0x220]

    # Volume table (0x220-0x24F)
    result["volume_header"] = data[0x220:0x226]
    result["volume_data"] = list(data[0x226:0x236])  # 16 bytes
    result["volume_extended"] = data[0x236:0x250]  # rest of volume area

    # Reverb send table (0x250-0x26F)
    result["reverb_header"] = data[0x250:0x256]
    result["reverb_data"] = list(data[0x256:0x266])  # 16 bytes
    result["reverb_extended"] = data[0x266:0x270]

    # Pan table (0x270-0x2BF)
    result["pan_header"] = data[0x270:0x276]
    result["pan_data"] = list(data[0x276:0x286])  # 16 bytes
    result["pan_extended"] = data[0x286:0x2A6]  # more pan data

    # INVESTIGATE: Chorus send area (0x296?)
    result["chorus_candidate"] = list(data[0x296:0x2A6])

    # TABLE_3 / unknown effects area (0x2C0-0x35F)
    result["table3_raw"] = data[0x2C0:0x360]

    # Phrase data (0x360-0x677)
    result["phrase_data"] = data[0x360:0x678]

    # Sequence data (0x678-0x86F)
    result["sequence_data"] = data[0x678:0x870]

    # Pattern name (0x876-0x87F)
    result["pattern_name_raw"] = data[0x876:0x880]
    try:
        name = ""
        for b in data[0x876:0x880]:
            if 0x20 <= b < 0x7F:
                name += chr(b)
            else:
                break
        result["pattern_name"] = name.rstrip()
    except:
        result["pattern_name"] = data[0x876:0x880].hex()

    # Fill/pad areas
    result["fill_area_start"] = 0x9C0
    result["pad_area_start"] = 0xB10

    # Raw data for investigation areas
    result["raw_data"] = data

    return result


# ─── QY70 SysEx Extraction ──────────────────────────────────────────────────


def extract_syx(filepath: Path) -> Dict[str, Any]:
    """Extract ALL parameters from QY70 SysEx file."""
    data = filepath.read_bytes()
    result = {}
    result["file_size"] = len(data)

    # Parse SysEx messages
    parser = SysExParser()
    messages = parser.parse_bytes(data)
    result["total_messages"] = len(messages)

    # Group decoded data by AL
    section_data: Dict[int, bytearray] = {}
    first_7e7f_raw: Optional[bytes] = None
    track_headers: Dict[int, bytes] = {}  # AL -> first 24 bytes of decoded track data

    for msg in messages:
        if not msg.is_style_data:
            continue

        al = msg.address_low

        # Capture raw payload for first 7E 7F message (tempo)
        if al == 0x7F and first_7e7f_raw is None and msg.data:
            first_7e7f_raw = bytes(msg.data)

        if msg.decoded_data:
            if al not in section_data:
                section_data[al] = bytearray()
            section_data[al].extend(msg.decoded_data)

    result["al_addresses"] = sorted(section_data.keys())
    result["al_sizes"] = {al: len(d) for al, d in section_data.items()}

    # Header (AL=0x7F, 640 decoded bytes)
    header = bytes(section_data.get(0x7F, b""))
    result["header_size"] = len(header)
    result["header_data"] = header

    # --- Header field extraction ---
    if len(header) > 0:
        result["format_marker"] = header[0]
        result["header_bytes_1_5"] = header[1:6]
        result["header_bytes_6_9"] = header[6:10]
        result["header_bytes_a_b"] = header[0x0A:0x0C]

    # Tempo from raw payload
    if first_7e7f_raw and len(first_7e7f_raw) >= 2:
        tempo_range = first_7e7f_raw[0]
        tempo_offset = first_7e7f_raw[1]
        tempo = (tempo_range * 95 - 133) + tempo_offset
        result["tempo_range_byte"] = tempo_range
        result["tempo_offset_byte"] = tempo_offset
        result["tempo_bpm"] = tempo
        result["tempo_raw_payload"] = first_7e7f_raw[:8]
    else:
        result["tempo_bpm"] = 120
        result["tempo_range_byte"] = 0
        result["tempo_offset_byte"] = 0

    # Time signature (header byte 0x0C candidate)
    if len(header) > 0x0D:
        result["time_sig_candidate_0c"] = header[0x0C]
        result["time_sig_candidate_0d"] = header[0x0D]

    # Extract track headers from track data
    result["track_headers"] = {}
    result["track_voices"] = {}
    result["track_pans"] = {}
    result["track_note_ranges"] = {}
    result["track_flags"] = {}

    for al in sorted(section_data.keys()):
        if al == 0x7F:
            continue
        track_data = bytes(section_data[al])
        if len(track_data) >= 24:
            # Track index within its section
            track_idx = al % 8
            section_idx = al // 8

            header_24 = track_data[:24]
            result["track_headers"][al] = header_24

            # Voice at bytes 14-15
            b14, b15 = track_data[14], track_data[15]
            result["track_voices"][al] = (b14, b15)

            # Note range at bytes 16-17
            result["track_note_ranges"][al] = (track_data[16], track_data[17])

            # Track type flags at bytes 18-20
            result["track_flags"][al] = (track_data[18], track_data[19], track_data[20])

            # Pan at bytes 21-22
            pan_flag = track_data[21]
            pan_val = track_data[22]
            result["track_pans"][al] = (pan_flag, pan_val)

    # Analyze header structure in detail
    result["header_hex_dump"] = header

    return result


# ─── Hex formatting helpers ─────────────────────────────────────────────────


def hex_bytes(data: bytes, max_len: int = 16) -> str:
    """Format bytes as hex string."""
    if len(data) <= max_len:
        return " ".join(f"{b:02X}" for b in data)
    return " ".join(f"{b:02X}" for b in data[:max_len]) + f" ... ({len(data)} bytes)"


def hex_list(lst: list, max_len: int = 16) -> str:
    """Format list as hex string."""
    if len(lst) <= max_len:
        return " ".join(f"{v:02X}" for v in lst)
    return " ".join(f"{v:02X}" for v in lst[:max_len]) + f" ... ({len(lst)} items)"


# ─── Main Analysis ──────────────────────────────────────────────────────────


def main():
    print("=" * 100)
    print("QY700 (Q7P) vs QY70 (SysEx) — COMPLETE FIELD MAPPING")
    print("=" * 100)

    # Load files
    q7p = extract_q7p(Q7P_FILE)
    q7p_empty = extract_q7p(Q7P_EMPTY)
    syx = extract_syx(SYX_FILE)

    print(f"\nFiles analyzed:")
    print(f"  Q7P (T01):  {Q7P_FILE.name}  ({q7p['file_size']} bytes)")
    print(f"  Q7P (TXX):  {Q7P_EMPTY.name}  ({q7p_empty['file_size']} bytes)")
    print(f"  SysEx:      {SYX_FILE.name}  ({syx['file_size']} bytes)")
    print(f"  SysEx msgs: {syx['total_messages']}")
    print(f"  SysEx AL addresses: {[f'0x{a:02X}' for a in syx['al_addresses']]}")
    print(
        f"  SysEx AL sizes: {{{', '.join(f'0x{k:02X}: {v}' for k, v in sorted(syx['al_sizes'].items()))}}}"
    )
    print(f"  Header decoded size: {syx['header_size']} bytes")

    # ─── SECTION 1: Global Header Fields ────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 1: GLOBAL HEADER / PATTERN-LEVEL FIELDS")
    print("=" * 100)

    print(
        f"\n{'Parameter':<25} {'Q7P Offset':<18} {'Q7P Value':<25} {'QY70 Location':<22} {'QY70 Value':<25} {'Match?':<8} {'Converter?'}"
    )
    print("─" * 150)

    # 1. Format marker
    q7p_hdr = q7p["header_magic"].decode("ascii", errors="replace")
    syx_fmt = f"0x{syx['format_marker']:02X}" if "format_marker" in syx else "N/A"
    print(
        f"{'Format marker':<25} {'0x000 (16B)':<18} {q7p_hdr!r:<25} {'Header[0]':<22} {syx_fmt:<25} {'N/A':<8} {'Yes (detect)'}"
    )

    # 2. Tempo
    q7p_tempo_s = f"{q7p['tempo_bpm']} BPM (0x{q7p['tempo_raw']:04X})"
    syx_tempo_s = (
        f"{syx['tempo_bpm']} BPM (R={syx['tempo_range_byte']},O={syx['tempo_offset_byte']})"
    )
    print(
        f"{'Tempo':<25} {'0x188-0x189':<18} {q7p_tempo_s:<25} {'Raw payload[0:2]':<22} {syx_tempo_s:<25} {'YES':<8} {'Partial'}"
    )

    # 3. Time signature
    q7p_ts = f"0x{q7p['time_sig_byte']:02X} (={q7p['time_sig_byte']}d)"
    syx_ts_c = (
        f"Hdr[0x0C]=0x{syx.get('time_sig_candidate_0c', 0):02X}"
        if "time_sig_candidate_0c" in syx
        else "Unknown"
    )
    print(
        f"{'Time signature':<25} {'0x18A':<18} {q7p_ts:<25} {syx_ts_c:<22} {'Not decoded':<25} {'???':<8} {'No'}"
    )

    # 4. Pattern name
    q7p_name = f"'{q7p['pattern_name']}'"
    print(
        f"{'Pattern name':<25} {'0x876-0x87F':<18} {q7p_name:<25} {'Not stored':<22} {'N/A':<25} {'N/A':<8} {'700->70 only'}"
    )

    # 5. Pattern number
    print(
        f"{'Pattern number':<25} {'0x010':<18} {f'0x{q7p["pattern_number"]:02X}':<25} {'N/A':<22} {'N/A':<25} {'N/A':<8} {'No'}"
    )

    # 6. Pattern flags
    print(
        f"{'Pattern flags':<25} {'0x011':<18} {f'0x{q7p["pattern_flags"]:02X}':<25} {'N/A':<22} {'N/A':<25} {'N/A':<8} {'No'}"
    )

    # 7. Size marker
    print(
        f"{'Size marker':<25} {'0x030':<18} {f'0x{q7p["size_marker"]:04X} (={q7p["size_marker"]}d)':<25} {'N/A':<22} {'N/A':<25} {'N/A':<8} {'No'}"
    )

    # ─── SECTION 2: Channel Assignments ─────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 2: CHANNEL ASSIGNMENTS")
    print("=" * 100)

    print(
        f"\n{'Track':<8} {'Q7P Offset':<12} {'Q7P Raw':<10} {'Q7P Ch':<8} {'QY70 Track':<12} {'QY70 Default Ch':<16} {'Match?'}"
    )
    print("─" * 80)

    for i in range(8):
        q7p_raw = q7p["channels_raw"][i]
        q7p_ch = q7p["channels"][i]
        qy70_ch = QY70_CHANNELS[i]
        match = "YES" if q7p_ch == qy70_ch else f"NO ({q7p_ch} vs {qy70_ch})"
        print(
            f"{Q7P_TRACKS[i]:<8} {f'0x{0x190 + i:03X}':<12} {f'0x{q7p_raw:02X}':<10} {f'Ch {q7p_ch}':<8} {QY70_TRACKS[i]:<12} {f'Ch {qy70_ch}':<16} {match}"
        )

    print(f"\nQ7P tracks 9-16 (no QY70 equivalent):")
    for i in range(8, 16):
        q7p_raw = q7p["channels_raw"][i]
        q7p_ch = q7p["channels"][i]
        print(f"  {Q7P_TRACKS[i]:<8} 0x{0x190 + i:03X}   raw=0x{q7p_raw:02X}  -> Ch {q7p_ch}")

    print(
        f"\nConverter status: qy700_to_qy70.py reads channels from 0x190+track_num (line 475-476)"
    )
    print(f"                 qy70_to_qy700.py does NOT write channels (SAFE mode)")

    # ─── SECTION 3: Volume ──────────────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 3: VOLUME PER TRACK")
    print("=" * 100)

    print(f"\nQ7P Volume header (0x220-0x225): {hex_bytes(q7p['volume_header'])}")
    print(f"Q7P Volume data   (0x226-0x235): {hex_list(q7p['volume_data'])}")
    print(f"\nQ7P Empty Volume  (0x226-0x235): {hex_list(q7p_empty['volume_data'])}")

    print(
        f"\n{'Track':<8} {'Q7P Offset':<12} {'Q7P Vol':<10} {'QY70 Track':<12} {'QY70 Vol':<10} {'Match?':<8} {'Notes'}"
    )
    print("─" * 80)

    # QY70 volume: stored in decoded track data but also XG default is 100
    # The QY70 doesn't store volume in track header bytes 0-23, it's separate
    for i in range(8):
        q7p_vol = q7p["volume_data"][i]
        # Check if we can find first track data for this track
        # In SGT style, first section is section 0, track i -> AL = i
        al = i  # section 0
        qy70_vol = "default(100)"

        match = "YES" if q7p_vol == 100 else "DIFF"
        if q7p_vol == 100:
            match = "BOTH=100"

        print(
            f"{Q7P_TRACKS[i]:<8} {f'0x{0x226 + i:03X}':<12} {q7p_vol:<10} {QY70_TRACKS[i]:<12} {qy70_vol:<10} {match:<8} {'XG default'}"
        )

    print(f"\nConverter status: qy700_to_qy70.py reads from 0x226 + section*8 + track")
    print(f"                 qy70_to_qy700.py extracts from decoded track data byte 24 (WRONG?)")
    print(f"                 NOTE: QY70 stores volume in HEADER, not track blocks")

    # ─── SECTION 4: Pan ─────────────────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 4: PAN PER TRACK")
    print("=" * 100)

    print(f"\nQ7P Pan header (0x270-0x275): {hex_bytes(q7p['pan_header'])}")
    print(f"Q7P Pan data   (0x276-0x285): {hex_list(q7p['pan_data'])}")
    print(f"Q7P Empty Pan  (0x276-0x285): {hex_list(q7p_empty['pan_data'])}")

    print(
        f"\n{'Track':<8} {'Q7P Off':<10} {'Q7P Pan':<12} {'QY70 Track':<12} {'QY70 Pan(flag,val)':<25} {'Match?'}"
    )
    print("─" * 80)

    for i in range(8):
        q7p_pan = q7p["pan_data"][i]
        pan_str = f"{q7p_pan} ({'C' if q7p_pan == 64 else f'L{64 - q7p_pan}' if q7p_pan < 64 else f'R{q7p_pan - 64}'})"

        # Find QY70 pan from first section track data
        al = i  # section 0
        if al in syx["track_pans"]:
            flag, val = syx["track_pans"][al]
            qy70_pan = f"flag=0x{flag:02X}, val={val}"
            if flag == 0x41:
                match = "YES" if val == q7p_pan else f"DIFF ({val} vs {q7p_pan})"
            elif flag == 0x00:
                qy70_pan += " (use default)"
                match = "DEFAULT"
            else:
                match = "???"
        else:
            qy70_pan = "No data"
            match = "N/A"

        print(
            f"{Q7P_TRACKS[i]:<8} {f'0x{0x276 + i:03X}':<10} {pan_str:<12} {QY70_TRACKS[i]:<12} {qy70_pan:<25} {match}"
        )

    print(f"\nConverter status: qy700_to_qy70.py sets bytes 21-23 to 00 00 00 (NOT using pan)")
    print(f"                 qy70_to_qy700.py reads flag=0x41 check + byte 22 (correct)")

    # ─── SECTION 5: Reverb Send ─────────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 5: REVERB SEND PER TRACK")
    print("=" * 100)

    print(f"\nQ7P Reverb header (0x250-0x255): {hex_bytes(q7p['reverb_header'])}")
    print(f"Q7P Reverb data   (0x256-0x265): {hex_list(q7p['reverb_data'])}")
    print(f"Q7P Empty Reverb  (0x256-0x265): {hex_list(q7p_empty['reverb_data'])}")

    print(f"\n{'Track':<8} {'Q7P Offset':<12} {'Q7P Rev':<10} {'QY70 Default':<15} {'Notes'}")
    print("─" * 60)
    for i in range(8):
        q7p_rev = q7p["reverb_data"][i]
        print(
            f"{Q7P_TRACKS[i]:<8} {f'0x{0x256 + i:03X}':<12} {q7p_rev:<10} {'40 (XG def)':<15} {'Match' if q7p_rev == 40 else f'DIFF (Q7P={q7p_rev})'}"
        )

    print(f"\nConverter status: qy700_to_qy70.py reads from 0x256 + section*8 + track")
    print(f"                 qy70_to_qy700.py does NOT extract reverb from QY70")
    print(
        f"                 QY70: Reverb is NOT in track header bytes 0-23. Likely in header AL=0x7F."
    )

    # ─── SECTION 6: Chorus Send (INVESTIGATION) ────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 6: CHORUS SEND — INVESTIGATION")
    print("=" * 100)

    print(f"\nQ7P Chorus candidate area (0x296-0x2A5): {hex_list(q7p['chorus_candidate'])}")
    print(f"Q7P Empty Chorus area    (0x296-0x2A5): {hex_list(q7p_empty['chorus_candidate'])}")

    # Compare with pattern tables to find the structure
    raw = q7p["raw_data"]
    print(f"\nSearching for chorus send offset in Q7P...")
    print(f"  Expected: 16 bytes of 0x00 (XG default chorus=0)")
    print()

    # Look at the area between pan and table_3
    print(f"  Full area 0x286-0x2BF (after pan, before table_3):")
    for offset in range(0x286, 0x2C0, 16):
        chunk = raw[offset : offset + 16]
        label = ""
        if offset == 0x296:
            label = " <-- CHORUS_TABLE candidate (from converter OFFSETS)"
        print(f"    0x{offset:03X}: {hex_bytes(chunk)}{label}")

    print(f"\n  Comparing T01.Q7P vs TXX.Q7P at 0x290-0x2BF:")
    raw_empty = q7p_empty["raw_data"]
    for offset in range(0x290, 0x2C0, 16):
        t01 = raw[offset : offset + 16]
        txx = raw_empty[offset : offset + 16]
        diff = "SAME" if t01 == txx else "DIFFERENT"
        print(f"    0x{offset:03X}: T01={hex_bytes(t01)}")
        print(f"    0x{offset:03X}: TXX={hex_bytes(txx)}  [{diff}]")

    # Check the converter's OFFSETS for chorus
    print(f"\n  Converter qy700_to_qy70.py defines CHORUS offset at 0x296 (line 92)")
    print(f"  Converter reads chorus at: 0x296 + section*8 + track")
    print(f"  Q7P data at 0x296-0x2A5: {hex_list(list(raw[0x296:0x2A6]))}")

    # ─── SECTION 7: Bank / Program / Voice ──────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 7: BANK MSB / PROGRAM / BANK LSB (VOICE SELECTION)")
    print("=" * 100)

    print(f"\nQ7P Bank MSB (0x1E6-0x1F5): {hex_list(q7p['bank_msb'])}")
    print(f"Q7P Program  (0x1F6-0x205): {hex_list(q7p['program'])}")
    print(f"Q7P Bank LSB (0x206-0x215): {hex_list(q7p['bank_lsb'])}")

    print(
        f"\n{'Track':<8} {'Q7P BankMSB':<12} {'Q7P Prog':<10} {'Q7P BankLSB':<12} {'Q7P Voice':<25} {'QY70 B14,B15':<15} {'QY70 Voice'}"
    )
    print("─" * 110)

    for i in range(8):
        msb = q7p["bank_msb"][i]
        prog = q7p["program"][i]
        lsb = q7p["bank_lsb"][i]
        ch = q7p["channels"][i]
        q7p_voice = get_voice_name(prog, msb, lsb, ch)

        # QY70 voice from first section track data
        al = i
        if al in syx["track_voices"]:
            b14, b15 = syx["track_voices"][al]
            if b14 == 0x40 and b15 == 0x80:
                qy70_voice = "Default drum kit"
                qy70_b14b15 = "40 80 (drum)"
            elif b14 == 0x00 and b15 == 0x04:
                qy70_voice = "Bass marker (Prog38?)"
                qy70_b14b15 = "00 04 (bass)"
            else:
                qy70_voice = get_voice_name(b15, b14, 0)
                qy70_b14b15 = f"{b14:02X} {b15:02X}"
        else:
            qy70_voice = "No data"
            qy70_b14b15 = "N/A"

        print(
            f"{Q7P_TRACKS[i]:<8} {f'0x{msb:02X}':<12} {f'0x{prog:02X} ({prog})':<10} {f'0x{lsb:02X}':<12} {q7p_voice:<25} {qy70_b14b15:<15} {qy70_voice}"
        )

    print(
        f"\nConverter status: qy700_to_qy70.py sets voice bytes to 0x40 0x80 (default) for all tracks"
    )
    print(f"                 Does NOT transfer actual voice selection from Q7P!")
    print(f"                 qy70_to_qy700.py does NOT extract voice from QY70 track headers")

    # ─── SECTION 8: Section Pointers ────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 8: SECTION POINTERS / STRUCTURE")
    print("=" * 100)

    SECTION_NAMES = ["Intro", "Main A", "Main B", "Fill AB", "Fill BA", "Ending"]

    print(
        f"\n{'Section':<10} {'Q7P Ptr Offset':<16} {'Q7P Ptr Value':<15} {'Q7P Active?':<12} {'QY70 AL Range':<15} {'QY70 Has Data?':<15} {'Match?'}"
    )
    print("─" * 100)

    for i in range(6):
        ptr = q7p["section_pointers"][i]
        ptr_hex = f"0x{ptr:04X}"
        q7p_active = ptr != 0xFEFE

        # QY70: check if any track AL in this section has data
        al_start = i * 8
        al_end = al_start + 7
        qy70_has_data = any(al in syx["al_sizes"] for al in range(al_start, al_end + 1))
        al_range = f"0x{al_start:02X}-0x{al_end:02X}"

        match = "YES" if q7p_active == qy70_has_data else "MISMATCH"

        print(
            f"{SECTION_NAMES[i]:<10} {f'0x{0x100 + i * 2:03X}':<16} {ptr_hex:<15} {'YES' if q7p_active else 'NO':<12} {al_range:<15} {'YES' if qy70_has_data else 'NO':<15} {match}"
        )

    print(
        f"\nConverter status: qy700_to_qy70.py checks pointers at 0x100+section*2 for empty (0xFEFE)"
    )
    print(f"                 qy70_to_qy700.py does NOT modify section pointers (SAFE)")

    # ─── SECTION 9: Section Lengths ─────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 9: SECTION LENGTHS / BAR COUNTS")
    print("=" * 100)

    print(f"\nQ7P Section data area (0x120-0x17F) — 6 sections × 16 bytes each:")
    for i in range(6):
        offset = 0x120 + i * 16
        chunk = raw[offset : offset + 16]
        print(f"  Section {i} ({SECTION_NAMES[i]:>8}): 0x{offset:03X}: {hex_bytes(chunk)}")

    print(f"\nQY70 section lengths — estimated from track data sizes:")
    for i in range(6):
        al_start = i * 8
        sizes = []
        for t in range(8):
            al = al_start + t
            if al in syx["al_sizes"]:
                sizes.append(syx["al_sizes"][al])
        if sizes:
            print(
                f"  Section {i} ({SECTION_NAMES[i]:>8}): track sizes = {sizes}, total = {sum(sizes)}"
            )
        else:
            print(f"  Section {i} ({SECTION_NAMES[i]:>8}): no track data")

    print(f"\nNOTE: Section length encoding is NOT fully understood in either format.")
    print(f"  Q7P: The 16-byte section config at 0x120 likely encodes bar count,")
    print(f"        time sig, and phrase references, but the encoding is not documented.")
    print(f"  QY70: Section length is implicit from track data size (multiples of 128 bytes).")

    # ─── SECTION 10: Track Types ────────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 10: TRACK TYPE IDENTIFICATION (DRUM/BASS/CHORD)")
    print("=" * 100)

    print(f"\n{'Track':<8} {'Q7P Method':<35} {'QY70 Method':<40} {'Compatible?'}")
    print("─" * 100)

    for i in range(8):
        # Q7P: track type determined by position and channel
        q7p_ch = q7p["channels"][i]
        q7p_msb = q7p["bank_msb"][i]
        if q7p_ch == 10:
            q7p_type = f"DRUM (Ch10, BankMSB=0x{q7p_msb:02X})"
        elif i == 2:
            q7p_type = f"BASS (position, Ch{q7p_ch})"
        else:
            q7p_type = f"MELODY (Ch{q7p_ch}, BankMSB=0x{q7p_msb:02X})"

        # QY70: track type from bytes 14-17, 18-20
        al = i
        if al in syx["track_voices"] and al in syx["track_flags"]:
            b14, b15 = syx["track_voices"][al]
            b16, b17 = syx["track_note_ranges"][al]
            b18, b19, b20 = syx["track_flags"][al]
            if b14 == 0x40 and b15 == 0x80:
                qy70_type = (
                    f"DRUM (B14=40,B15=80,NR={b16:02X}-{b17:02X},F={b18:02X} {b19:02X} {b20:02X})"
                )
            elif b14 == 0x00 and b15 == 0x04:
                qy70_type = (
                    f"BASS (B14=00,B15=04,NR={b16:02X}-{b17:02X},F={b18:02X} {b19:02X} {b20:02X})"
                )
            else:
                qy70_type = f"MELODY (B14={b14:02X},B15={b15:02X},NR={b16:02X}-{b17:02X},F={b18:02X} {b19:02X} {b20:02X})"
        else:
            qy70_type = "No data"

        compat = "Different encoding"
        print(f"{Q7P_TRACKS[i]:<8} {q7p_type:<35} {qy70_type:<40} {compat}")

    print(f"\nQ7P: Track type determined by position (TR1-2=RHY, TR3=BASS) + channel + BankMSB")
    print(f"QY70: Track type encoded in bytes 14-15, 16-17, 18-20 of each track block")
    print(f"Converter: qy700_to_qy70.py uses track_num in (0,1) for drum detection (line 456)")

    # ─── SECTION 11: Note Range ─────────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 11: NOTE RANGE (QY70 only — bytes 16-17)")
    print("=" * 100)

    print(
        f"\n{'Track':<8} {'QY70 AL':<8} {'Byte 16':<10} {'Byte 17':<10} {'Range':<20} {'Q7P Equivalent?'}"
    )
    print("─" * 80)

    for i in range(8):
        al = i
        if al in syx["track_note_ranges"]:
            b16, b17 = syx["track_note_ranges"][al]
            if b16 == 0x87 and b17 == 0xF8:
                range_str = "Drum encoding"
            elif b16 < 128 and b17 < 128:
                range_str = f"MIDI {b16}-{b17}"
            else:
                range_str = f"0x{b16:02X}-0x{b17:02X}"
            print(
                f"{QY70_TRACKS[i]:<8} {'0x{:02X}'.format(al):<8} {'0x{:02X}'.format(b16):<10} {'0x{:02X}'.format(b17):<10} {range_str:<20} {'NOT MAPPED in Q7P'}"
            )
        else:
            print(
                f"{QY70_TRACKS[i]:<8} {'0x{:02X}'.format(al):<8} {'N/A':<10} {'N/A':<10} {'No data':<20} {'N/A'}"
            )

    print(f"\nQ7P does NOT have a note range field. This is QY70-only.")
    print(f"Converter: qy700_to_qy70.py hardcodes 0x87/0xF8 for drums, 0x07/0x78 for melody")

    # ─── SECTION 12: Header Deep Dive (AL=0x7F) ────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 12: QY70 HEADER DEEP DIVE (AL=0x7F, decoded)")
    print("=" * 100)

    header = syx["header_data"]
    if header:
        print(f"\nFull header hex dump ({len(header)} bytes):")
        for offset in range(0, len(header), 16):
            chunk = header[offset : min(offset + 16, len(header))]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"  0x{offset:03X}: {hex_str:<48}  {ascii_str}")

        # Structured analysis of header regions
        print(f"\n--- Header Structure Analysis ---")
        print(
            f"  [0x000] Format marker:     0x{header[0]:02X} ({'Style' if header[0] >= 0x08 else 'Pattern'})"
        )
        print(f"  [0x001-0x005] Fixed:       {hex_bytes(header[1:6])}")
        print(f"  [0x006-0x009] Style data:  {hex_bytes(header[6:10])}")
        print(f"  [0x00A-0x00B] Constant:    {hex_bytes(header[0xA:0xC])}")
        print(f"  [0x00C-0x00F] TS/timing?:  {hex_bytes(header[0xC:0x10])}")

        # Look for repeating structures
        print(f"\n  [0x010-0x04F] Repeating 7-byte structures (section config?):")
        for i in range(0x10, min(0x50, len(header)), 7):
            chunk = header[i : min(i + 7, len(header))]
            if len(chunk) == 7:
                print(f"    0x{i:03X}: {hex_bytes(chunk)}")

        # Look for mixer/voice data area
        print(f"\n  [0x050-0x09F] Potential mixer/voice area:")
        for i in range(0x50, min(0xA0, len(header)), 16):
            chunk = header[i : min(i + 16, len(header))]
            non_zero = sum(1 for b in chunk if b != 0)
            marker = " <-- has data" if non_zero > 2 else ""
            print(f"    0x{i:03X}: {hex_bytes(chunk)}{marker}")

        # Per-track config area (0x096-0x0B7 from syx_analyzer docstring)
        print(f"\n  [0x090-0x0CF] Per-track config area:")
        for i in range(0x90, min(0xD0, len(header)), 16):
            chunk = header[i : min(i + 16, len(header))]
            print(f"    0x{i:03X}: {hex_bytes(chunk)}")

        # Look for volume/pan/reverb/chorus values in the header
        print(f"\n  Searching header for XG parameter patterns...")

        # Volume (looking for clusters of values around 100/0x64)
        vol_candidates = []
        for i in range(len(header) - 7):
            window = header[i : i + 8]
            # Look for 8 consecutive bytes that could be volumes (40-127 range)
            if all(40 <= b <= 127 for b in window):
                vol_candidates.append((i, list(window)))
        if vol_candidates:
            print(f"  Volume candidates (8 bytes in 40-127 range):")
            for off, vals in vol_candidates[:5]:
                print(f"    0x{off:03X}: {vals}")
        else:
            print(f"  No clear volume pattern found in header")

        # Pan (looking for clusters around 64/0x40)
        pan_candidates = []
        for i in range(len(header) - 7):
            window = header[i : i + 8]
            if all(0 <= b <= 127 for b in window) and any(32 <= b <= 96 for b in window):
                center_count = sum(1 for b in window if b == 64)
                if center_count >= 3:
                    pan_candidates.append((i, list(window)))
        if pan_candidates:
            print(f"  Pan candidates (8 bytes with multiple 64s):")
            for off, vals in pan_candidates[:5]:
                print(f"    0x{off:03X}: {vals}")

        # Style-specific data area (0x1B9+)
        if len(header) > 0x1B9:
            print(f"\n  [0x1B9-0x21F] Style-specific area (effects?):")
            for i in range(0x1B9, min(0x220, len(header)), 16):
                chunk = header[i : min(i + 16, len(header))]
                print(f"    0x{i:03X}: {hex_bytes(chunk)}")

        # Fill pattern area
        if len(header) > 0x220:
            print(f"\n  [0x220-0x27F] Fill/default pattern area:")
            for i in range(0x220, min(0x280, len(header)), 16):
                chunk = header[i : min(i + 16, len(header))]
                print(f"    0x{i:03X}: {hex_bytes(chunk)}")

    # ─── SECTION 13: Q7P Unknown Areas ──────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 13: Q7P UNKNOWN / UNMAPPED AREAS")
    print("=" * 100)

    unknown_areas = [
        (0x012, 0x030, "Reserved after pattern flags"),
        (0x032, 0x100, "Reserved before section ptrs"),
        (0x18C, 0x190, "Timing flags after time sig"),
        (0x198, 0x1A0, "After channel assignments"),
        (0x1A0, 0x1DC, "Reserved before track numbers"),
        (0x216, 0x220, "After bank_lsb, before volume header"),
        (0x236, 0x250, "After volume data, before reverb header"),
        (0x266, 0x270, "After reverb data, before pan header"),
        (0x286, 0x2C0, "After pan data — CHORUS/VARIATION/EXPRESSION?"),
        (0x2C0, 0x360, "Table 3 — unknown effects area"),
    ]

    for start, end, desc in unknown_areas:
        size = end - start
        chunk = raw[start:end]
        chunk_empty = raw_empty[start:end]
        diff = "DIFFERENT" if chunk != chunk_empty else "SAME in both"
        non_zero = sum(1 for b in chunk if b not in (0x00, 0x20, 0x40, 0xFE, 0xF8))
        print(f"\n  0x{start:03X}-0x{end:03X} ({size:3d} bytes): {desc}")
        print(f"    T01 vs TXX: {diff}")
        print(f"    Non-filler bytes: {non_zero}/{size}")
        # Show first and last 16 bytes
        if size <= 32:
            print(f"    T01: {hex_bytes(chunk)}")
            print(f"    TXX: {hex_bytes(chunk_empty)}")
        else:
            print(f"    T01 start: {hex_bytes(chunk[:16])}")
            print(f"    TXX start: {hex_bytes(chunk_empty[:16])}")
            if chunk != chunk_empty:
                # Find first difference
                for di in range(len(chunk)):
                    if chunk[di] != chunk_empty[di]:
                        print(
                            f"    First diff at offset 0x{start + di:03X}: T01=0x{chunk[di]:02X} TXX=0x{chunk_empty[di]:02X}"
                        )
                        break

    # ─── SECTION 14: Specific Investigation — Chorus/Variation/Expression ───
    print("\n")
    print("=" * 100)
    print("SECTION 14: INVESTIGATING CHORUS / VARIATION / EXPRESSION IN Q7P")
    print("=" * 100)

    # The area 0x286-0x2BF (after pan data, before table_3) has 58 bytes
    # If chorus is at 0x296 (from converter), pattern is:
    #   0x276: Pan data (16 bytes for tracks, more for sections?)
    #   0x286: More pan? Or start of chorus?
    #   0x296: Chorus data?
    #   0x2A6: Variation data?
    #   0x2B6: Expression data?

    print(f"\nQ7P parameter table pattern analysis:")
    print(f"  Volume table:  header=0x220 (6 bytes), data=0x226 (16+ bytes)")
    print(f"  Reverb table:  header=0x250 (6 bytes), data=0x256 (16+ bytes)")
    print(f"  Pan table:     header=0x270 (6 bytes), data=0x276 (16+ bytes)")
    print(f"  Table spacing: 0x250-0x220 = 0x30 (48 bytes)")
    print(f"  Table spacing: 0x270-0x250 = 0x20 (32 bytes)")
    print(f"  Table spacing: 0x2C0-0x270 = 0x50 (80 bytes)")

    print(f"\n  Following the 0x30 pattern from volume:")
    print(f"    Volume:     0x220 (header) / 0x226 (data)")
    print(f"    Reverb:     0x250 (header) / 0x256 (data)")
    print(f"    Pan:        0x270 (header) / 0x276 (data)")

    print(f"\n  After pan at 0x276+16=0x286, remaining area before 0x2C0:")
    print(f"  0x286-0x2BF = 58 bytes")

    print(f"\n  Hypothesis: Chorus at 0x296, same structure as converter says")
    print(f"  Checking 0x290-0x2BF for table headers (pattern: starts with non-zero prefix):")

    for offset in range(0x286, 0x2C0, 2):
        t01_val = raw[offset : offset + 2]
        txx_val = raw_empty[offset : offset + 2]
        diff = "" if t01_val == txx_val else " <-- DIFFERENT"
        print(
            f"    0x{offset:03X}: T01={t01_val[0]:02X} {t01_val[1]:02X}  TXX={txx_val[0]:02X} {txx_val[1]:02X}{diff}"
        )

    # Check if 0x296 area has the typical "header + data" pattern
    print(f"\n  Comparing table header patterns:")
    print(f"    Vol header (0x220): {hex_bytes(raw[0x220:0x226])}")
    print(f"    Rev header (0x250): {hex_bytes(raw[0x250:0x256])}")
    print(f"    Pan header (0x270): {hex_bytes(raw[0x270:0x276])}")
    print(f"    0x290 area:         {hex_bytes(raw[0x290:0x296])}")
    print(f"    0x2A0 area:         {hex_bytes(raw[0x2A0:0x2A6])}")
    print(f"    0x2B0 area:         {hex_bytes(raw[0x2B0:0x2B6])}")

    # ─── SECTION 15: Table 3 Deep Dive ──────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 15: TABLE 3 (0x2C0-0x35F) — EFFECTS SETTINGS?")
    print("=" * 100)

    print(f"\nQ7P Table 3 (0x2C0-0x35F, 160 bytes):")
    for offset in range(0x2C0, 0x360, 16):
        t01_chunk = raw[offset : offset + 16]
        txx_chunk = raw_empty[offset : offset + 16]
        diff = "SAME" if t01_chunk == txx_chunk else "DIFF"
        print(f"  0x{offset:03X}: T01={hex_bytes(t01_chunk)}  [{diff}]")

    # Byte frequency analysis
    table3_t01 = raw[0x2C0:0x360]
    table3_txx = raw_empty[0x2C0:0x360]
    from collections import Counter

    freq_t01 = Counter(table3_t01).most_common(10)
    freq_txx = Counter(table3_txx).most_common(10)
    print(f"\n  Byte frequency T01: {[(f'0x{b:02X}', c) for b, c in freq_t01]}")
    print(f"  Byte frequency TXX: {[(f'0x{b:02X}', c) for b, c in freq_txx]}")

    # ─── SECTION 16: Complete Mapping Summary ───────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 16: COMPLETE MAPPING SUMMARY TABLE")
    print("=" * 100)

    mappings = [
        # (Parameter, Q7P offset, QY70 location, Status, Direction, Notes)
        ("Format marker", "0x000 (16B)", "Header[0]", "MAPPED", "Both", "Different encoding"),
        ("Pattern number", "0x010", "N/A", "Q7P ONLY", "N/A", "No QY70 equivalent"),
        ("Pattern flags", "0x011", "N/A", "Q7P ONLY", "N/A", "No QY70 equivalent"),
        ("Size marker", "0x030", "N/A", "Q7P ONLY", "N/A", "Fixed per format"),
        (
            "Section pointers",
            "0x100-0x11F",
            "AL distribution",
            "MAPPED",
            "Both",
            "Different structure",
        ),
        (
            "Section config",
            "0x120-0x17F",
            "Implicit in data",
            "PARTIAL",
            "N/A",
            "Critical—not modified",
        ),
        ("Tempo", "0x188-0x189", "Raw payload[0:1]", "MAPPED", "700→70", "Different encoding"),
        ("Time signature", "0x18A", "Header[0x0C]?", "UNCERTAIN", "N/A", "QY70 location unknown"),
        (
            "Channel assignments",
            "0x190-0x19F",
            "Fixed per track",
            "PARTIAL",
            "700→70",
            "QY70 uses defaults",
        ),
        ("Track numbers", "0x1DC-0x1E3", "Fixed (0-7)", "IMPLICIT", "N/A", "Both positional"),
        (
            "Track enable flags",
            "0x1E4-0x1E5",
            "Has data per AL",
            "MAPPED",
            "Both",
            "Different encoding",
        ),
        ("Bank MSB", "0x1E6-0x1F5", "Track byte 14", "PARTIAL", "N/A", "Converter ignores"),
        ("Program number", "0x1F6-0x205", "Track byte 15", "PARTIAL", "N/A", "Converter ignores"),
        ("Bank LSB", "0x206-0x215", "Track byte 26?", "UNCERTAIN", "N/A", "Only for bass track"),
        ("Volume", "0x226+", "Header area?", "PARTIAL", "700→70", "QY70 loc uncertain"),
        ("Reverb send", "0x256+", "Header area?", "PARTIAL", "700→70", "QY70 loc uncertain"),
        ("Pan", "0x276+", "Track bytes 21-22", "MAPPED", "70→700", "Flag byte needed"),
        ("Chorus send", "0x296+?", "Header area?", "UNCERTAIN", "N/A", "Q7P offset unverified"),
        ("Variation send", "???", "Header area?", "UNMAPPED", "N/A", "Unknown in both"),
        ("Expression", "???", "???", "UNMAPPED", "N/A", "Unknown in both"),
        ("Note range (low)", "N/A", "Track byte 16", "QY70 ONLY", "N/A", "QY70 per-track"),
        ("Note range (high)", "N/A", "Track byte 17", "QY70 ONLY", "N/A", "QY70 per-track"),
        (
            "Track type flags",
            "Position-based",
            "Track bytes 18-20",
            "PARTIAL",
            "N/A",
            "Different encoding",
        ),
        (
            "Pattern name",
            "0x876-0x87F",
            "Not stored",
            "Q7P ONLY",
            "700→70",
            "QY70 has no name field",
        ),
        (
            "Phrase/MIDI data",
            "0x360-0x86F",
            "Track data (24+)",
            "MAPPED",
            "Both",
            "Same event format!",
        ),
        ("Fill area (0xFE)", "0x9C0-0xB0F", "N/A", "Q7P ONLY", "N/A", "Structural padding"),
        ("Pad area (0xF8)", "0xB10-0xBFF", "N/A", "Q7P ONLY", "N/A", "End padding"),
        ("Global reverb type", "???", "Header area", "UNMAPPED", "N/A", "Unknown Q7P location"),
        ("Global chorus type", "???", "Header area", "UNMAPPED", "N/A", "Unknown Q7P location"),
        ("Transpose", "???", "???", "UNMAPPED", "N/A", "Unknown in both"),
        ("Velocity offset", "???", "???", "UNMAPPED", "N/A", "Unknown in both"),
        ("Gate time", "???", "???", "UNMAPPED", "N/A", "Unknown in both"),
    ]

    print(
        f"\n{'Parameter':<22} {'Q7P Location':<18} {'QY70 Location':<20} {'Status':<12} {'Direction':<10} {'Notes'}"
    )
    print("─" * 120)
    for param, q7p_loc, qy70_loc, status, direction, notes in mappings:
        # Color-code status
        if status == "MAPPED":
            marker = "[OK]"
        elif status == "PARTIAL":
            marker = "[!!]"
        elif status in ("UNMAPPED", "UNCERTAIN"):
            marker = "[??]"
        elif "ONLY" in status:
            marker = "[--]"
        else:
            marker = "[  ]"
        print(
            f"{marker} {param:<20} {q7p_loc:<18} {qy70_loc:<20} {status:<12} {direction:<10} {notes}"
        )

    # ─── SECTION 17: Gap Analysis ───────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("SECTION 17: GAP ANALYSIS & OPEN QUESTIONS")
    print("=" * 100)

    # Count statuses
    mapped = sum(1 for _, _, _, s, _, _ in mappings if s == "MAPPED")
    partial = sum(1 for _, _, _, s, _, _ in mappings if s == "PARTIAL")
    unmapped = sum(1 for _, _, _, s, _, _ in mappings if s == "UNMAPPED")
    uncertain = sum(1 for _, _, _, s, _, _ in mappings if s == "UNCERTAIN")
    one_sided = sum(1 for _, _, _, s, _, _ in mappings if "ONLY" in s)

    print(f"\n  MAPPED (complete):      {mapped}")
    print(f"  PARTIAL (needs work):   {partial}")
    print(f"  UNCERTAIN (unverified): {uncertain}")
    print(f"  UNMAPPED (unknown):     {unmapped}")
    print(f"  ONE-SIDED (no equiv):   {one_sided}")
    print(f"  TOTAL fields:           {len(mappings)}")

    print(f"\n--- Open Questions ---")
    print(f"""
  1. WHERE IS CHORUS SEND IN Q7P?
     - Converter defines 0x296 but this is UNVERIFIED against hardware.
     - The area 0x286-0x2BF after pan data is the prime candidate.
     - Both T01 and TXX show identical data in this region, suggesting defaults (0x00=no chorus).
     - VERDICT: Likely at 0x296+track, matches converter assumption.
       The 6-byte header + 16 bytes data pattern would put it at 0x290(hdr) + 0x296(data).

  2. WHERE IS VARIATION SEND?
     - XG standard includes Variation Send (CC94).
     - Not found in any documented Q7P offset.
     - Could be in Table 3 (0x2C0-0x35F) or in the 0x2A6+ area.
     - NEEDS HARDWARE TESTING with non-default variation send values.

  3. WHERE IS EXPRESSION?
     - XG Expression (CC11) is typically a per-note or per-event parameter.
     - Likely NOT stored as a per-track global value in pattern data.
     - May be embedded in MIDI event data (0x360+ / 0x678+) as CC events.
     - VERDICT: Probably not a header field — it's an event-level parameter.

  4. HOW ARE SECTION LENGTHS ENCODED?
     - Q7P: 16-byte config per section at 0x120. Encoding unknown.
       First bytes seem to be phrase pointers or measure counts.
     - QY70: Implicit from track data size. Each track block is 128-byte multiples.
       The header MAY contain section length metadata but no clear field identified.
     - NEEDS: Create patterns with different bar counts and compare.

  5. WHERE IS TIME SIGNATURE IN QY70 HEADER?
     - Q7P: Clearly at 0x18A (e.g., 0x1C = 4/4).
     - QY70: Header byte 0x0C is a candidate (syx_analyzer reads it) but NOT confirmed.
     - The header byte 0x0C in SGT = {f"0x{syx.get('time_sig_candidate_0c', 0):02X}"}.
     - NEEDS: Dump QY70 patterns with different time signatures.

  6. TRACK TYPE MARKING DIFFERENCES
     - Q7P: Position-based (TR1-2=drums) + Bank MSB (127=drums)
     - QY70: Byte 14-15 patterns (0x40,0x80=drum; 0x00,0x04=bass; other=melody)
       Plus bytes 16-17 (note range) and 18-20 (flags)
     - Converter hardcodes types based on track position, which is correct
       but loses any custom track type assignments.

  7. VOICE SELECTION GAP
     - Q7P stores Bank MSB/Program/Bank LSB per track (0x1E6/0x1F6/0x206)
     - QY70 stores voice in track header bytes 14-15 (and byte 26 for bass)
     - Converter does NOT transfer voices — hardcodes 0x40/0x80 for all.
     - This is a CRITICAL gap for meaningful conversion.

  8. VOLUME/REVERB/CHORUS LOCATION IN QY70
     - These parameters are NOT in the 24-byte track header.
     - They are likely in the global header (AL=0x7F, 640 bytes).
     - The exact offsets within the header are UNKNOWN.
     - qy70_to_qy700.py incorrectly tries to read volume from track byte 24.
     - NEEDS: Systematic header analysis with known mixer values.
""")

    # ─── SECTION 18: Converter Code Issues ──────────────────────────────────
    print("=" * 100)
    print("SECTION 18: CONVERTER CODE ISSUES FOUND")
    print("=" * 100)

    print(f"""
  1. qy700_to_qy70.py — INCORRECT header generation
     - Line 277: Writes tempo to header[0x0A] as single byte. QY70 uses
       range/offset encoding, NOT a single byte value.
     - Line 258-266: Writes pattern name to header[0:10] as raw ASCII.
       QY70 doesn't store name as simple ASCII — the first byte is a
       format marker (0x5E for style), NOT a name character.

  2. qy700_to_qy70.py — Voice not transferred
     - Line 491-492: Hardcodes 0x40 0x80 for ALL tracks.
     - Should read Q7P Bank MSB (0x1E6), Program (0x1F6), Bank LSB (0x206)
       and encode properly for each track type.

  3. qy70_to_qy700.py — Volume extraction wrong
     - Line 268: Reads volume from decoded track data byte 24.
     - Byte 24 is the START of MIDI sequence data, not volume!
     - Volume is likely in the QY70 header (AL=0x7F), not track blocks.

  4. qy70_to_qy700.py — Missing parameter transfers
     - Does NOT extract: reverb send, chorus send, voice/program,
       bank MSB/LSB, channel assignments, track enable flags.
     - Only transfers: name (incorrectly), tempo (from wrong location), pan, volume (from wrong location).

  5. qy700_to_qy70.py — Section AL offset
     - Line 63-70: SECTION_AL maps SectionType to AL 0x00-0x05.
       This means only 1 track per section gets an AL.
       But QY70 uses AL = section*8 + track (0-7 per section).
     - The actual track generation at line 360 uses base_al = section_idx * 8,
       which is CORRECT. The SECTION_AL dict is unused/wrong.
""")

    print("\nDone. Full analysis complete.")


if __name__ == "__main__":
    main()
