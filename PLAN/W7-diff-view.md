# W7 — DiffRoute + DiffView

> **Obiettivo**: pagina `/diff` che permette di caricare 2 device e mostra le differenze
> side-by-side.

## Route `src/routes/DiffRoute.tsx`

```tsx
import { useState } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Uploader } from "@/components/Uploader"
import { DiffView } from "@/components/DiffView"
import type { DiffChange } from "@/lib/types"

export default function DiffRoute() {
  const [idA, setIdA] = useState<string | null>(null)
  const [idB, setIdB] = useState<string | null>(null)
  const [changes, setChanges] = useState<DiffChange[] | null>(null)
  const [busy, setBusy] = useState(false)

  const computeDiff = async () => {
    if (!idA || !idB) return
    setBusy(true)
    try {
      const r = await api.diff(idA, idB)
      setChanges(r.changes as DiffChange[])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Diff two devices</h1>
      <div className="grid grid-cols-2 gap-6">
        <UploadSlot label="Device A" onUploaded={setIdA} current={idA} />
        <UploadSlot label="Device B" onUploaded={setIdB} current={idB} />
      </div>
      <Button className="my-6" onClick={computeDiff} disabled={!idA || !idB || busy}>
        {busy ? "Comparing..." : "Compare"}
      </Button>
      {changes && <DiffView changes={changes} />}
    </div>
  )
}

function UploadSlot({
  label, onUploaded, current,
}: { label: string; onUploaded: (id: string) => void; current: string | null }) {
  const handleUpload = async (file: File) => {
    const r = await api.uploadDevice(file)
    onUploaded(r.id)
  }
  return (
    <div>
      <h2 className="mb-2 font-semibold">{label}</h2>
      {current ? (
        <p className="text-sm text-muted-foreground font-mono">id: {current}</p>
      ) : (
        <InlineUploader onUpload={handleUpload} />
      )}
    </div>
  )
}

function InlineUploader({ onUpload }: { onUpload: (f: File) => void }) {
  return (
    <input
      type="file"
      accept=".syx,.q7p,.blk,.mid"
      onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
      className="block w-full text-sm file:mr-4 file:px-3 file:py-2
                 file:rounded-md file:border-0 file:bg-primary file:text-primary-foreground"
    />
  )
}
```

## Componente `src/components/DiffView.tsx`

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { DiffChange } from "@/lib/types"

export function DiffView({ changes }: { changes: DiffChange[] }) {
  if (changes.length === 0) {
    return (
      <div className="border rounded-xl p-8 text-center text-muted-foreground">
        The two devices are identical.
      </div>
    )
  }

  return (
    <div>
      <p className="mb-3 text-sm">{changes.length} differing fields</p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Path</TableHead>
            <TableHead>A</TableHead>
            <TableHead>B</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {changes.map((c) => (
            <TableRow key={c.path}>
              <TableCell className="font-mono text-xs">{c.path}</TableCell>
              <TableCell>
                <Value v={c.a} />
              </TableCell>
              <TableCell>
                <Value v={c.b} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function Value({ v }: { v: unknown }) {
  if (v === undefined) return <span className="text-muted-foreground italic">absent</span>
  return <span className="font-mono text-xs">{JSON.stringify(v)}</span>
}
```

## Registrazione route in `App.tsx`

```tsx
import DiffRoute from "@/routes/DiffRoute"
// ...
<Route path="/diff" element={<DiffRoute />} />
```

Aggiungere nav link nel Dashboard:

```tsx
// Dashboard.tsx
<nav className="mb-4 flex gap-3">
  <Link to="/">Dashboard</Link>
  <Link to="/diff">Diff</Link>
  <Link to="/realtime">Realtime</Link>
</nav>
```

## Test Vitest

`src/test/__tests__/DiffView.test.tsx`:

1. `empty changes shows identical message`
2. `renders table with N rows for N changes`
3. `absent value (undefined) shown as placeholder`

`src/test/__tests__/DiffRoute.test.tsx`:

1. `compare button disabled until both uploads complete`

## Task granulari

1. Creare `src/components/DiffView.tsx`
2. Creare `src/routes/DiffRoute.tsx`
3. Registrare route in `App.tsx` + nav link in `Dashboard.tsx`
4. Test Vitest (2 file)
5. Commit: `feat(web-frontend): W7 — DiffRoute + DiffView side-by-side`

## Verifica

```bash
cd web/frontend
npm test
npm run build

# Smoke manuale:
# upload 2 device con 1 modifica via PATCH → /diff mostra 1 riga nella tabella
```
