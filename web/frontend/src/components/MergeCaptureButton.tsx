import { useRef, useState } from "react"
import { useMergeCapture } from "@/lib/queries"

export function MergeCaptureButton({ deviceId }: { deviceId: string }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [err, setErr] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)
  const merge = useMergeCapture(deviceId)

  async function handleFile(file: File) {
    setErr(null)
    setOk(null)
    try {
      const result = await merge.mutateAsync(file)
      const filled = result.device.multi_part.filter((p) => {
        const v = p.voice as Record<string, number>
        return v && (v.bank_msb || v.bank_lsb || v.program)
      }).length
      setOk(`Merged: ${filled} voices resolved`)
    } catch (e) {
      setErr(String(e))
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <input
        ref={fileRef}
        type="file"
        accept=".json,.syx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) handleFile(f)
          e.target.value = ""
        }}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={merge.isPending}
        className="rounded-full border border-border/70 bg-background/80 px-3 py-1.5 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground hover:border-foreground/40 hover:text-foreground disabled:opacity-60"
      >
        {merge.isPending ? "Merging…" : "Merge XG capture"}
      </button>
      {ok && <span className="text-[10px] text-emerald-600">{ok}</span>}
      {err && <span className="max-w-[16rem] truncate text-[10px] text-red-600">{err}</span>}
    </div>
  )
}
