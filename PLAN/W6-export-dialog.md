# W6 — ExportDialog + WarningList + download

> **Obiettivo**: dialog per esportare il device. Selettore formato, opzioni target_model
> (conversione cross-device), keep/drop per lossy policy, mostra warnings.

## Componente `src/components/ExportDialog.tsx`

```tsx
import { useState } from "react"
import { api } from "@/lib/api"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { WarningList } from "./WarningList"

const FORMATS = [
  { value: "syx", label: "Yamaha SysEx (.syx)" },
  { value: "q7p", label: "QY700 Pattern (.q7p)" },
  { value: "mid", label: "Standard MIDI (.mid)" },
]

const LOSSY_GROUPS = [
  "fill-cc-dd", "variation-effect", "parts-17-32", "drum-kit-2", "song-tracks-17-32",
]

export function ExportDialog({ deviceId, currentModel }: { deviceId: string; currentModel: string }) {
  const [format, setFormat] = useState("syx")
  const [target, setTarget] = useState<string>("same")
  const [drop, setDrop] = useState<string[]>([])
  const [keep, setKeep] = useState<string[]>([])
  const [warnings, setWarnings] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleExport = async () => {
    setBusy(true)
    setErr(null)
    try {
      const opts: {
        format: string; target_model?: string; keep?: string[]; drop?: string[]
      } = { format }
      if (target !== "same") opts.target_model = target
      if (drop.length) opts.drop = drop
      if (keep.length) opts.keep = keep

      const blob = await api.exportDevice(deviceId, opts)

      // extract X-Warnings è un header che non arriva via blob; il server mette
      // JSON separato? Dipende dall'implementazione backend.
      // Per W6 semplice assumiamo: warnings = [] se target == same, altrimenti
      // chiamata separata a /api/convert-dry-run che ritorna warnings.

      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `export.${format}`
      a.click()
      URL.revokeObjectURL(url)
      setWarnings([])
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>Export...</Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Export device</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Format</Label>
            <Select value={format} onValueChange={setFormat}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {FORMATS.map((f) => (
                  <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Target device</Label>
            <Select value={target} onValueChange={setTarget}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="same">Same as source ({currentModel})</SelectItem>
                <SelectItem value="QY70">QY70</SelectItem>
                <SelectItem value="QY700">QY700</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {target !== "same" && (
            <>
              <div>
                <Label>Drop groups (lossy)</Label>
                <div className="grid grid-cols-2 gap-2">
                  {LOSSY_GROUPS.map((g) => (
                    <label key={g} className="flex items-center gap-2">
                      <Checkbox
                        checked={drop.includes(g)}
                        onCheckedChange={(v) =>
                          setDrop(v ? [...drop, g] : drop.filter((x) => x !== g))
                        }
                      />
                      <span>{g}</span>
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}
          {warnings && <WarningList warnings={warnings} />}
          {err && <p className="text-red-500">{err}</p>}
        </div>
        <DialogFooter>
          <Button onClick={handleExport} disabled={busy}>
            {busy ? "Exporting..." : "Export & Download"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

## Componente `src/components/WarningList.tsx`

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export function WarningList({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return <p className="text-sm text-muted-foreground">No warnings.</p>
  }
  return (
    <div>
      <p className="mb-2 text-sm">Conversion warnings:</p>
      <Table>
        <TableHeader>
          <TableRow><TableHead>Warning</TableHead></TableRow>
        </TableHeader>
        <TableBody>
          {warnings.map((w, i) => (
            <TableRow key={i}><TableCell className="font-mono text-xs">{w}</TableCell></TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

## Backend ajuste per X-Warnings header

Il backend W1 già mette `X-Warnings: w1|w2|...` in header. Per leggere il header dal client
(fetch + blob), serve un'API wrapper che ritorna `{blob, warnings}`:

```ts
// in lib/api.ts, sostituisce exportDevice:
exportDevice: async (id, opts) => {
  const res = await fetch(`/api/devices/${id}/export`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts),
  })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  const warnings = (res.headers.get("X-Warnings") ?? "").split("|").filter(Boolean)
  const blob = await res.blob()
  return { blob, warnings }
}
```

Aggiornare `types.ts` e il componente di conseguenza.

## Integrazione in DeviceView

```tsx
import { ExportDialog } from "@/components/ExportDialog"

<header className="border-b px-8 py-3 flex items-center justify-between">
  <h1 className="text-lg font-semibold">{(data.device as any).model}</h1>
  <ExportDialog deviceId={id!} currentModel={(data.device as any).model} />
</header>
```

## Test Vitest

`src/test/__tests__/ExportDialog.test.tsx`:

1. `opens dialog and shows format options`
2. `export triggers download blob` — mock fetch + URL.createObjectURL stub
3. `shows lossy drop groups only when target != same`

`src/test/__tests__/WarningList.test.tsx`:

1. `empty warnings shows placeholder`
2. `renders warnings in table`

## Task granulari

1. `shadcn add dialog table label` se mancano
2. Aggiornare `src/lib/api.ts` `exportDevice` per leggere header
3. Aggiornare `src/lib/types.ts` se serve
4. Creare `src/components/WarningList.tsx`
5. Creare `src/components/ExportDialog.tsx`
6. Integrare in `src/routes/DeviceView.tsx`
7. Test Vitest
8. Commit: `feat(web-frontend): W6 — ExportDialog + WarningList + lossy conversion`

## Verifica

```bash
cd web/frontend
npm test
npm run build

# Smoke: upload QY70 device → Export... → target=QY700 → drop fill-cc-dd → download
```
