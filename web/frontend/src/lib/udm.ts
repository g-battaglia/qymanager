import type { UdmDevice } from "@/lib/types"

const LABEL_OVERRIDES: Record<string, string> = {
  udm_version: "UDM Version",
  source_format: "Source Format",
  multi_part: "Multi Part",
  drum_setup: "Drum Setup",
  phrases_user: "User Phrases",
  fingered_zone: "Fingered Zone",
  master_volume: "Master Volume",
  master_tune: "Master Tune",
  midi_sync: "MIDI Sync",
  time_sig: "Time Signature",
  tempo_bpm: "Tempo",
  groove_ref: "Groove Reference",
}

export const ROOT_SECTION_ORDER = [
  "model",
  "source_format",
  "udm_version",
  "system",
  "effects",
  "multi_part",
  "drum_setup",
  "patterns",
  "songs",
  "phrases_user",
  "groove_templates",
  "fingered_zone",
  "utility",
] as const

function titleCase(value: string): string {
  return value
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

export function humanizeKey(key: string): string {
  if (LABEL_OVERRIDES[key]) {
    return LABEL_OVERRIDES[key]
  }
  if (/^\[\d+\]$/.test(key)) {
    return `Item ${Number(key.slice(1, -1)) + 1}`
  }
  return titleCase(key.replace(/_/g, " "))
}

export function joinPath(parent: string, key: string): string {
  if (!parent) {
    return key
  }
  if (key.startsWith("[")) {
    return `${parent}${key}`
  }
  return `${parent}.${key}`
}

export function getNodeSummary(value: unknown): string {
  if (Array.isArray(value)) {
    const suffix = value.length === 1 ? "item" : "items"
    return `${value.length} ${suffix}`
  }
  if (value && typeof value === "object") {
    const size = Object.keys(value as Record<string, unknown>).length
    const suffix = size === 1 ? "field" : "fields"
    return `${size} ${suffix}`
  }
  if (typeof value === "boolean") {
    return value ? "On" : "Off"
  }
  if (value === null) {
    return "None"
  }
  if (value === "") {
    return "Empty"
  }
  return String(value)
}

export function isScalarValue(value: unknown): boolean {
  return value === null || ["string", "number", "boolean"].includes(typeof value)
}

export function formatPathLabel(path: string): string {
  return path
    .replace(/\[(\d+)\]/g, ".[$1]")
    .split(".")
    .filter(Boolean)
    .map((part) => humanizeKey(part.startsWith("[") ? part : part))
    .join(" / ")
}

export function getRootEntries(device: Record<string, unknown>) {
  const order = new Map<string, number>(
    ROOT_SECTION_ORDER.map((key, index) => [key, index]),
  )
  return Object.entries(device).sort(([a], [b]) => {
    const ai = order.get(a) ?? 999
    const bi = order.get(b) ?? 999
    return ai - bi || a.localeCompare(b)
  })
}

export function getFirstPattern(device: UdmDevice) {
  return device.patterns[0] as Record<string, unknown> | undefined
}

export function getPatternSections(device: UdmDevice): string[] {
  const firstPattern = getFirstPattern(device)
  const sections = firstPattern?.sections
  if (!sections || typeof sections !== "object") {
    return []
  }
  return Object.keys(sections as Record<string, unknown>)
}

export function countDrumNoteOverrides(device: UdmDevice): number {
  return device.drum_setup.reduce((total, setup) => {
    const notes = setup["notes"]
    if (!notes || typeof notes !== "object") {
      return total
    }
    return total + Object.keys(notes).length
  }, 0)
}

export function describeImportContext(device: UdmDevice): string | null {
  if (
    device.source_format === "syx" &&
    device.multi_part.length === 0 &&
    device.drum_setup.length === 0
  ) {
    return "This looks like a sparse QY70 pattern dump. Pattern structure is available, but XG Multi Part and Drum Setup state are not present in this file."
  }
  return null
}

export type TrackInfo = {
  index: number
  midiChannel: number
  voice: { bank_msb: number; bank_lsb: number; program: number }
  volume: number
  pan: number
  reverbSend: number
  chorusSend: number
  mute: boolean
  transposeRule: string
  phraseRef: number
  path: string
}

export type SectionInfo = {
  name: string
  enabled: boolean
  tracks: TrackInfo[]
  path: string
}

export function getSectionsWithTracks(device: UdmDevice): SectionInfo[] {
  const pattern = device.patterns[0] as Record<string, unknown> | undefined
  if (!pattern) return []

  const sections = pattern.sections as Record<string, Record<string, unknown>> | undefined
  if (!sections) return []

  return Object.entries(sections).map(([sectionName, section]) => {
    const rawTracks = section.tracks as Record<string, unknown>[] | undefined
    const tracks: TrackInfo[] = (rawTracks ?? []).map((t, i) => ({
      index: i,
      midiChannel: Number(t.midi_channel ?? 0),
      voice: {
        bank_msb: Number((t.voice as Record<string, unknown>)?.bank_msb ?? 0),
        bank_lsb: Number((t.voice as Record<string, unknown>)?.bank_lsb ?? 0),
        program: Number((t.voice as Record<string, unknown>)?.program ?? 0),
      },
      volume: Number(t.volume ?? 100),
      pan: Number(t.pan ?? 64),
      reverbSend: Number(t.reverb_send ?? 0),
      chorusSend: Number(t.chorus_send ?? 0),
      mute: Boolean(t.mute),
      transposeRule: String(t.transpose_rule ?? "Bypass"),
      phraseRef: Number(t.phrase_ref ?? 0),
      path: `patterns[0].sections.${sectionName}.tracks[${i}]`,
    }))

    return {
      name: String(section.name ?? sectionName),
      enabled: Boolean(section.enabled),
      tracks,
      path: `patterns[0].sections.${sectionName}`,
    }
  })
}

export function panLabel(value: number): string {
  if (value === 0) return "Rnd"
  if (value < 64) return `L${64 - value}`
  if (value > 64) return `R${value - 64}`
  return "C"
}

export function isDrumChannel(channel: number): boolean {
  return channel === 9
}
