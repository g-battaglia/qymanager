import type { UdmDevice } from "@/lib/types"
import {
  countDrumNoteOverrides,
  describeImportContext,
  getFirstPattern,
  getPatternSections,
} from "@/lib/udm"

function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string
  value: string
  tone?: "default" | "accent"
}) {
  return (
    <div
      className={
        tone === "accent"
          ? "rounded-3xl border border-foreground/10 bg-foreground px-4 py-4 text-background shadow-sm"
          : "rounded-3xl border border-border/70 bg-card px-4 py-4 shadow-sm"
      }
    >
      <p className={tone === "accent" ? "text-xs uppercase tracking-[0.24em] text-background/70" : "text-xs uppercase tracking-[0.24em] text-muted-foreground"}>
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  )
}

function SectionPill({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-border/80 bg-muted/60 px-3 py-1 text-xs font-medium text-foreground/80">
      {label}
    </span>
  )
}

export function DeviceOverview({ device }: { device: UdmDevice }) {
  const firstPattern = getFirstPattern(device)
  const firstPatternName = firstPattern?.["name"]
  const firstPatternTempo = firstPattern?.["tempo_bpm"]
  const firstPatternMeasures = firstPattern?.["measures"]
  const timeSig =
    firstPattern &&
    typeof firstPattern["time_sig"] === "object" &&
    firstPattern["time_sig"] !== null
      ? `${String((firstPattern["time_sig"] as Record<string, unknown>).numerator)}/${String((firstPattern["time_sig"] as Record<string, unknown>).denominator)}`
      : "-"
  const tempo = firstPatternTempo ? `${String(firstPatternTempo)} BPM` : "-"
  const measures = firstPatternMeasures ? `${String(firstPatternMeasures)} bars` : "-"
  const patternName =
    typeof firstPatternName === "string" && firstPatternName.trim()
      ? firstPatternName
      : "Untitled pattern"
  const sectionLabels = getPatternSections(device)
  const importContext = describeImportContext(device)

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
              Imported Device
            </p>
            <div>
              <h2 className="text-3xl font-semibold tracking-tight">
                {String(device.model).toUpperCase()} {patternName !== "Untitled pattern" ? `· ${patternName}` : ""}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                This page is organized around the UDM model. Start from the overview cards,
                then inspect sections from the navigator on the left. Only schema-backed
                fields are directly editable.
              </p>
            </div>
          </div>
          <div className="grid min-w-[18rem] gap-3 sm:grid-cols-2">
            <StatCard label="Source" value={String(device.source_format ?? "unknown").toUpperCase()} tone="accent" />
            <StatCard label="UDM" value={String(device.udm_version ?? "1.0")} />
          </div>
        </div>
      </section>

      {importContext ? (
        <section className="rounded-[2rem] border border-amber-200/80 bg-amber-50 px-6 py-5 text-amber-950 shadow-sm">
          <p className="text-xs uppercase tracking-[0.24em] text-amber-700">Import Note</p>
          <p className="mt-2 text-sm leading-6">{importContext}</p>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Tempo" value={tempo} />
        <StatCard label="Time Signature" value={timeSig} />
        <StatCard label="Pattern Length" value={measures} />
        <StatCard label="Patterns" value={String(device.patterns.length)} />
        <StatCard label="Songs" value={String(device.songs.length)} />
        <StatCard label="Multi Parts" value={String(device.multi_part.length)} />
        <StatCard label="Drum Overrides" value={String(countDrumNoteOverrides(device))} />
        <StatCard label="User Phrases" value={String(device.phrases_user.length)} />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Visible In This Import
          </p>
          <h3 className="mt-2 text-xl font-semibold">Device structure at a glance</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            The left navigator exposes the full imported UDM structure. Use it to inspect
            system data, pattern structure, effects, phrases, utility flags, and any other
            section present in the file.
          </p>
          {sectionLabels.length > 0 ? (
            <div className="mt-5 flex flex-wrap gap-2">
              {sectionLabels.map((label) => (
                <SectionPill key={label} label={label.replace(/_/g, " ")} />
              ))}
            </div>
          ) : (
            <p className="mt-5 text-sm text-muted-foreground">No named pattern sections detected.</p>
          )}
        </div>

        <div className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Editable Now
          </p>
          <h3 className="mt-2 text-xl font-semibold">Schema-backed controls</h3>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
            <li>System: master tune, volume, transpose, sync basics.</li>
            <li>Effects: reverb, chorus, variation blocks when present.</li>
            <li>Multi Part: voice, pan, sends, filters, EG, bend, detune.</li>
            <li>Drum Setup: note-level tuning, level, pan, sends, filter, envelopes.</li>
          </ul>
          <p className="mt-4 text-sm leading-6 text-muted-foreground">
            Pattern and song structures are visible here too, but many of those fields are
            still read-only in the current web editor.
          </p>
        </div>
      </section>
    </div>
  )
}
