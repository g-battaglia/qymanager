"""
XG/GM Voice and Drum Kit lookup tables.

Based on Yamaha XG specification.
Reference: https://www.studio4all.de/htmle/main92.html
"""

from typing import Optional

# GM/XG Voice names (Program 0-127)
# Bank MSB 0 = Normal voices
GM_VOICES = [
    # Piano (0-7)
    "Acoustic Grand Piano",
    "Bright Acoustic Piano",
    "Electric Grand Piano",
    "Honky-tonk Piano",
    "Electric Piano 1",
    "Electric Piano 2",
    "Harpsichord",
    "Clavinet",
    # Chromatic Percussion (8-15)
    "Celesta",
    "Glockenspiel",
    "Music Box",
    "Vibraphone",
    "Marimba",
    "Xylophone",
    "Tubular Bells",
    "Dulcimer",
    # Organ (16-23)
    "Drawbar Organ",
    "Percussive Organ",
    "Rock Organ",
    "Church Organ",
    "Reed Organ",
    "Accordion",
    "Harmonica",
    "Tango Accordion",
    # Guitar (24-31)
    "Acoustic Guitar (nylon)",
    "Acoustic Guitar (steel)",
    "Electric Guitar (jazz)",
    "Electric Guitar (clean)",
    "Electric Guitar (muted)",
    "Overdriven Guitar",
    "Distortion Guitar",
    "Guitar Harmonics",
    # Bass (32-39)
    "Acoustic Bass",
    "Electric Bass (finger)",
    "Electric Bass (pick)",
    "Fretless Bass",
    "Slap Bass 1",
    "Slap Bass 2",
    "Synth Bass 1",
    "Synth Bass 2",
    # Strings (40-47)
    "Violin",
    "Viola",
    "Cello",
    "Contrabass",
    "Tremolo Strings",
    "Pizzicato Strings",
    "Orchestral Harp",
    "Timpani",
    # Ensemble (48-55)
    "String Ensemble 1",
    "String Ensemble 2",
    "Synth Strings 1",
    "Synth Strings 2",
    "Choir Aahs",
    "Voice Oohs",
    "Synth Voice",
    "Orchestra Hit",
    # Brass (56-63)
    "Trumpet",
    "Trombone",
    "Tuba",
    "Muted Trumpet",
    "French Horn",
    "Brass Section",
    "Synth Brass 1",
    "Synth Brass 2",
    # Reed (64-71)
    "Soprano Sax",
    "Alto Sax",
    "Tenor Sax",
    "Baritone Sax",
    "Oboe",
    "English Horn",
    "Bassoon",
    "Clarinet",
    # Pipe (72-79)
    "Piccolo",
    "Flute",
    "Recorder",
    "Pan Flute",
    "Blown Bottle",
    "Shakuhachi",
    "Whistle",
    "Ocarina",
    # Synth Lead (80-87)
    "Lead 1 (square)",
    "Lead 2 (sawtooth)",
    "Lead 3 (calliope)",
    "Lead 4 (chiff)",
    "Lead 5 (charang)",
    "Lead 6 (voice)",
    "Lead 7 (fifths)",
    "Lead 8 (bass + lead)",
    # Synth Pad (88-95)
    "Pad 1 (new age)",
    "Pad 2 (warm)",
    "Pad 3 (polysynth)",
    "Pad 4 (choir)",
    "Pad 5 (bowed)",
    "Pad 6 (metallic)",
    "Pad 7 (halo)",
    "Pad 8 (sweep)",
    # Synth Effects (96-103)
    "FX 1 (rain)",
    "FX 2 (soundtrack)",
    "FX 3 (crystal)",
    "FX 4 (atmosphere)",
    "FX 5 (brightness)",
    "FX 6 (goblins)",
    "FX 7 (echoes)",
    "FX 8 (sci-fi)",
    # Ethnic (104-111)
    "Sitar",
    "Banjo",
    "Shamisen",
    "Koto",
    "Kalimba",
    "Bagpipe",
    "Fiddle",
    "Shanai",
    # Percussive (112-119)
    "Tinkle Bell",
    "Agogo",
    "Steel Drums",
    "Woodblock",
    "Taiko Drum",
    "Melodic Tom",
    "Synth Drum",
    "Reverse Cymbal",
    # Sound Effects (120-127)
    "Guitar Fret Noise",
    "Breath Noise",
    "Seashore",
    "Bird Tweet",
    "Telephone Ring",
    "Helicopter",
    "Applause",
    "Gunshot",
]

