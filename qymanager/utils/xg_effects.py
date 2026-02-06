"""
XG Effect Types and Parameters Lookup Tables.

Based on Yamaha XG specification and webxgmidi documentation.
These tables map effect type bytes to human-readable names.
"""

from typing import Dict, Tuple, Optional

# =============================================================================
# REVERB TYPES
# =============================================================================
# Format: (MSB, LSB) -> Name
REVERB_TYPES: Dict[Tuple[int, int], str] = {
    (0x00, 0x00): "No Effect",
    (0x01, 0x00): "Hall 1",
    (0x01, 0x01): "Hall 2",
    (0x02, 0x00): "Room 1",
    (0x02, 0x01): "Room 2",
    (0x02, 0x02): "Room 3",
    (0x03, 0x00): "Stage 1",
    (0x03, 0x01): "Stage 2",
    (0x04, 0x00): "Plate",
    (0x10, 0x00): "White Room",
    (0x11, 0x00): "Tunnel",
    (0x12, 0x00): "Canyon",
    (0x13, 0x00): "Basement",
}


def get_reverb_type_name(msb: int, lsb: int = 0) -> str:
    """Get reverb type name from MSB/LSB bytes."""
    return REVERB_TYPES.get((msb, lsb), f"Unknown (0x{msb:02X}, 0x{lsb:02X})")


# =============================================================================
# CHORUS TYPES
# =============================================================================
# Format: (MSB, LSB) -> Name
CHORUS_TYPES: Dict[Tuple[int, int], str] = {
    (0x00, 0x00): "No Effect",
    (0x41, 0x00): "Chorus 1",
    (0x41, 0x01): "Chorus 2",
    (0x41, 0x02): "Chorus 3",
    (0x41, 0x08): "Chorus 4",
    (0x42, 0x00): "Celeste 1",
    (0x42, 0x01): "Celeste 2",
    (0x42, 0x02): "Celeste 3",
    (0x42, 0x08): "Celeste 4",
    (0x43, 0x00): "Flanger 1",
    (0x43, 0x01): "Flanger 2",
    (0x43, 0x08): "Flanger 3",
}


def get_chorus_type_name(msb: int, lsb: int = 0) -> str:
    """Get chorus type name from MSB/LSB bytes."""
    return CHORUS_TYPES.get((msb, lsb), f"Unknown (0x{msb:02X}, 0x{lsb:02X})")


# =============================================================================
# VARIATION EFFECT TYPES
# =============================================================================
# Format: (MSB, LSB) -> Name
VARIATION_TYPES: Dict[Tuple[int, int], str] = {
    # Off/Thru
    (0x00, 0x00): "No Effect",
    (0x40, 0x00): "Thru",
    # Reverbs
    (0x01, 0x00): "Hall 1",
    (0x01, 0x01): "Hall 2",
    (0x02, 0x00): "Room 1",
    (0x02, 0x01): "Room 2",
    (0x02, 0x02): "Room 3",
    (0x03, 0x00): "Stage 1",
    (0x03, 0x01): "Stage 2",
    (0x04, 0x00): "Plate",
    # Delays
    (0x05, 0x00): "Delay LCR",
    (0x06, 0x00): "Delay LR",
    (0x07, 0x00): "Echo",
    (0x08, 0x00): "Cross Delay",
    # Early Reflections
    (0x09, 0x00): "Early Reflection 1",
    (0x09, 0x01): "Early Reflection 2",
    (0x0A, 0x00): "Gated Reverb",
    (0x0B, 0x00): "Reverse Gate",
    # Karaoke
    (0x14, 0x00): "Karaoke 1",
    (0x14, 0x01): "Karaoke 2",
    (0x14, 0x02): "Karaoke 3",
    # Chorus/Modulation
    (0x41, 0x00): "Chorus 1",
    (0x41, 0x01): "Chorus 2",
    (0x41, 0x02): "Chorus 3",
    (0x41, 0x08): "Chorus 4",
    (0x42, 0x00): "Celeste 1",
    (0x42, 0x01): "Celeste 2",
    (0x42, 0x02): "Celeste 3",
    (0x42, 0x08): "Celeste 4",
    (0x43, 0x00): "Flanger 1",
    (0x43, 0x01): "Flanger 2",
    (0x43, 0x08): "Flanger 3",
    (0x44, 0x00): "Symphonic",
    (0x45, 0x00): "Rotary Speaker",
    (0x46, 0x00): "Tremolo",
    (0x47, 0x00): "Auto Pan",
    (0x48, 0x00): "Phaser 1",
    (0x48, 0x08): "Phaser 2",
    # Distortion
    (0x49, 0x00): "Distortion",
    (0x4A, 0x00): "Overdrive",
    (0x4B, 0x00): "Amp Simulator",
    # EQ
    (0x4C, 0x00): "3-Band EQ",
    (0x4D, 0x00): "2-Band EQ",
    # Filter
    (0x4E, 0x00): "Auto Wah",
    # Pitch
    (0x50, 0x00): "Pitch Change 1",
    (0x50, 0x08): "Pitch Change 2",
    (0x52, 0x00): "Harmonic Enhancer",
    (0x53, 0x00): "Touch Wah 1",
    (0x53, 0x01): "Touch Wah 2",
    (0x54, 0x00): "Compressor",
    (0x55, 0x00): "Noise Gate",
    (0x56, 0x00): "Voice Cancel",
}


