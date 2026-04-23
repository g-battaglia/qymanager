import { Uploader } from "@/components/Uploader"

function FormatBadge({ ext, label }: { ext: string; label: string }) {
  return (
    <span className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
      <span className="font-semibold text-foreground">{ext}</span>{" "}
      {label}
    </span>
  )
}

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(15,23,42,0.05),_transparent_28rem)]">
      <header className="border-b border-border/70">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
              Yamaha QY70 / QY700
            </p>
            <h1 className="text-xl font-semibold tracking-tight">QYConv</h1>
          </div>
          <span className="text-xs text-muted-foreground">Web Editor v1.0</span>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-12">
        <section className="mb-12">
          <h2 className="text-3xl font-semibold tracking-tight">
            Inspect, edit, convert
          </h2>
          <p className="mt-3 max-w-xl text-base leading-7 text-muted-foreground">
            Upload a QY70 SysEx dump or QY700 pattern file. Browse the full UDM
            structure, edit schema-backed parameters, and export to any supported
            format.
          </p>
        </section>

        <section className="mb-10">
          <Uploader />
        </section>

        <section className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Supported formats
          </span>
          <FormatBadge ext=".syx" label="QY70 SysEx" />
          <FormatBadge ext=".q7p" label="QY700 Pattern" />
          <FormatBadge ext=".blk" label="Bulk Dump" />
          <FormatBadge ext=".mid" label="Standard MIDI" />
        </section>
      </div>
    </div>
  )
}
