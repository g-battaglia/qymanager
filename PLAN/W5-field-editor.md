# W5 — FieldEditor schema-driven + PATCH wiring

> **Obiettivo**: editor del campo selezionato nel tree. Legge `/api/schema` per sapere se è
> range (→ Slider+Input) o enum (→ Select). PATCH con optimistic update, toast su errore.

## Componente `src/components/FieldEditor.tsx`

```tsx
import { useMemo } from "react"
import { useSchema, usePatchField } from "@/lib/queries"
import type { SchemaEntry } from "@/lib/types"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select"
import { useToast } from "@/components/ui/use-toast"

function matchSchema(path: string, entries: SchemaEntry[]): SchemaEntry | null {
  const direct = entries.find((e) => e.path === path)
  if (direct) return direct
  // pattern match: multi_part[3].volume → multi_part[*].volume
  const pattern = path.replace(/\[\d+\]/g, "[*]")
  return entries.find((e) => e.path === pattern) ?? null
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
  const { toast } = useToast()

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
            toast({ title: "Validation error", description: r.errors.join("; "),
                    variant: "destructive" })
          }
        },
        onError: (e) => toast({ title: "Network error", description: String(e),
                                variant: "destructive" }),
      }
    )
  }

  if (!entry) {
    return (
      <div>
        <p className="text-muted-foreground mb-2">Raw value (no schema):</p>
        <Input
          defaultValue={String(currentValue)}
          onBlur={(e) => handleChange(e.target.value)}
          disabled={isPending}
        />
      </div>
    )
  }

  if (entry.kind === "range" && entry.lo !== undefined && entry.hi !== undefined) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">Range [{entry.lo}, {entry.hi}]</p>
        <Slider
          min={entry.lo}
          max={entry.hi}
          step={1}
          value={[Number(currentValue) || entry.lo]}
          onValueCommit={([v]) => handleChange(v)}
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
      <Select defaultValue={String(currentValue)} onValueChange={handleChange}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          {entry.options.map((opt) => (
            <SelectItem key={opt} value={opt}>{opt}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  return <p className="text-muted-foreground">Unsupported schema kind</p>
}
```

## Hook `src/components/ui/use-toast.ts`

Generato da `shadcn add toast`. Verifica esista o aggiungilo.

## Utilità per estrarre il valore corrente dal path

`src/lib/path.ts`:

```ts
export function getByPath(obj: unknown, path: string): unknown {
  let cur: unknown = obj
  for (const seg of path.split(/\.|\[|\]\.?/).filter(Boolean)) {
    if (cur == null) return undefined
    if (/^\d+$/.test(seg)) {
      cur = (cur as unknown[])[Number(seg)]
    } else {
      cur = (cur as Record<string, unknown>)[seg]
    }
  }
  return cur
}
```

## Integrazione in DeviceView

Aggiornare `src/routes/DeviceView.tsx`:

```tsx
import { FieldEditor } from "@/components/FieldEditor"
import { getByPath } from "@/lib/path"

// ... dentro il component:
<main className="p-8">
  {selected ? (
    <>
      <h2 className="text-xl font-bold mb-4">{selected}</h2>
      <FieldEditor
        deviceId={id!}
        path={selected}
        currentValue={getByPath(data.device, selected)}
      />
    </>
  ) : (
    <p className="text-muted-foreground">Seleziona un campo dal tree</p>
  )}
</main>
```

Per i toast, aggiungi `<Toaster />` in `App.tsx`.

## Test Vitest

`src/test/__tests__/FieldEditor.test.tsx`:

1. `renders slider for range field` — mock schema con `{path: "system.master_volume", kind: "range", lo: 0, hi: 127}` + mock `/api/devices/:id` → verifica `<Slider>` renderizzato
2. `renders select for enum field` — mock schema con enum
3. `on slider commit, calls PATCH` — mock fetch + interact → verifica POST inviato
4. `shows toast on validation error` — PATCH ritorna `{errors: ["out of range"]}` → verifica toast

`src/test/__tests__/path.test.ts`:

1. `getByPath navigates nested objects`
2. `getByPath handles array index`

## Task granulari

1. Verificare `shadcn add toast` e altri componenti richiesti
2. Creare `src/lib/path.ts` con `getByPath`
3. Creare `src/components/FieldEditor.tsx`
4. Integrare `<Toaster />` in `App.tsx`
5. Aggiornare `src/routes/DeviceView.tsx` per renderizzare FieldEditor
6. Test Vitest (2 file, 6 test)
7. Commit: `feat(web-frontend): W5 — FieldEditor schema-driven with PATCH`

## Verifica

```bash
cd web/frontend
npm run typecheck
npm test
npm run build

# Smoke manuale:
npm run dev
# upload SGT.syx → clicca system.master_volume → muovi slider → valore persiste
```
