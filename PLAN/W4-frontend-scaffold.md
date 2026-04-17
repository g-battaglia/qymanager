# W4 — Frontend scaffold + Uploader + UDMTree

> **Obiettivo**: scaffold React + Vite + TS + Tailwind + shadcn + TanStack Query + router.
> Upload funzionante (drag-and-drop) + tree navigabile dell'UDM nel DeviceView.

## Setup iniziale

```bash
cd /Volumes/Data/DK/XG/T700/qyconv
mkdir -p web/frontend
cd web/frontend

# Scaffold Vite
npm create vite@latest . -- --template react-ts
# Quando chiede overwrite: yes

npm install

# Router + Query
npm install react-router-dom @tanstack/react-query

# Tailwind
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# shadcn/ui init
npx shadcn@latest init -d
# Target: Default style, Slate base color, CSS variables

# Componenti iniziali shadcn
npx shadcn@latest add button input label slider select checkbox dialog tabs table toast scroll-area tooltip
```

## Configurazione

### `vite.config.ts`

```ts
import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/api/midi/watch": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
})
```

### `tailwind.config.ts`

(Fornito da `shadcn init`, verifica che `content` includa `"./src/**/*.{ts,tsx}"`.)

### `tsconfig.json`

Aggiungi `"paths": {"@/*": ["./src/*"]}` in `compilerOptions`, `"strict": true`.

### `package.json` scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint src --ext ts,tsx",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

### Vitest setup

```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react
```

`vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import path from "node:path"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
})
```

`src/test/setup.ts`:

```ts
import "@testing-library/jest-dom"
```

## Struttura `src/`

```
src/
├── main.tsx
├── App.tsx
├── index.css              # tailwind + shadcn CSS vars
├── lib/
│   ├── api.ts             # fetch wrapper
│   ├── queries.ts         # TanStack Query hooks
│   ├── types.ts           # TS mirror di pydantic schemas
│   └── utils.ts           # cn() da shadcn
├── components/
│   ├── ui/                # shadcn primitives (generati da npx)
│   ├── Uploader.tsx
│   └── UDMTree.tsx
├── routes/
│   ├── Dashboard.tsx
│   └── DeviceView.tsx
└── test/
    ├── setup.ts
    └── __tests__/
        ├── Uploader.test.tsx
        └── UDMTree.test.tsx
```

### `src/lib/types.ts`

```ts
export type UdmDevice = {
  model: "QY70" | "QY700"
  system: Record<string, unknown>
  multi_part: Record<string, unknown>[]
  drum_setup: Record<string, unknown>[]
  effects: Record<string, unknown>
  songs: Record<string, unknown>[]
  patterns: Record<string, unknown>[]
  phrases: Record<string, unknown>[]
  groove_templates: Record<string, unknown>[]
  fingered_zone: Record<string, unknown>
  utility_flags: Record<string, unknown>
}

export type UploadResponse = {
  id: string
  device: UdmDevice
  warnings: string[]
}

export type FieldPatch = { path: string; value: unknown }

export type SchemaEntry = {
  path: string
  kind: "range" | "enum"
  lo?: number
  hi?: number
  options?: string[]
}

export type DiffChange = { path: string; a: unknown; b: unknown }
```

### `src/lib/api.ts`

```ts
const BASE = "/api"

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  uploadDevice: async (file: File) => {
    const fd = new FormData()
    fd.append("file", file)
    return handle<{ id: string; device: unknown; warnings: string[] }>(
      await fetch(`${BASE}/devices`, { method: "POST", body: fd })
    )
  },
  getDevice: async (id: string) =>
    handle<{ device: unknown; warnings: string[] }>(
      await fetch(`${BASE}/devices/${id}`)
    ),
  patchField: async (id: string, path: string, value: unknown) =>
    handle<{ device: unknown; errors: string[] }>(
      await fetch(`${BASE}/devices/${id}/field`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ path, value }),
      })
    ),
  deleteDevice: async (id: string) =>
    handle<{ ok: boolean }>(
      await fetch(`${BASE}/devices/${id}`, { method: "DELETE" })
    ),
  getSchema: async () =>
    handle<{ paths: unknown[] }>(await fetch(`${BASE}/schema`)),
  diff: async (id_a: string, id_b: string) =>
    handle<{ changes: unknown[] }>(
      await fetch(`${BASE}/diff`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id_a, id_b }),
      })
    ),
  midiPorts: async () =>
    handle<{ outputs: string[]; inputs: string[] }>(
      await fetch(`${BASE}/midi/ports`)
    ),
  midiEmit: async (port: string, edits: Record<string, unknown>) =>
    handle<{ sysex_hex: string }>(
      await fetch(`${BASE}/midi/emit`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ port, edits }),
      })
    ),
  exportDevice: async (
    id: string,
    opts: { format: string; target_model?: string; keep?: string[]; drop?: string[] }
  ): Promise<Blob> => {
    const res = await fetch(`${BASE}/devices/${id}/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(opts),
    })
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
    return res.blob()
  },
}
```

### `src/lib/queries.ts`

```ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "./api"

export const keys = {
  device: (id: string) => ["device", id] as const,
  schema: ["schema"] as const,
  midiPorts: ["midi", "ports"] as const,
}

export function useDevice(id: string) {
  return useQuery({ queryKey: keys.device(id), queryFn: () => api.getDevice(id) })
}

export function useSchema() {
  return useQuery({ queryKey: keys.schema, queryFn: api.getSchema, staleTime: Infinity })
}

export function useMidiPorts() {
  return useQuery({ queryKey: keys.midiPorts, queryFn: api.midiPorts, refetchInterval: 5000 })
}

