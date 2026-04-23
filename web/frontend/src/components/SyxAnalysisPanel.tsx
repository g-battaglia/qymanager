import type { ReactNode } from "react"
import type {
  SyxAnalysisResponse,
  SyxAnalysisSection,
  SyxAnalysisTrack,
  UdmDevice,
} from "@/lib/types"
import { panLabel } from "@/lib/udm"
import { PhraseEvents } from "@/components/PhraseEvents"

// ───────────────────────────────────────────────────────────────────
// Layout primitives: one-place definition of section hierarchy
// ───────────────────────────────────────────────────────────────────

function SectionGroup({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="space-y-5">
      <header>
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-muted-foreground">
          {eyebrow}
        </p>
        <h2 className="mt-1 text-xl font-semibold tracking-tight">{title}</h2>
        {description && (
          <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
            {description}
          </p>
        )}
      </header>
      <div className="space-y-6 border-l-2 border-border/40 pl-4">{children}</div>
    </section>
  )
}

function SubSection({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && (
          <span className="text-[10px] text-muted-foreground/70">{hint}</span>
        )}
      </div>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function Divider() {
  return <hr className="border-t border-border/40" />
}

// ───────────────────────────────────────────────────────────────────
// Small shared pieces
// ───────────────────────────────────────────────────────────────────

function VoiceSourceBadge({ source }: { source: SyxAnalysisTrack["voice_source"] }) {
  if (source === "none") return null
  const map: Record<string, { label: string; className: string; title: string }> = {
    db: {
      label: "DB",
      className: "bg-emerald-100 text-emerald-800",
      title: "Matched against the 29-signature pre-trained database",
    },
    class: {
      label: "class",
      className: "bg-slate-200 text-slate-700",
      title: "Only the voice category is known (drum / bass / chord / sfx)",
    },
    xg: {
      label: "XG",
      className: "bg-sky-100 text-sky-800",
      title: "Resolved from captured XG Bank/Program",
    },
  }
  const spec = map[source]
  if (!spec) return null
  return (
    <span
      title={spec.title}
      className={`shrink-0 rounded px-1 py-px text-[9px] font-semibold uppercase tracking-wider ${spec.className}`}
    >
      {spec.label}
    </span>
  )
}

function PanIndicator({ value }: { value: number }) {
  const normalized = (value / 127) * 2 - 1
  const isCenter = value === 64
  const left = 50 - normalized * 40
  return (
    <div className="relative h-1 w-full rounded-full bg-foreground/5">
      <div
        className={`absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full ${
          isCenter ? "bg-foreground/40" : "bg-foreground/60"
        }`}
        style={{ left: `${left}%` }}
      />
    </div>
  )
}

function LevelBar({ value, max }: { value: number; max: number }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="h-1 w-full rounded-full bg-foreground/5">
      <div className="h-full rounded-full bg-foreground/30" style={{ width: `${pct}%` }} />
    </div>
  )
}

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string
  value: string | number
  tone?: "default" | "warn"
}) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <p
        className={`mt-0.5 text-sm font-semibold tabular-nums ${
          tone === "warn" ? "text-amber-700" : ""
        }`}
      >
        {value}
      </p>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────────
// Sound Engine · Effects
// ───────────────────────────────────────────────────────────────────