# XG Drum Kits (Bank MSB 127)
XG_DRUM_KITS = {
    0: "Standard Kit",
    1: "Standard Kit 2",
    8: "Room Kit",
    16: "Rock Kit",
    24: "Electronic Kit",
    25: "Analog Kit",
    26: "Dance Kit",
    27: "Jazz Kit",
    28: "Brush Kit",
    32: "Classic Kit",
    40: "SFX Kit 1",
    41: "SFX Kit 2",
    48: "Orchestra Kit",
    56: "Ethnic Kit",
}

# XG SFX Voices (Bank MSB 64)
XG_SFX_VOICES = {
    0: "Cutting Noise",
    1: "Cutting Noise 2",
    3: "String Slap",
    16: "Flute Key Click",
    32: "Rain",
    33: "Thunder",
    34: "Wind",
    35: "Stream",
    36: "Bubble",
    37: "Feed",
    48: "Dog",
    49: "Horse Gallop",
    50: "Bird Tweet 2",
    54: "Ghost",
    55: "Maou",
    64: "Phone Call",
    65: "Door Squeak",
    66: "Door Slam",
    67: "Scratch Cut",
    68: "Scratch Split",
    69: "Wind Chime",
    70: "Telephone Ring 2",
    80: "Car Engine Ignition",
    81: "Car Tires Squeal",
    82: "Car Passing",
    83: "Car Crash",
    84: "Siren",
    85: "Train",
    86: "Jet Plane",
    87: "Starship",
    88: "Burst Noise",
    89: "Coaster",
    90: "Submarine",
    96: "Laugh",
    97: "Scream",
    98: "Punch",
    99: "Heart Beat",
    100: "Footsteps",
    112: "Machine Gun",
    113: "Laser Gun",
    114: "Explosion",
    115: "Firework",
}


def get_voice_name(
    program: int,
    bank_msb: int = 0,
    bank_lsb: int = 0,
    channel: int = 1,
) -> str:
    """
    Get voice/instrument name from program, bank, and channel.

    Args:
        program: Program number (0-127)
        bank_msb: Bank Select MSB (0=Normal, 64=SFX, 127=Drums)
        bank_lsb: Bank Select LSB (voice variations)
        channel: MIDI channel (1-16, 10=drums by convention)

    Returns:
        Human-readable voice name
    """
    # Drum channel or drum bank
    if channel == 10 or bank_msb == 127:
        if program in XG_DRUM_KITS:
            return XG_DRUM_KITS[program]
        return f"Drum Kit {program}"

    # SFX bank
    if bank_msb == 64:
        if program in XG_SFX_VOICES:
            return XG_SFX_VOICES[program]
        return f"SFX {program}"

    # Normal voices
    if 0 <= program < len(GM_VOICES):
        name = GM_VOICES[program]
        # Add bank variation indicator if not default
        if bank_lsb > 0:
            return f"{name} (var.{bank_lsb})"
        return name

    return f"Program {program}"


def get_voice_category(program: int) -> str:
    """Get the category/family of a GM voice."""
    if program < 0 or program > 127:
        return "Unknown"

    categories = [
        (0, 7, "Piano"),
        (8, 15, "Chromatic Percussion"),
        (16, 23, "Organ"),
        (24, 31, "Guitar"),
        (32, 39, "Bass"),
        (40, 47, "Strings"),
        (48, 55, "Ensemble"),
        (56, 63, "Brass"),
        (64, 71, "Reed"),
        (72, 79, "Pipe"),
        (80, 87, "Synth Lead"),
        (88, 95, "Synth Pad"),
        (96, 103, "Synth Effects"),
        (104, 111, "Ethnic"),
        (112, 119, "Percussive"),
        (120, 127, "Sound Effects"),
    ]

    for start, end, name in categories:
        if start <= program <= end:
            return name

    return "Unknown"


# XG Default values (from studio4all.de documentation)
XG_DEFAULTS = {
    "volume": 100,  # 0x64
    "pan": 64,  # 0x40 = Center
    "reverb_send": 40,  # 0x28
    "chorus_send": 0,  # 0x00
    "variation_send": 0,  # 0x00
    "bank_msb_normal": 0,  # 0x00
    "bank_msb_drums": 127,  # 0x7F
    "bank_lsb": 0,  # 0x00
    "program": 0,  # 0x00
    "note_shift": 64,  # 0x40 = 0 semitones
    "expression": 127,  # 0x7F
}
