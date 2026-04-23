import { describe, expect, it } from "vitest"

import {
  getNodeSummary,
  getSectionsWithTracks,
  humanizeKey,
  isDrumChannel,
  joinPath,
  panLabel,
} from "@/lib/udm"
import type { UdmDevice } from "@/lib/types"

function makeDevice(overrides: Partial<UdmDevice> = {}): UdmDevice {
  return {
    model: "qy700",
    system: {},
    multi_part: [],
    drum_setup: [],
    effects: {},
    songs: [],
    patterns: [],
    phrases_user: [],
    groove_templates: [],
    fingered_zone: {},
    utility: {},
    ...overrides,
  }
}

function makeTrack(overrides: Record<string, unknown> = {}) {
  return {
    phrase_ref: 0,
    midi_channel: 0,
    voice: { bank_msb: 0, bank_lsb: 0, program: 0 },
    transpose_rule: "Bypass",
    mute: false,
    pan: 64,
    volume: 100,
    reverb_send: 40,
    chorus_send: 0,
    ...overrides,
  }
}

describe("udm helpers", () => {
  it("joins array paths without inserting a dot", () => {
    expect(joinPath("patterns", "[0]")).toBe("patterns[0]")
    expect(joinPath("patterns[0]", "tempo_bpm")).toBe("patterns[0].tempo_bpm")
  })

  it("humanizes common UDM keys", () => {
    expect(humanizeKey("multi_part")).toBe("Multi Part")
    expect(humanizeKey("master_volume")).toBe("Master Volume")
    expect(humanizeKey("[3]")).toBe("Item 4")
  })

  it("summarizes booleans and collections", () => {
    expect(getNodeSummary(true)).toBe("On")
    expect(getNodeSummary([1, 2])).toBe("2 items")
    expect(getNodeSummary({ a: 1 })).toBe("1 field")
  })

  it("identifies drum channel 9", () => {
    expect(isDrumChannel(9)).toBe(true)
    expect(isDrumChannel(0)).toBe(false)
    expect(isDrumChannel(10)).toBe(false)
  })

  it("formats pan labels", () => {
    expect(panLabel(64)).toBe("C")
    expect(panLabel(0)).toBe("Rnd")
    expect(panLabel(32)).toBe("L32")
    expect(panLabel(96)).toBe("R32")
  })

  it("extracts sections with tracks from a device", () => {
    const device = makeDevice({
      patterns: [
        {
          sections: {
            Main_A: {
              name: "Main_A",
              enabled: true,
              tracks: [
                makeTrack({ midi_channel: 9, volume: 91, pan: 64 }),
                makeTrack({ midi_channel: 1, volume: 100, pan: 32 }),
              ],
            },
          },
        },
      ],
    })

    const sections = getSectionsWithTracks(device)
    expect(sections).toHaveLength(1)
    expect(sections[0].name).toBe("Main_A")
    expect(sections[0].enabled).toBe(true)
    expect(sections[0].tracks).toHaveLength(2)
    expect(sections[0].tracks[0].midiChannel).toBe(9)
    expect(sections[0].tracks[0].volume).toBe(91)
    expect(sections[0].tracks[1].pan).toBe(32)
    expect(sections[0].tracks[0].path).toBe(
      "patterns[0].sections.Main_A.tracks[0]",
    )
  })

  it("returns empty when no patterns", () => {
    const device = makeDevice()
    expect(getSectionsWithTracks(device)).toEqual([])
  })
})
