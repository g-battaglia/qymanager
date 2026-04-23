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

function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string
  value: string
  tone?: "default" | "accent"
}) {
  const toneClass =
    tone === "accent"
      ? "border-foreground/10 bg-foreground text-background"
      : "border-border/70 bg-card"
  return (
    <div className={`rounded-2xl border px-4 py-3 ${toneClass}`}>
      <p
        className={
          tone === "accent"
            ? "text-[10px] uppercase tracking-[0.24em] text-background/70"
            : "text-[10px] uppercase tracking-[0.24em] text-muted-foreground"
        }
      >
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function Divider() {
  return <hr className="border-t border-border/40" />
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
  const measures = firstPatternMeasures
    ? `${String(firstPatternMeasures)} bars`
    : "-"
  const udmPatternName =
    typeof firstPatternName === "string" && firstPatternName.trim()
      ? firstPatternName
      : ""
  const importContext = describeImportContext(device)

  const { data: syx } = useSyxAnalysis(deviceId)
  const syxAvailable = syx?.available ?? false
  const patternName =
    (syxAvailable && syx?.pattern_name) || udmPatternName || "Untitled pattern"

  const tempo =
    syxAvailable && syx?.tempo ? `${syx.tempo} BPM` : udmTempo
  const timeSig = syxAvailable && syx?.time_signature ? syx.time_signature : udmTimeSig

  return (
    <div className="space-y-8">
      <section className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
              Imported Device
            </p>
            <h2 className="text-3xl font-semibold tracking-tight">
              {String(device.model).toUpperCase()}
              {patternName !== "Untitled pattern" ? ` · ${patternName}` : ""}
            </h2>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              This page is organized around the UDM model. Start from the overview, then
              inspect sections from the navigator on the left. Only schema-backed fields
              are directly editable.
            </p>
          </div>
          <div className="grid min-w-[16rem] gap-3 sm:grid-cols-2">
            <StatCard
              label="Source"
              value={String(device.source_format ?? "unknown").toUpperCase()}
              tone="accent"
            />
            <StatCard label="UDM" value={String(device.udm_version ?? "1.0")} />
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

        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-border/40 pt-5 sm:grid-cols-4 lg:grid-cols-8">
          <MiniStat label="Tempo" value={tempo} />
          <MiniStat label="Time Sig" value={timeSig} />
          <MiniStat label="Length" value={measures} />
          {syxAvailable && syx ? (
            <>
              <MiniStat
                label="Sections"
                value={`${syx.active_section_count}/${syx.section_total}`}
              />
              <MiniStat
                label="Tracks"
                value={`${syx.active_track_count}/${syx.track_total}`}
              />
              <MiniStat label="File Size" value={formatBytes(syx.filesize)} />
              <MiniStat
                label="Density"
                value={`${syx.data_density.toFixed(1)}%`}
              />
              <MiniStat
                label="Format"
                value={(syx.format_type ?? "-").toUpperCase()}
              />
            </>
          ) : (
            <>
              <MiniStat label="Patterns" value={String(device.patterns.length)} />
              <MiniStat label="Songs" value={String(device.songs.length)} />
              <MiniStat label="Parts" value={String(device.multi_part.length)} />
              <MiniStat
                label="Drum Overrides"
                value={String(countDrumNoteOverrides(device))}
              />
              <MiniStat
                label="User Phrases"
                value={String(device.phrases_user.length)}
              />
            </>
          )}
        </div>
      </section>

      {syxAvailable && syx ? (
        <>
          {device.multi_part.some((p) => {
            const v = p.voice as Record<string, number> | undefined
            return v && (v.bank_msb || v.bank_lsb || v.program)
          }) && (
            <>
              <SoundOverview device={device} onSelectNode={onSelectNode} />
              <Divider />
            </>
          )}
          <SyxAnalysisPanel analysis={syx} />
          <Divider />
          <PhraseEvents deviceId={deviceId} />
        </>
      ) : (
        <>
          <SoundOverview device={device} onSelectNode={onSelectNode} />
          <Divider />
          <PhraseEvents deviceId={deviceId} />
          <Divider />
          <PatternOverview device={device} onSelectNode={onSelectNode} />
        </>
      )}

      <Divider />

      <footer className="pb-4">
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Editable now
        </p>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          System (master tune, volume, transpose, sync), Effects (reverb, chorus,
          variation), Multi Part (voice, pan, sends, filter, EG) and Drum Setup
          (note-level tuning, level, pan, sends, filter). Pattern and song structures
          are visible here but many fields remain read-only.
        </p>
      </footer>
    </div>
  )
}