function EffectsBlock({ analysis }: { analysis: SyxAnalysisResponse }) {
  const rows = [
    { label: "Reverb", effect: analysis.reverb },
    { label: "Chorus", effect: analysis.chorus },
    { label: "Variation", effect: analysis.variation },
  ].filter((r) => r.effect !== null) as Array<{
    label: string
    effect: NonNullable<(typeof analysis)["reverb"]>
  }>
  if (rows.length === 0) return null
  return (
    <SubSection
      title="Effects"
      hint="Global reverb, chorus and variation applied to the whole pattern"
    >
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map(({ label, effect }) => (
          <div key={label} className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {label}
              </p>
              <p className="mt-0.5 truncate text-base font-semibold">{effect.name}</p>
            </div>
            <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground/60">
              {effect.msb.toString(16).toUpperCase().padStart(2, "0")}/
              {effect.lsb.toString(16).toUpperCase().padStart(2, "0")}
            </span>
          </div>
        ))}
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Sound Engine · Multi Part (from UDM, populated after merge-capture)
// ───────────────────────────────────────────────────────────────────

function MultiPartBlock({ device }: { device: UdmDevice }) {
  type VoiceShape = { bank_msb?: number; bank_lsb?: number; program?: number }
  const parts = device.multi_part
    .map((p, i) => ({ idx: i, part: p as Record<string, unknown> }))
    .filter(({ part }) => {
      const v = (part.voice as VoiceShape) || {}
      return v.bank_msb || v.bank_lsb || v.program
    })
  if (parts.length === 0) return null
  return (
    <SubSection
      title="Multi Part"
      hint={`${parts.length} parts with resolved voices (post merge-capture)`}
    >
      <div className="grid gap-1 sm:grid-cols-2 xl:grid-cols-3">
        {parts.map(({ idx, part }) => {
          const v = (part.voice as VoiceShape) || {}
          return (
            <div
              key={idx}
              className="flex items-center gap-2 rounded-md px-2 py-1 text-xs hover:bg-muted/40"
            >
              <span className="w-8 shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
                ch{(part.rx_channel as number) + 1}
              </span>
              <span className="flex-1 font-mono text-[10px] tabular-nums">
                {v.bank_msb ?? 0}/{v.bank_lsb ?? 0}/{v.program ?? 0}
              </span>
              <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                vol {part.volume as number} · rev {part.reverb_send as number}
              </span>
            </div>
          )
        })}
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Sound Engine · XG System
// ───────────────────────────────────────────────────────────────────

function SystemBlock({ system }: { system: SyxAnalysisResponse["system"] }) {
  if (!system) return null
  const hasAny =
    system.master_tune_cents !== null ||
    system.master_volume !== null ||
    (system.master_attenuator !== null && system.master_attenuator > 0) ||
    (system.transpose !== null && system.transpose !== 0) ||
    system.xg_system_on
  if (!hasAny) return null
  return (
    <SubSection title="XG System" hint="Global tuning and output level">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {system.master_tune_cents !== null && (
          <Metric
            label="Master Tune"
            value={`${system.master_tune_cents > 0 ? "+" : ""}${system.master_tune_cents} ¢`}
          />
        )}
        {system.master_volume !== null && (
          <Metric label="Master Vol" value={system.master_volume} />
        )}
        {system.master_attenuator !== null && system.master_attenuator > 0 && (
          <Metric label="Attenuator" value={system.master_attenuator} />
        )}
        {system.transpose !== null && system.transpose !== 0 && (
          <Metric
            label="Transpose"
            value={`${system.transpose > 0 ? "+" : ""}${system.transpose} st`}
          />
        )}
        {system.xg_system_on && <Metric label="XG On" value="✓" />}
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Sound Engine · Drum Kits
// ───────────────────────────────────────────────────────────────────

function DrumKitsBlock({ kits }: { kits: SyxAnalysisResponse["drum_kits"] }) {
  if (kits.length === 0) return null
  return (
    <SubSection
      title="Drum Kits"
      hint="Per-note edits on top of the GM drum map (post merge-capture)"
    >
      <div className="space-y-3">
        {kits.map((kit) => (
          <div key={kit.kit_index}>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Kit {kit.kit_index + 1} · {kit.notes.length} notes
            </p>
            <div className="mt-1 grid gap-x-3 gap-y-0.5 sm:grid-cols-2 lg:grid-cols-3">
              {kit.notes.map((n) => (
                <div
                  key={n.note}
                  className="flex items-center justify-between gap-2 rounded-md px-2 py-0.5 text-[11px] hover:bg-muted/40"
                >
                  <span className="truncate">
                    <span className="font-mono text-[9px] tabular-nums text-muted-foreground/60">
                      {n.note}
                    </span>{" "}
                    {n.note_name}
                  </span>
                  <span className="shrink-0 text-[9px] tabular-nums text-muted-foreground/70">
                    {n.level !== null ? `L${n.level}` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Pattern Structure · Sections
// ───────────────────────────────────────────────────────────────────

function SectionsTable({
  sections,
  active,
  total,
}: {
  sections: SyxAnalysisSection[]
  active: number
  total: number
}) {
  return (
    <SubSection
      title="Sections"
      hint={`${active} active of ${total} · QY70 layout: Intro / Main A / Main B / Fill AB / Fill BA / Ending`}
    >
      <div className="divide-y divide-border/30 rounded-lg bg-muted/20">
        <div className="grid grid-cols-[1.5rem_1fr_5rem_6rem_6rem_1fr] gap-2 px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          <span>#</span>
          <span>Name</span>
          <span>Status</span>
          <span>Phrase B</span>
          <span>Track B</span>
          <span>Active</span>
        </div>
        {sections.map((s) => (
          <div
            key={s.index}
            className={`grid grid-cols-[1.5rem_1fr_5rem_6rem_6rem_1fr] items-center gap-2 px-2 py-1.5 text-xs ${
              s.has_data ? "" : "opacity-50"
            }`}
          >
            <span className="tabular-nums text-muted-foreground">{s.index}</span>
            <span className="font-semibold">{s.name}</span>
            <span>
              {s.has_data ? (
                <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-emerald-800">
                  Active
                </span>
              ) : (
                <span className="rounded bg-muted px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Empty
                </span>
              )}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {s.has_data ? s.phrase_bytes : "—"}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {s.has_data ? s.track_bytes : "—"}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {s.active_tracks.length > 0 ? `T ${s.active_tracks.join(", ")}` : "—"}
            </span>
          </div>
        ))}
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Pattern Structure · Tracks
// ───────────────────────────────────────────────────────────────────

function TracksTable({
  tracks,
  active,
  total,
}: {
  tracks: SyxAnalysisTrack[]
  active: number
  total: number
}) {
  return (
    <SubSection
      title="Tracks"
      hint={`${active} active of ${total} · QY70 labels D1/D2/PC/BA/C1..C4 on MIDI ch 9..16`}
    >
      <div className="hidden divide-y divide-border/30 rounded-lg bg-muted/20 xl:block">
        <div className="grid grid-cols-[3.5rem_2rem_1fr_4rem_3rem_3rem_3rem_3rem] gap-2 px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          <span>Track</span>
          <span>Ch</span>
          <span>Voice</span>
          <span>B/L/P</span>
          <span>Vol</span>
          <span>Pan</span>
          <span>Rev</span>
          <span>Cho</span>
        </div>
        {tracks.map((t) => {
          const empty = !t.has_data
          return (
            <div
              key={t.index}
              className={`grid grid-cols-[3.5rem_2rem_1fr_4rem_3rem_3rem_3rem_3rem] items-center gap-2 px-2 py-1.5 text-xs ${
                empty ? "opacity-40" : "hover:bg-muted/50"
              }`}
            >
              <div className="min-w-0">
                <div className="font-semibold tabular-nums">{t.name}</div>
                <div className="truncate text-[9px] text-muted-foreground/60">
                  {t.long_name}
                </div>
              </div>
              <span className="rounded bg-foreground/5 px-1.5 py-0.5 text-center text-[10px] font-semibold tabular-nums text-foreground/70">
                {t.channel || "—"}
              </span>
              <div className="min-w-0">
                {empty ? (
                  <span className="text-muted-foreground/60">Empty</span>
                ) : (
                  <div className="flex min-w-0 items-center gap-1.5">
                    <span className="truncate font-medium">
                      {t.voice_name || `Prog ${t.program}`}
                    </span>
                    <VoiceSourceBadge source={t.voice_source} />
                  </div>
                )}
              </div>
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60">
                {empty ? "—" : `${t.bank_msb}/${t.bank_lsb}/${t.program}`}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {empty ? "—" : t.volume}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {empty ? "—" : panLabel(t.pan)}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {empty ? "—" : t.reverb_send}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {empty ? "—" : t.chorus_send}
              </span>
            </div>
          )
        })}
      </div>
      <div className="grid gap-1 sm:grid-cols-2 xl:hidden">
        {tracks.map((t) => {
          const empty = !t.has_data
          return (
            <div
              key={t.index}
              className={`flex items-start gap-2 rounded-md bg-muted/20 px-2 py-1.5 text-xs ${
                empty ? "opacity-40" : "hover:bg-muted/40"
              }`}
            >
              <div className="w-10 shrink-0">
                <div className="font-semibold tabular-nums">{t.name}</div>
                <div className="truncate text-[9px] text-muted-foreground/60">
                  {t.long_name}
                </div>
              </div>
              <span className="mt-0.5 inline-flex h-5 w-8 shrink-0 items-center justify-center rounded bg-foreground/5 text-[10px] font-semibold tabular-nums text-foreground/70">
                {t.channel || "—"}
              </span>
              <div className="min-w-0 flex-1 space-y-1">
                {empty ? (
                  <span className="text-muted-foreground/60">Empty</span>
                ) : (
                  <>
                    <div className="flex min-w-0 items-center gap-1.5">
                      <span className="truncate font-medium">
                        {t.voice_name || `Prog ${t.program}`}
                      </span>
                      <VoiceSourceBadge source={t.voice_source} />
                      <span className="shrink-0 font-mono text-[9px] tabular-nums text-muted-foreground/50">
                        {t.bank_msb}/{t.bank_lsb}/{t.program}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <LevelBar value={t.volume} max={127} />
                      <PanIndicator value={t.pan} />
                    </div>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9px] tabular-nums text-muted-foreground/70">
                      <span>Vol {t.volume}</span>
                      <span>Pan {panLabel(t.pan)}</span>
                      {t.reverb_send > 0 && <span>Rev {t.reverb_send}</span>}
                      {t.chorus_send > 0 && <span>Cho {t.chorus_send}</span>}
                      {t.active_sections.length > 0 && (
                        <span>in {t.active_sections.join(", ")}</span>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Musical Content · Pattern Slots
// ───────────────────────────────────────────────────────────────────

function SlotsBlock({ slots }: { slots: SyxAnalysisResponse["pattern_directory"] }) {
  if (slots.length === 0) return null
  return (
    <SubSection
      title="Pattern Slots Directory"
      hint="Slot names declared in the bulk (AH=0x05, BULK_ALL only)"
    >
      <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-4">
        {slots.map((s) => (
          <div
            key={s.slot}
            className="flex items-center gap-2 rounded-md bg-muted/20 px-2 py-1 text-xs hover:bg-muted/40"
          >
            <span className="w-8 shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
              U{s.slot.toString().padStart(2, "0")}
            </span>
            <span className="truncate">{s.name}</span>
          </div>
        ))}
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Diagnostics · Warning + SysEx stats
// ───────────────────────────────────────────────────────────────────

function WarningsBlock({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null
  return (
    <div className="rounded-xl border border-amber-200/80 bg-amber-50 px-4 py-3 text-amber-950">
      <p className="text-[10px] uppercase tracking-[0.2em] text-amber-700">
        Voice Info Partial
      </p>
      {warnings.map((w, i) => (
        <p key={i} className="mt-1 text-sm leading-6">
          {w}
        </p>
      ))}
    </div>
  )
}

function SysExStatsBlock({ stats }: { stats: SyxAnalysisResponse["stats"] }) {
  if (!stats) return null
  return (
    <SubSection
      title="SysEx Message Statistics"
      hint="Raw message counts and 7-bit packing expansion"
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
        <Metric label="Total msgs" value={stats.total_messages} />
        <Metric label="Bulk dumps" value={stats.bulk_dump_messages} />
        <Metric label="Param msgs" value={stats.parameter_messages} />
        <Metric
          label="Checksums"
          value={
            stats.invalid_checksums === 0
              ? `${stats.valid_checksums} valid`
              : `${stats.valid_checksums}✓ / ${stats.invalid_checksums}✗`
          }
          tone={stats.invalid_checksums === 0 ? "default" : "warn"}
        />
        <Metric label="Encoded" value={`${stats.total_encoded_bytes} B`} />
        <Metric label="Decoded" value={`${stats.total_decoded_bytes} B`} />
        <Metric
          label="Expansion"
          value={
            stats.total_encoded_bytes > 0
              ? `${(
                  (1 - stats.total_decoded_bytes / stats.total_encoded_bytes) *
                  100
                ).toFixed(1)}%`
              : "—"
          }
        />
      </div>
    </SubSection>
  )
}

// ───────────────────────────────────────────────────────────────────
// Main panel
// ───────────────────────────────────────────────────────────────────

export function SyxAnalysisPanel({
  analysis,
  device,
  deviceId,
}: {
  analysis: SyxAnalysisResponse
  device: UdmDevice
  deviceId: string
}) {
  if (!analysis.available) return null

  const hasEffects = analysis.reverb || analysis.chorus || analysis.variation
  const hasMultiPart = device.multi_part.some((p) => {
    const v = (p as Record<string, unknown>).voice as
      | { bank_msb?: number; bank_lsb?: number; program?: number }
      | undefined
    return v && (v.bank_msb || v.bank_lsb || v.program)
  })
  const hasSystem =
    !!analysis.system &&
    (analysis.system.master_tune_cents !== null ||
      analysis.system.master_volume !== null ||
      (analysis.system.master_attenuator ?? 0) > 0 ||
      (analysis.system.transpose ?? 0) !== 0 ||
      analysis.system.xg_system_on)
  const hasDrumKits = analysis.drum_kits.length > 0
  const hasSlots = analysis.pattern_directory.length > 0

  return (
    <div className="space-y-10">
      {/* L1 — Sound Engine */}
      {(hasEffects || hasMultiPart || hasSystem || hasDrumKits) && (
        <SectionGroup
          eyebrow="Sound Engine"
          title="How it sounds"
          description="Global effects, per-part voices, tuning and drum-kit edits. Voices that the bulk doesn't carry (XG ROM index is opaque) are filled in after a Merge XG capture."
        >
          {hasEffects && <EffectsBlock analysis={analysis} />}
          {hasMultiPart && <MultiPartBlock device={device} />}
          {hasSystem && <SystemBlock system={analysis.system} />}
          {hasDrumKits && <DrumKitsBlock kits={analysis.drum_kits} />}
        </SectionGroup>
      )}

      <Divider />

      {/* L1 — Pattern Structure */}
      <SectionGroup
        eyebrow="Pattern Structure"
        title="How it's organized"
        description="On QY70 each pattern has up to 6 sections × 8 tracks. Active tracks carry event data in the bulk; the rest are zero-padded."
      >
        {analysis.sections.length > 0 && (
          <SectionsTable
            sections={analysis.sections}
            active={analysis.active_section_count}
            total={analysis.section_total}
          />
        )}
        {analysis.tracks.length > 0 && (
          <TracksTable
            tracks={analysis.tracks}
            active={analysis.active_track_count}
            total={analysis.track_total}
          />
        )}
      </SectionGroup>

      <Divider />

      {/* L1 — Musical Content */}
      <SectionGroup
        eyebrow="Musical Content"
        title="What it plays"
        description="Note events decoded from the bulk via the R=9×(i+1) barrel-rotation decoder (proven 7/7 on known_pattern.syx). Tracks whose plausibility drops below 60 % are skipped to avoid ghost notes from factory dense styles."
      >
        <PhraseEvents deviceId={deviceId} />
        {hasSlots && <SlotsBlock slots={analysis.pattern_directory} />}
      </SectionGroup>

      <Divider />

      {/* L1 — Diagnostics */}
      <SectionGroup
        eyebrow="Diagnostics"
        title="Technical details"
        description="Warnings, SysEx message counts and 7-bit expansion — useful for troubleshooting imports and verifying checksum integrity."
      >
        {analysis.warnings.length > 0 && (
          <WarningsBlock warnings={analysis.warnings} />
        )}
        {analysis.stats && <SysExStatsBlock stats={analysis.stats} />}
      </SectionGroup>
    </div>
  )
}
