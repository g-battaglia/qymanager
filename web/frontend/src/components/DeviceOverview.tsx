import type { UdmDevice } from "@/lib/types"
import {
  countDrumNoteOverrides,
  describeImportContext,
  getFirstPattern,
} from "@/lib/udm"
import { useSyxAnalysis } from "@/lib/queries"
import { PatternOverview } from "@/components/PatternOverview"
import { SoundOverview } from "@/components/SoundOverview"
import { PhraseEvents } from "@/components/PhraseEvents"
import { SyxAnalysisPanel } from "@/components/SyxAnalysisPanel"

function SourcePill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 rounded-xl border border-border/70 bg-background/80 px-3 py-1.5">
      <span className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </span>
      <span className="text-xs font-semibold">{value}</span>
    </div>
  )
}

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-base font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function DeviceOverview({
  device,
  deviceId,
  onSelectNode,
}: {
  device: UdmDevice
  deviceId: string
  onSelectNode: (path: string) => void
}) {
  const firstPattern = getFirstPattern(device)
  const firstPatternName = firstPattern?.["name"]
  const firstPatternTempo = firstPattern?.["tempo_bpm"]
  const firstPatternMeasures = firstPattern?.["measures"]
  const udmTimeSig =
    firstPattern &&
    typeof firstPattern["time_sig"] === "object" &&
    firstPattern["time_sig"] !== null
      ? `${String((firstPattern["time_sig"] as Record<string, unknown>).numerator)}/${String((firstPattern["time_sig"] as Record<string, unknown>).denominator)}`
      : "-"
  const udmTempo = firstPatternTempo ? `${String(firstPatternTempo)} BPM` : "-"
  const measures = firstPatternMeasures ? `${String(firstPatternMeasures)} bars` : "-"
  const udmPatternName =
    typeof firstPatternName === "string" && firstPatternName.trim()
      ? firstPatternName
      : ""
  const importContext = describeImportContext(device)

  const { data: syx } = useSyxAnalysis(deviceId)
  const syxAvailable = syx?.available ?? false
  const patternName =
    (syxAvailable && syx?.pattern_name) || udmPatternName || "Untitled pattern"
  const tempo = syxAvailable && syx?.tempo ? `${syx.tempo} BPM` : udmTempo
  const timeSig = syxAvailable && syx?.time_signature ? syx.time_signature : udmTimeSig

  return (
    <div className="space-y-10">
      {/* ── HERO ─────────────────────────────────────────────────── */}
      <section className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-muted-foreground">
              Imported Device
            </p>
            <h2 className="text-3xl font-semibold tracking-tight">
              {String(device.model).toUpperCase()}
              {patternName !== "Untitled pattern" ? ` · ${patternName}` : ""}
            </h2>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{tempo}</span>
              <span>·</span>
              <span>{timeSig}</span>
              <span>·</span>
              <span>{measures}</span>
              {syxAvailable && syx?.format_type && (
                <>
                  <span>·</span>
                  <span className="uppercase tracking-wider">
                    {syx.format_type}
                  </span>
                </>
              )}
            </p>
            <p className="max-w-2xl text-xs leading-5 text-muted-foreground">
              The page is organized as <em>how it sounds</em> → <em>how it's organized</em>{" "}
              → <em>what it plays</em> → <em>diagnostics</em>. Use the left navigator
              to drill into the raw UDM structure; every field backed by the schema is
              editable inline.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <SourcePill
              label="Source"
              value={String(device.source_format ?? "unknown").toUpperCase()}
            />
            <SourcePill label="UDM" value={String(device.udm_version ?? "1.0")} />
          </div>
        </div>

        {importContext && (
          <div className="mt-5 rounded-xl border border-amber-200/80 bg-amber-50 px-4 py-3 text-amber-950">
            <p className="text-[10px] uppercase tracking-[0.2em] text-amber-700">
              Import Note
            </p>
            <p className="mt-1 text-sm leading-6">{importContext}</p>
          </div>
        )}

        <div className="mt-6 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-border/40 pt-4 sm:grid-cols-4 lg:grid-cols-6">
          {syxAvailable && syx ? (
            <>
              <HeroStat
                label="File Size"
                value={formatBytes(syx.filesize)}
              />
              <HeroStat
                label="Density"
                value={`${syx.data_density.toFixed(0)}%`}
              />
              <HeroStat
                label="Sections"
                value={`${syx.active_section_count}/${syx.section_total}`}
              />
              <HeroStat
                label="Tracks"
                value={`${syx.active_track_count}/${syx.track_total}`}
              />
              <HeroStat
                label="Patterns"
                value={String(device.patterns.length)}
              />
              <HeroStat
                label="User Phrases"
                value={String(device.phrases_user.length)}
              />
            </>
          ) : (
            <>
              <HeroStat label="Patterns" value={String(device.patterns.length)} />
              <HeroStat label="Songs" value={String(device.songs.length)} />
              <HeroStat label="Parts" value={String(device.multi_part.length)} />
              <HeroStat
                label="Drum Overrides"
                value={String(countDrumNoteOverrides(device))}
              />
              <HeroStat
                label="User Phrases"
                value={String(device.phrases_user.length)}
              />
            </>
          )}
        </div>
      </section>

      {/* ── CONTENT ──────────────────────────────────────────────── */}
      {syxAvailable && syx ? (
        <SyxAnalysisPanel analysis={syx} device={device} deviceId={deviceId} />
      ) : (
        // Non-syx formats keep the legacy UDM panels; each renders as a
        // section and the divider between them keeps the flat hierarchy.
        <>
          <SoundOverview device={device} onSelectNode={onSelectNode} />
          <hr className="border-t border-border/40" />
          <PhraseEvents deviceId={deviceId} />
          <hr className="border-t border-border/40" />
          <PatternOverview device={device} onSelectNode={onSelectNode} />
        </>
      )}

      {/* ── FOOTER ───────────────────────────────────────────────── */}
      <footer className="border-t border-border/40 pt-5 pb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-muted-foreground">
          Editable Now
        </p>
        <p className="mt-2 max-w-3xl text-xs leading-5 text-muted-foreground">
          System (master tune, volume, transpose, sync), Effects (reverb, chorus,
          variation), Multi Part (voice, pan, sends, filter, EG) and Drum Setup
          (note-level tuning, level, pan, sends, filter). Pattern and song
          structures are visible here but many fields remain read-only.
        </p>
      </footer>
    </div>
  )
}
