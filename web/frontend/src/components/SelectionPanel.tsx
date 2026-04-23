import { FieldEditor, matchSchema } from "@/components/FieldEditor"
import type { SchemaEntry } from "@/lib/types"
import {
  formatPathLabel,
  getNodeSummary,
  humanizeKey,
  isScalarValue,
} from "@/lib/udm"
import { useSchema } from "@/lib/queries"

function PreviewGrid({ entries }: { entries: Array<[string, unknown]> }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-2xl border border-border/70 bg-muted/40 px-4 py-3">
          <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">
            {humanizeKey(key)}
          </p>
          <p className="mt-2 text-sm font-medium text-foreground">
            {getNodeSummary(value)}
          </p>
        </div>
      ))}
    </div>
  )
}

function ValueTypeBadge({ value }: { value: unknown }) {
  let label = "Value"
  if (Array.isArray(value)) {
    label = "Array"
  } else if (value === null) {
    label = "Null"
  } else if (typeof value === "object") {
    label = "Object"
  } else {
    label = typeof value
  }
  return (
    <span className="rounded-full border border-border/80 bg-muted px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
      {label}
    </span>
  )
}

function SchemaBadge({ entry }: { entry: SchemaEntry | null }) {
  if (!entry) {
    return (
      <span className="rounded-full border border-border/80 bg-background px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
        Read-only here
      </span>
    )
  }
  return (
    <span className="rounded-full border border-emerald-300/80 bg-emerald-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-emerald-800">
      Editable
    </span>
  )
}

export function SelectionPanel({
  deviceId,
  path,
  value,
}: {
  deviceId: string
  path: string
  value: unknown
}) {
  const { data: schema } = useSchema()
  const entry = schema ? matchSchema(path, schema.paths as SchemaEntry[]) : null
  const isScalar = isScalarValue(value)
  const objectEntries =
    value && typeof value === "object" && !Array.isArray(value)
      ? Object.entries(value as Record<string, unknown>)
      : []
  const arrayEntries = Array.isArray(value)
    ? value.map((item, index) => [`[${index}]`, item] as [string, unknown])
    : []
  const previewEntries = (Array.isArray(value) ? arrayEntries : objectEntries).slice(0, 10)

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
              Selected Node
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">
              {formatPathLabel(path)}
            </h2>
            <p className="mt-2 font-mono text-xs text-muted-foreground">{path}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ValueTypeBadge value={value} />
            <SchemaBadge entry={entry} />
          </div>
        </div>
      </section>

      {isScalar ? (
        <section className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Current Value
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">
            {getNodeSummary(value)}
          </p>
          <div className="mt-6">
            <FieldEditor deviceId={deviceId} path={path} currentValue={value} />
          </div>
        </section>
      ) : (
        <section className="rounded-[2rem] border border-border/70 bg-card px-6 py-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                Structure Preview
              </p>
              <h3 className="mt-2 text-xl font-semibold">
                {Array.isArray(value)
                  ? `${arrayEntries.length} nested items`
                  : `${objectEntries.length} nested fields`}
              </h3>
            </div>
          </div>
          {previewEntries.length > 0 ? (
            <div className="mt-5">
              <PreviewGrid entries={previewEntries} />
            </div>
          ) : (
            <p className="mt-5 text-sm text-muted-foreground">This node has no nested values.</p>
          )}

          <details className="mt-6 rounded-2xl border border-border/70 bg-muted/30 px-4 py-4">
            <summary className="cursor-pointer text-sm font-medium">
              Raw JSON preview
            </summary>
            <pre className="mt-4 overflow-auto rounded-xl bg-background p-4 text-xs leading-6 text-foreground">
              {JSON.stringify(value, null, 2)}
            </pre>
          </details>
        </section>
      )}
    </div>
  )
}
