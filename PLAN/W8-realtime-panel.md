# W8 — RealtimePanel (emit + watch WebSocket)

> **Obiettivo**: pagina `/realtime` con 2 tab: Send (emit XG edit verso hardware) e Watch
> (stream WebSocket Parameter Change in arrivo).

## Route `src/routes/RealtimeRoute.tsx`

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SendPanel } from "@/components/realtime/SendPanel"
import { WatchPanel } from "@/components/realtime/WatchPanel"

export default function RealtimeRoute() {
  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Realtime MIDI</h1>
      <Tabs defaultValue="send">
        <TabsList>
          <TabsTrigger value="send">Send</TabsTrigger>
          <TabsTrigger value="watch">Watch</TabsTrigger>
        </TabsList>
        <TabsContent value="send"><SendPanel /></TabsContent>
        <TabsContent value="watch"><WatchPanel /></TabsContent>
      </Tabs>
    </div>
  )
}
```

## Componente `src/components/realtime/SendPanel.tsx`

```tsx
import { useState } from "react"
import { useMidiPorts } from "@/lib/queries"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

type Edit = { path: string; value: string }

export function SendPanel() {
  const { data: ports, isLoading } = useMidiPorts()
  const [port, setPort] = useState<string>("")
  const [edits, setEdits] = useState<Edit[]>([{ path: "system.master_volume", value: "100" }])
  const [result, setResult] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const addEdit = () => setEdits([...edits, { path: "", value: "" }])
  const updateEdit = (i: number, patch: Partial<Edit>) =>
    setEdits(edits.map((e, j) => (j === i ? { ...e, ...patch } : e)))
  const removeEdit = (i: number) => setEdits(edits.filter((_, j) => j !== i))

  const handleEmit = async () => {
    setErr(null)
    setResult(null)
    const payload: Record<string, unknown> = {}
    for (const e of edits) {
      if (!e.path) continue
      payload[e.path] = /^-?\d+$/.test(e.value) ? Number(e.value) : e.value
    }
    try {
      const r = await api.midiEmit(port, payload)
      setResult(r.sysex_hex)
    } catch (e) {
      setErr(String(e))
    }
  }

  if (isLoading) return <p>Loading MIDI ports...</p>

  return (
    <div className="space-y-4 mt-4">
      <div>
        <label className="block text-sm mb-1">Output port</label>
        <Select value={port} onValueChange={setPort}>
          <SelectTrigger><SelectValue placeholder="Select port..." /></SelectTrigger>
          <SelectContent>
            {(ports?.outputs ?? []).map((p) => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <label className="block text-sm mb-1">Edits</label>
        {edits.map((e, i) => (
          <div key={i} className="flex gap-2 mb-2">
            <Input placeholder="path" value={e.path}
                   onChange={(ev) => updateEdit(i, { path: ev.target.value })} />
            <Input placeholder="value" value={e.value}
                   onChange={(ev) => updateEdit(i, { value: ev.target.value })} />
            <Button variant="ghost" onClick={() => removeEdit(i)}>×</Button>
          </div>
        ))}
        <Button variant="outline" onClick={addEdit}>+ Add edit</Button>
      </div>

      <Button onClick={handleEmit} disabled={!port}>Emit</Button>

      {result && (
        <div>
          <p className="text-sm">SysEx sent:</p>
          <pre className="text-xs bg-muted p-2 rounded">{result}</pre>
        </div>
      )}
      {err && <p className="text-red-500">{err}</p>}
    </div>
  )
}
```

## Componente `src/components/realtime/WatchPanel.tsx`

```tsx
import { useEffect, useRef, useState } from "react"
import { useMidiPorts } from "@/lib/queries"
import { Button } from "@/components/ui/button"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type XgEvent = { ah: number; am: number; al: number; value: number; ts?: number }

export function WatchPanel() {
  const { data: ports } = useMidiPorts()
  const [port, setPort] = useState("")
  const [events, setEvents] = useState<XgEvent[]>([])
  const [status, setStatus] = useState<"idle" | "connected" | "error">("idle")
  const wsRef = useRef<WebSocket | null>(null)

  const start = () => {
    if (!port) return
    const url = new URL("/api/midi/watch", window.location.href)
    url.protocol = url.protocol.replace("http", "ws")
    url.searchParams.set("port", port)
    const ws = new WebSocket(url.toString())
    ws.onopen = () => setStatus("connected")
    ws.onmessage = (e) => {
      const ev = JSON.parse(e.data) as XgEvent
      setEvents((prev) => [{ ...ev, ts: Date.now() }, ...prev.slice(0, 199)])
    }
    ws.onerror = () => setStatus("error")
    ws.onclose = () => setStatus("idle")
    wsRef.current = ws
  }

  const stop = () => {
    wsRef.current?.close()
    wsRef.current = null
    setStatus("idle")
  }

  useEffect(() => () => stop(), [])

  return (
    <div className="space-y-4 mt-4">
      <div className="flex gap-3 items-end">
        <div className="flex-1">
          <label className="block text-sm mb-1">Input port</label>
          <Select value={port} onValueChange={setPort}>
            <SelectTrigger><SelectValue placeholder="Select port..." /></SelectTrigger>
            <SelectContent>
              {(ports?.inputs ?? []).map((p) => (
                <SelectItem key={p} value={p}>{p}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {status === "connected" ? (
          <Button variant="destructive" onClick={stop}>Stop</Button>
        ) : (
          <Button onClick={start} disabled={!port}>Start</Button>
        )}
        <span className="text-sm text-muted-foreground">{status}</span>
      </div>

      <ScrollArea className="h-96 border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>AH</TableHead>
              <TableHead>AM</TableHead>
              <TableHead>AL</TableHead>
              <TableHead>Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((e, i) => (
              <TableRow key={i}>
                <TableCell className="font-mono text-xs">0x{e.ah.toString(16).padStart(2, "0")}</TableCell>
                <TableCell className="font-mono text-xs">0x{e.am.toString(16).padStart(2, "0")}</TableCell>
                <TableCell className="font-mono text-xs">0x{e.al.toString(16).padStart(2, "0")}</TableCell>
                <TableCell className="font-mono text-xs">{e.value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ScrollArea>
    </div>
  )
}
```

## Registrazione route + navigazione

```tsx
// App.tsx
import RealtimeRoute from "@/routes/RealtimeRoute"
<Route path="/realtime" element={<RealtimeRoute />} />
```

## Test Vitest

`src/test/__tests__/SendPanel.test.tsx`:

1. `lists available output ports`
2. `emit button calls midi/emit with payload`

`src/test/__tests__/WatchPanel.test.tsx`:

1. `mock WebSocket, receives event, appends to table`
2. `stop button closes WebSocket`

Per WS mock usare libreria `mock-socket` o stub `window.WebSocket`:

```ts
class MockWebSocket {
  onopen: any; onmessage: any; onerror: any; onclose: any
  readyState = 1
  constructor(public url: string) { setTimeout(() => this.onopen?.(), 0) }
  send() {}
  close() { this.onclose?.() }
  emit(data: any) { this.onmessage?.({ data: JSON.stringify(data) }) }
}
(global as any).WebSocket = MockWebSocket
```

## Task granulari

1. `shadcn add scroll-area tabs` se mancano
2. Creare directory `src/components/realtime/`
3. Creare `SendPanel.tsx`
4. Creare `WatchPanel.tsx`
5. Creare `src/routes/RealtimeRoute.tsx`
6. Registrare route + nav link
7. Test Vitest (2 file, 4 test)
8. Commit: `feat(web-frontend): W8 — RealtimePanel send + watch WebSocket`

## Verifica

```bash
cd web/frontend
npm test
npm run build

# Smoke (richiede hardware):
# 1. Collegare UR22C + QY70
# 2. uv run qymanager serve (dopo W9) oppure backend :8000 + npm run dev
# 3. /realtime → Send tab → port UR22C Port 1 → emit master_volume=100 → verifica hardware
# 4. Watch tab → Start → muovi fader QY70 → eventi appaiono
```