export function usePatchField(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, value }: { path: string; value: unknown }) =>
      api.patchField(id, path, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.device(id) }),
  })
}
```

### `src/App.tsx`

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import Dashboard from "@/routes/Dashboard"
import DeviceView from "@/routes/DeviceView"

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/device/:id" element={<DeviceView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

### `src/components/Uploader.tsx`

```tsx
import { useCallback, useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function Uploader() {
  const nav = useNavigate()
  const [isDrag, setDrag] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const upload = useCallback(
    async (file: File) => {
      setErr(null)
      try {
        const r = await api.uploadDevice(file)
        nav(`/device/${r.id}`)
      } catch (e) {
        setErr(String(e))
      }
    },
    [nav]
  )

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        const f = e.dataTransfer.files[0]
        if (f) upload(f)
      }}
      className={`border-2 border-dashed rounded-xl p-12 text-center ${
        isDrag ? "border-primary bg-primary/5" : "border-muted"
      }`}
    >
      <p className="mb-4">Drop .syx / .q7p / .blk / .mid here</p>
      <input
        id="file-input"
        type="file"
        accept=".syx,.q7p,.blk,.mid"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <Button asChild>
        <label htmlFor="file-input" className="cursor-pointer">Browse file</label>
      </Button>
      {err && <p className="text-red-500 mt-2">{err}</p>}
    </div>
  )
}
```

### `src/components/UDMTree.tsx`

Rendering ricorsivo. Nodo espandibile; click su leaf seleziona path e chiama callback.

```tsx
import { useState } from "react"

type NodeProps = { label: string; value: unknown; path: string; onSelect: (p: string) => void }

function Node({ label, value, path, onSelect }: NodeProps) {
  const [open, setOpen] = useState(false)

  if (value !== null && typeof value === "object") {
    const entries = Array.isArray(value)
      ? value.map((v, i) => [`[${i}]`, v] as const)
      : Object.entries(value)
    return (
      <div>
        <button onClick={() => setOpen(!open)} className="text-left w-full py-0.5 hover:bg-muted">
          {open ? "▼" : "▶"} {label}
        </button>
        {open && (
          <div className="pl-4 border-l">
            {entries.map(([k, v]) => (
              <Node key={k} label={k} value={v} path={`${path}.${k}`} onSelect={onSelect} />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <button
      onClick={() => onSelect(path)}
      className="text-left w-full py-0.5 pl-4 text-sm hover:bg-muted"
    >
      <span className="text-muted-foreground">{label}</span>: {String(value)}
    </button>
  )
}

export function UDMTree({
  device,
  onSelect,
}: {
  device: Record<string, unknown>
  onSelect: (path: string) => void
}) {
  return (
    <div className="text-sm font-mono">
      {Object.entries(device).map(([k, v]) => (
        <Node key={k} label={k} value={v} path={k} onSelect={onSelect} />
      ))}
    </div>
  )
}
```

### `src/routes/Dashboard.tsx`

```tsx
import { Uploader } from "@/components/Uploader"

export default function Dashboard() {
  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-6">QYConv</h1>
      <p className="mb-4 text-muted-foreground">
        Yamaha QY70 / QY700 editor. Upload un file per iniziare.
      </p>
      <Uploader />
    </div>
  )
}
```

### `src/routes/DeviceView.tsx`

```tsx
import { useParams } from "react-router-dom"
import { useDevice } from "@/lib/queries"
import { UDMTree } from "@/components/UDMTree"
import { useState } from "react"

export default function DeviceView() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, error } = useDevice(id!)
  const [selected, setSelected] = useState<string | null>(null)

  if (isLoading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{String(error)}</div>
  if (!data) return null

  return (
    <div className="grid grid-cols-[320px_1fr] h-screen">
      <aside className="border-r overflow-auto p-4">
        <UDMTree device={data.device as Record<string, unknown>} onSelect={setSelected} />
      </aside>
      <main className="p-8">
        <h2 className="text-xl font-bold mb-4">
          {selected ?? "Seleziona un campo"}
        </h2>
        {/* FieldEditor arriva in W5 */}
      </main>
    </div>
  )
}
```

## Test Vitest

`src/test/__tests__/Uploader.test.tsx` — drag-drop mock + fetch mock → verifica navigate
chiamato.

`src/test/__tests__/UDMTree.test.tsx` — device mock con 2 livelli → expand + click leaf →
verifica `onSelect` con path corretto.

`src/test/__tests__/api.test.ts` — mock fetch, verifica wrapper `api.uploadDevice` costruisce
FormData corretto.

## Task granulari

1. `npm create vite@latest . -- --template react-ts` in `web/frontend/`
2. Install router, query, tailwind, shadcn, vitest, testing-library
3. Config `vite.config.ts`, `tailwind.config.ts`, `tsconfig.json`, `vitest.config.ts`
4. `shadcn init` + aggiungi componenti base (button, input, etc.)
5. Creare `src/lib/{api,queries,types,utils}.ts`
6. Creare `src/App.tsx` + router + QueryClient
7. Creare `src/components/Uploader.tsx`
8. Creare `src/components/UDMTree.tsx`
9. Creare `src/routes/{Dashboard,DeviceView}.tsx`
10. 3 test Vitest
11. `npm run build` verifica successful
12. Commit: `feat(web-frontend): W4 — scaffold React+Vite+TS+shadcn + Uploader + UDMTree`

## Verifica

```bash
cd web/frontend
npm run typecheck
npm run lint
npm test
npm run build

# Smoke manuale (serve backend W1+ già running su :8000):
npm run dev
# apri http://localhost:5173
# upload SGT.syx → verifica redirect a /device/<id> + tree visibile
```
