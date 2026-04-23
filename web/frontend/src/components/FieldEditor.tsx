import { useEffect, useMemo, useState } from "react"
import { useSchema, usePatchField } from "@/lib/queries"
import type { SchemaEntry } from "@/lib/types"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"
import { toast } from "sonner"
import { humanizeKey } from "@/lib/udm"

export function matchSchema(
  path: string,
  entries: SchemaEntry[],
): SchemaEntry | null {
  const direct = entries.find((e) => e.path === path)
  if (direct) return direct
  const pattern = path.replace(/\[\d+\]/g, "[*]")
  return entries.find((e) => e.path === pattern) ?? null
}

function inferRawInput(value: unknown, raw: string): unknown {
  if (typeof value === "number") {
    return Number(raw)
  }
  if (typeof value === "boolean") {
    return raw === "true"
  }
  return raw
}

export function FieldEditor({
  deviceId,
  path,
  currentValue,
}: {
  deviceId: string
  path: string
  currentValue: unknown
}) {
  const { data: schema } = useSchema()
  const { mutate, isPending } = usePatchField(deviceId)
  const [rawValue, setRawValue] = useState(String(currentValue ?? ""))

  useEffect(() => {
    setRawValue(String(currentValue ?? ""))
  }, [currentValue, path])

  const entry = useMemo(() => {
    if (!schema) return null
    return matchSchema(path, schema.paths as SchemaEntry[])
  }, [schema, path])

  const handleChange = (value: unknown) => {
    mutate(
      { path, value },
      {
        onSuccess: (r) => {
          if (r.errors.length > 0) {
            toast.error("Validation error", {
              description: r.errors.join("; "),
            })
          }
        },
        onError: (e) => {
          toast.error("Network error", { description: String(e) })
        },
      },
    )
  }

  if (!entry) {
    const lastSegment = path.split(".").at(-1)?.replace(/\[\d+\]/g, "") ?? path
    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-dashed border-border/80 bg-muted/35 px-4 py-4">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Basic Editor
          </p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            <span className="font-medium text-foreground">{humanizeKey(lastSegment)}</span>{" "}
            is not part of the explicit schema-backed web editor yet. You can still edit its
            raw scalar value here using the current field type.
          </p>
        </div>

        {typeof currentValue === "boolean" ? (
          <Select
            defaultValue={String(currentValue)}
            onValueChange={(v: string | null) => {
              if (v !== null) handleChange(v === "true")
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">True</SelectItem>
              <SelectItem value="false">False</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Input
            type={typeof currentValue === "number" ? "number" : "text"}
            value={rawValue}
            onChange={(e) => setRawValue(e.target.value)}
            onBlur={(e) => handleChange(inferRawInput(currentValue, e.target.value))}
            disabled={isPending}
          />
        )}
      </div>
    )
  }

  if (
    entry.kind === "range" &&
    entry.lo !== undefined &&
    entry.hi !== undefined
  ) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Range [{entry.lo}, {entry.hi}]
        </p>
        <Slider
          min={entry.lo}
          max={entry.hi}
          step={1}
          value={[Number(currentValue) || entry.lo]}
          onValueCommitted={(v: number | readonly number[]) => {
            const val = Array.isArray(v) ? v[0] : v
            handleChange(val)
          }}
          disabled={isPending}
        />
        <Input
          type="number"
          min={entry.lo}
          max={entry.hi}
          defaultValue={String(currentValue)}
          onBlur={(e) => handleChange(Number(e.target.value))}
        />
      </div>
    )
  }

  if (entry.kind === "enum" && entry.options) {
    return (
      <Select
        defaultValue={String(currentValue)}
        onValueChange={(v: string | null) => {
          if (v !== null) handleChange(v)
        }}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {entry.options.map((opt) => (
            <SelectItem key={opt} value={opt}>
              {opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  return <p className="text-muted-foreground">Unsupported schema kind</p>
}
