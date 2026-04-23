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
    [nav],
  )

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
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
      <Button
        onClick={() => document.getElementById("file-input")?.click()}
      >
        Browse file
      </Button>
      {err && <p className="text-red-500 mt-2">{err}</p>}
    </div>
  )
}
