import type {
  SyxAnalysisResponse,
  SyxAnalysisSection,
  SyxAnalysisTrack,
} from "@/lib/types"
import { panLabel } from "@/lib/udm"

function VoiceSourceBadge({ source }: { source: SyxAnalysisTrack["voice_source"] }) {
  if (source === "none") return null
  const map: Record<string, { label: string; className: string; title: string }> = {
    db: {
      label: "DB",
      className: "bg-emerald-100 text-emerald-800",
      title: "Matched against the 23-signature pre-trained database",
    },
    class: {
      label: "class",
      className: "bg-slate-200 text-slate-700",
      title: "Only the voice category (drum/bass/chord) is known",
    },
    xg: {
      label: "XG",
      className: "bg-sky-100 text-sky-800",
      title: "Resolved via captured XG Bank/Program",
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
      <div
        className="h-full rounded-full bg-foreground/30"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function TrackRow({ track }: { track: SyxAnalysisTrack }) {
  const empty = !track.has_data
  return (
    <div
      className={`grid grid-cols-[3.5rem_2rem_1fr_4rem_3rem_3rem_3rem_3rem] items-center gap-2 rounded-md px-2 py-1.5 text-xs ${
        empty ? "opacity-40" : "hover:bg-muted/50"
      }`}
    >
      <div className="min-w-0">
        <div className="font-semibold tabular-nums">{track.name}</div>
        <div className="truncate text-[9px] text-muted-foreground/60">
          {track.long_name}
        </div>
      </div>
      <span className="rounded bg-foreground/5 px-1.5 py-0.5 text-center text-[10px] font-semibold tabular-nums text-foreground/70">
        {track.channel || "-"}
      </span>
      <div className="min-w-0">
        {empty ? (
          <span className="text-muted-foreground/60">Empty</span>
        ) : (
          <div className="flex min-w-0 items-center gap-1.5">
            <span className="truncate font-medium">
              {track.voice_name || `Prog ${track.program}`}
            </span>
            <VoiceSourceBadge source={track.voice_source} />
          </div>
        )}
      </div>
      <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60">
        {empty ? "—" : `${track.bank_msb}/${track.bank_lsb}/${track.program}`}
      </span>
      <span className="tabular-nums text-muted-foreground">
        {empty ? "—" : track.volume}
      </span>
      <span className="tabular-nums text-muted-foreground">
        {empty ? "—" : panLabel(track.pan)}
      </span>
      <span className="tabular-nums text-muted-foreground">
        {empty ? "—" : track.reverb_send}
      </span>
      <span className="tabular-nums text-muted-foreground">
        {empty ? "—" : track.chorus_send}
      </span>
    </div>
  )
}

function TrackRowDetailed({ track }: { track: SyxAnalysisTrack }) {
  const empty = !track.has_data
  return (
    <div
      className={`flex items-start gap-2 rounded-md px-2 py-1.5 text-xs ${
        empty ? "opacity-40" : "hover:bg-muted/50"
      }`}
    >
      <div className="mt-0.5 w-10 shrink-0">
        <div className="font-semibold tabular-nums">{track.name}</div>
        <div className="truncate text-[9px] text-muted-foreground/60">
          {track.long_name}
        </div>
      </div>
      <span className="mt-0.5 inline-flex h-5 w-8 shrink-0 items-center justify-center rounded bg-foreground/5 text-[10px] font-semibold tabular-nums text-foreground/70">
        {track.channel || "-"}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        {empty ? (
          <span className="text-muted-foreground/60">Empty</span>
        ) : (
          <>
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="truncate font-medium">
                {track.voice_name || `Prog ${track.program}`}
              </span>
              <VoiceSourceBadge source={track.voice_source} />
              <span className="shrink-0 font-mono text-[9px] tabular-nums text-muted-foreground/50">
                {track.bank_msb}/{track.bank_lsb}/{track.program}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <LevelBar value={track.volume} max={127} />
              <PanIndicator value={track.pan} />
            </div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9px] tabular-nums text-muted-foreground/70">
              <span>Vol {track.volume}</span>
              <span>Pan {panLabel(track.pan)}</span>
              {track.reverb_send > 0 && <span>Rev {track.reverb_send}</span>}
              {track.chorus_send > 0 && <span>Cho {track.chorus_send}</span>}
              {track.active_sections.length > 0 && (
                <span>in {track.active_sections.join(", ")}</span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function SectionRow({ section }: { section: SyxAnalysisSection }) {
  return (
    <div
      className={`grid grid-cols-[1.5rem_1fr_5rem_6rem_6rem_1fr] items-center gap-2 px-2 py-1.5 text-xs ${
        section.has_data ? "" : "opacity-50"
      }`}
    >
      <span className="tabular-nums text-muted-foreground">{section.index}</span>
      <span className="font-semibold">{section.name}</span>
      <span>
        {section.has_data ? (
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
        {section.has_data ? `${section.phrase_bytes} phr` : "—"}
      </span>
      <span className="tabular-nums text-muted-foreground">
        {section.has_data ? `${section.track_bytes} trk` : "—"}
      </span>
      <span className="tabular-nums text-muted-foreground">
        {section.active_tracks.length > 0
          ? `T ${section.active_tracks.join(", ")}`
          : "—"}
      </span>
    </div>
  )
}

export function SyxAnalysisPanel({
  analysis,
}: {
  analysis: SyxAnalysisResponse
}) {
  if (!analysis.available) return null

  const effects = [
    { label: "Reverb", effect: analysis.reverb },
    { label: "Chorus", effect: analysis.chorus },
    { label: "Variation", effect: analysis.variation },
  ].filter((e) => e.effect !== null) as Array<{
    label: string
    effect: NonNullable<(typeof analysis)["reverb"]>
  }>

  return (
    <div className="space-y-6">
      {analysis.warnings.length > 0 && (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50 px-4 py-3 text-amber-950">
          <p className="text-[10px] uppercase tracking-[0.2em] text-amber-700">
            Voice Info Partial
          </p>
          {analysis.warnings.map((w, i) => (
            <p key={i} className="mt-1 text-sm leading-6">
              {w}
            </p>
          ))}
        </div>
      )}

      {effects.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Global Effects
          </p>
          <h3 className="mt-2 text-xl font-semibold">Reverb / Chorus / Variation</h3>
          <div className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
            {effects.map(({ label, effect }) => (
              <div key={label} className="flex items-baseline justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    {label}
                  </p>
                  <p className="mt-0.5 truncate text-base font-semibold">
                    {effect.name}
                  </p>
                </div>
                <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground/60">
                  {effect.msb.toString(16).toUpperCase().padStart(2, "0")}/
                  {effect.lsb.toString(16).toUpperCase().padStart(2, "0")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {analysis.sections.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Pattern Structure
          </p>
          <h3 className="mt-2 text-xl font-semibold">
            Sections · {analysis.active_section_count} active of {analysis.section_total}
          </h3>
          <div className="mt-3 divide-y divide-border/30">
            <div className="grid grid-cols-[1.5rem_1fr_5rem_6rem_6rem_1fr] gap-2 px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              <span>#</span>
              <span>Name</span>
              <span>Status</span>
              <span>Phrase</span>
              <span>Tracks</span>
              <span>Active</span>
            </div>
            {analysis.sections.map((s) => (
              <SectionRow key={s.index} section={s} />
            ))}
          </div>
        </div>
      )}

      {analysis.tracks.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Track Configuration
          </p>
          <h3 className="mt-2 text-xl font-semibold">
            Tracks · {analysis.active_track_count} active of {analysis.track_total}
          </h3>

          <div className="mt-3 hidden divide-y divide-border/30 xl:block">
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
            {analysis.tracks.map((t) => (
              <TrackRow key={t.index} track={t} />
            ))}
          </div>

          <div className="mt-3 grid gap-1 sm:grid-cols-2 xl:hidden">
            {analysis.tracks.map((t) => (
              <TrackRowDetailed key={t.index} track={t} />
            ))}
          </div>
        </div>
      )}

      {analysis.system && (
        analysis.system.master_tune_cents !== null ||
        analysis.system.master_volume !== null ||
        analysis.system.master_attenuator !== null ||
        analysis.system.transpose !== null ||
        analysis.system.xg_system_on
      ) ? (
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            XG System
          </p>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {analysis.system.master_tune_cents !== null && (
              <Metric
                label="Master Tune"
                value={`${
                  analysis.system.master_tune_cents > 0 ? "+" : ""
                }${analysis.system.master_tune_cents} ¢`}
              />
            )}
            {analysis.system.master_volume !== null && (
              <Metric label="Master Vol" value={analysis.system.master_volume} />
            )}
            {analysis.system.master_attenuator !== null &&
              analysis.system.master_attenuator > 0 && (
                <Metric label="Attenuator" value={analysis.system.master_attenuator} />
              )}
            {analysis.system.transpose !== null &&
              analysis.system.transpose !== 0 && (
                <Metric
                  label="Transpose"
                  value={`${
                    analysis.system.transpose > 0 ? "+" : ""
                  }${analysis.system.transpose} st`}
                />
              )}
            {analysis.system.xg_system_on && (
              <Metric label="XG On" value="✓" />
            )}
          </div>
        </div>
      ) : null}

      {analysis.pattern_directory.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Pattern Slots
          </p>
          <div className="mt-2 grid gap-1 sm:grid-cols-2 lg:grid-cols-4">
            {analysis.pattern_directory.map((s) => (
              <div
                key={s.slot}
                className="flex items-center gap-2 rounded-md px-2 py-1 text-xs hover:bg-muted/40"
              >
                <span className="w-8 shrink-0 font-mono text-[10px] tabular-nums text-muted-foreground">
                  U{s.slot.toString().padStart(2, "0")}
                </span>
                <span className="truncate">{s.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {analysis.drum_kits.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            XG Drum Kits
          </p>
          {analysis.drum_kits.map((kit) => (
            <div key={kit.kit_index} className="mt-2">
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
      )}

      {analysis.stats && (
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            SysEx Message Statistics
          </p>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
            <Metric label="Total msgs" value={analysis.stats.total_messages} />
            <Metric label="Bulk dumps" value={analysis.stats.bulk_dump_messages} />
            <Metric label="Param msgs" value={analysis.stats.parameter_messages} />
            <Metric
              label="Checksums"
              value={
                analysis.stats.invalid_checksums === 0
                  ? `${analysis.stats.valid_checksums} valid`
                  : `${analysis.stats.valid_checksums}✓ / ${analysis.stats.invalid_checksums}✗`
              }
              tone={
                analysis.stats.invalid_checksums === 0 ? "default" : "warn"
              }
            />
            <Metric
              label="Encoded"
              value={`${analysis.stats.total_encoded_bytes} B`}
            />
            <Metric
              label="Decoded"
              value={`${analysis.stats.total_decoded_bytes} B`}
            />
            <Metric
              label="Expansion"
              value={
                analysis.stats.total_encoded_bytes > 0
                  ? `${(
                      (1 -
                        analysis.stats.total_decoded_bytes /
                          analysis.stats.total_encoded_bytes) *
                      100
                    ).toFixed(1)}%`
                  : "—"
              }
            />
          </div>
        </div>
      )}
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