def get_variation_type_name(msb: int, lsb: int = 0) -> str:
    """Get variation effect type name from MSB/LSB bytes."""
    return VARIATION_TYPES.get((msb, lsb), f"Unknown (0x{msb:02X}, 0x{lsb:02X})")


# =============================================================================
# XG CONTROL CHANGE NUMBERS
# =============================================================================
XG_CC_NAMES: Dict[int, str] = {
    0: "Bank Select MSB",
    1: "Modulation",
    2: "Breath Controller",
    5: "Portamento Time",
    6: "Data Entry MSB",
    7: "Volume",
    10: "Pan",
    11: "Expression",
    32: "Bank Select LSB",
    38: "Data Entry LSB",
    64: "Sustain Pedal",
    65: "Portamento On/Off",
    66: "Sostenuto",
    67: "Soft Pedal",
    71: "Resonance (Harmonic Content)",
    72: "Release Time",
    73: "Attack Time",
    74: "Cutoff Frequency (Brightness)",
    75: "Decay Time",
    76: "Vibrato Rate",
    77: "Vibrato Depth",
    78: "Vibrato Delay",
    84: "Portamento Control",
    91: "Reverb Send Level",
    92: "Tremolo Depth",
    93: "Chorus Send Level",
    94: "Variation Send Level",
    95: "Phaser Depth",
    98: "NRPN LSB",
    99: "NRPN MSB",
    100: "RPN LSB",
    101: "RPN MSB",
    120: "All Sound Off",
    121: "Reset All Controllers",
    123: "All Notes Off",
}


def get_cc_name(cc_number: int) -> str:
    """Get Control Change name from CC number."""
    return XG_CC_NAMES.get(cc_number, f"CC {cc_number}")


# =============================================================================
# XG DEFAULT VALUES
# =============================================================================
XG_DEFAULTS = {
    "volume": 100,
    "pan": 64,  # Center
    "reverb_send": 40,
    "chorus_send": 0,
    "variation_send": 0,
    "cutoff": 64,
    "resonance": 64,
    "attack": 64,
    "decay": 64,
    "release": 64,
    "bank_msb": 0,
    "bank_lsb": 0,
    "program": 0,
}

# Default MIDI channels for QY70 tracks
QY70_DEFAULT_CHANNELS = {
    "RHY1": 10,
    "RHY2": 10,
    "BASS": 2,
    "CHD1": 3,
    "CHD2": 4,
    "PAD": 5,
    "PHR1": 6,
    "PHR2": 7,
}


# =============================================================================
# DRUM KIT NAMES (Program numbers on channel 10)
# =============================================================================
DRUM_KITS: Dict[int, str] = {
    0: "Standard Kit",
    1: "Standard Kit 2",
    8: "Room Kit",
    16: "Rock Kit",
    24: "Electronic Kit",
    25: "Analog Kit",
    26: "Dance Kit",
    27: "Hip Hop Kit",
    28: "Jungle Kit",
    32: "Jazz Kit",
    40: "Brush Kit",
    48: "Orchestra Kit",
    56: "SFX Kit",
    127: "SFX Kit 2",
}


def get_drum_kit_name(program: int) -> str:
    """Get drum kit name from program number."""
    return DRUM_KITS.get(program, f"Drum Kit {program}")
