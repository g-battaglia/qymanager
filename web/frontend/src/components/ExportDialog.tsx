import { useState } from "react"
import { api } from "@/lib/api"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { WarningList } from "./WarningList"
import { toast } from "sonner"

const FORMATS = [
  { value: "syx", label: "Yamaha SysEx (.syx)" },
  { value: "q7p", label: "QY700 Pattern (.q7p)" },
  { value: "mid", label: "Standard MIDI (.mid)" },
]

const LOSSY_GROUPS = [
  "fill-cc-dd",
  "variation",
  "parts-17-32",
  "drum-kit-2",
  "song-tracks-5-35",
]

export function ExportDialog({
  deviceId,
  currentModel,
}: { deviceId: string; currentModel: string }) {
  const [format, setFormat] = useState("syx")
  const [target, setTarget] = useState<string>("same")
  const [drop, setDrop] = useState<string[]>([])
  const [warnings, setWarnings] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleExport = async () => {
    setBusy(true)
    setErr(null)
    try {
      const opts: {
        format: string
        target_model?: string
        drop?: string[]
      } = { format }
      if (target !== "same") opts.target_model = target
      if (drop.length) opts.drop = drop

      const result = await api.exportDevice(deviceId, opts)
      setWarnings(result.warnings)

      const url = URL.createObjectURL(result.blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `export.${format}`
      a.click()
      URL.revokeObjectURL(url)

      if (result.warnings.length > 0) {
        toast.warning("Export completed with warnings")
      }
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog>
      <DialogTrigger
        render={<Button variant="outline">Export...</Button>}
      />
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Export device</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Format</Label>
            <Select
              value={format}
              onValueChange={(v: string | null) => {
                if (v !== null) setFormat(v)
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FORMATS.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Target device</Label>
            <Select
              value={target}
              onValueChange={(v: string | null) => {
                if (v !== null) setTarget(v)
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="same">
                  Same as source ({currentModel})
                </SelectItem>
                <SelectItem value="QY70">QY70</SelectItem>
                <SelectItem value="QY700">QY700</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {target !== "same" && (
            <div>
              <Label>Drop groups (lossy)</Label>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {LOSSY_GROUPS.map((g) => (
                  <label key={g} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={drop.includes(g)}
                      onCheckedChange={(v) =>
                        setDrop(
                          v ? [...drop, g] : drop.filter((x) => x !== g),
                        )
                      }
                    />
                    <span>{g}</span>
                  </label>
                ))}
              </div>
            </div>
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
