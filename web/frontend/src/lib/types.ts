export type UdmDevice = {
  model: string
  udm_version?: string
  system: Record<string, unknown>
  multi_part: Record<string, unknown>[]
  drum_setup: Record<string, unknown>[]
  effects: Record<string, unknown>
  songs: Record<string, unknown>[]
  patterns: Record<string, unknown>[]
  phrases_user: Record<string, unknown>[]
  groove_templates: Record<string, unknown>[]
  fingered_zone: Record<string, unknown>
  utility: Record<string, unknown>
  source_format?: string
}

export type UploadResponse = {
  id: string
  device: UdmDevice
  warnings: string[]
}

export type DeviceResponse = {
  device: UdmDevice
  warnings: string[]
}

export type FieldPatch = { path: string; value: unknown }

export type FieldPatchResponse = {
  device: UdmDevice
  errors: string[]
}

export type SchemaEntry = {
  path: string
  kind: "range" | "enum"
  lo?: number
  hi?: number
  options?: string[]
}

export type SchemaResponse = {
  paths: SchemaEntry[]
}

export type DiffChange = { path: string; a: unknown; b: unknown }

export type ExportResult = { blob: Blob; warnings: string[] }

export type VoiceResolveRequest = {
  bank_msb: number
  bank_lsb: number
  program: number
  channel: number
}

export type VoiceResolveResponse = {
  name: string
  category: string
  is_drum: boolean
  is_sfx: boolean
}

export type PhraseEvent = {
  tick: number
  channel: number
  kind: string
  data1: number
  data2: number
  note_name: string | null
  velocity: number | null
}

export type PhraseModel = {
  name: string
  tempo: number
  note_count: number
  event_count: number
  events: PhraseEvent[]
}

export type PhrasesResponse = {
  source: string
  phrases: PhraseModel[]
  note: string | null
}

export type SyxAnalysisTrack = {
  index: number
  name: string
  long_name: string
  channel: number
  has_data: boolean
  data_bytes: number
  active_sections: string[]
  bank_msb: number
  bank_lsb: number
  program: number
  voice_name: string
  voice_source: "db" | "nn" | "class" | "xg" | "none"
  voice_bit_distance: number | null
  volume: number
  pan: number
  reverb_send: number
  chorus_send: number
  variation_send: number
  is_drum_track: boolean
}

export type SyxAnalysisSection = {
  index: number
  name: string
  has_data: boolean
  phrase_bytes: number
  track_bytes: number
  active_tracks: number[]
  bar_count: number
  beat_count: number
}

export type SyxAnalysisEffect = {
  name: string
  msb: number
  lsb: number
}

export type SyxAnalysisStats = {
  total_messages: number
  bulk_dump_messages: number
  parameter_messages: number
  valid_checksums: number
  invalid_checksums: number
  total_encoded_bytes: number
  total_decoded_bytes: number
}

export type SyxAnalysisSystem = {
  master_tune_cents: number | null
  master_volume: number | null
  master_attenuator: number | null
  transpose: number | null
  xg_system_on: boolean
}

export type SyxAnalysisSlot = {
  slot: number
  name: string
}

export type SyxAnalysisDrumNote = {
  note: number
  note_name: string
  level: number | null
  pan: number | null
  reverb_send: number | null
  chorus_send: number | null
  pitch_coarse: number | null
  pitch_fine: number | null
}

export type SyxAnalysisDrumKit = {
  kit_index: number
  notes: SyxAnalysisDrumNote[]
}

export type SyxAnalysisResponse = {
  available: boolean
  source_format: string
  format_type: string | null
  pattern_name: string | null
  filesize: number
  data_density: number
  active_section_count: number
  section_total: number
  active_track_count: number
  track_total: number
  tempo: number | null
  time_signature: string | null
  reverb: SyxAnalysisEffect | null
  chorus: SyxAnalysisEffect | null
  variation: SyxAnalysisEffect | null
  tracks: SyxAnalysisTrack[]
  sections: SyxAnalysisSection[]
  stats: SyxAnalysisStats | null
  system: SyxAnalysisSystem | null
  pattern_directory: SyxAnalysisSlot[]
  drum_kits: SyxAnalysisDrumKit[]
  warnings: string[]
  note: string | null
}
