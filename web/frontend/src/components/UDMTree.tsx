import { useState } from "react"

type NodeProps = {
  label: string
  value: unknown
  path: string
  onSelect: (p: string) => void
}

function Node({ label, value, path, onSelect }: NodeProps) {
  const [open, setOpen] = useState(false)

  if (value !== null && typeof value === "object") {
    const entries = Array.isArray(value)
      ? value.map((v, i) => [`[${i}]`, v] as const)
      : Object.entries(value as Record<string, unknown>)
    return (
      <div>
        <button
          onClick={() => setOpen(!open)}
          className="text-left w-full py-0.5 hover:bg-muted px-1"
        >
          {open ? "\u25BC" : "\u25B6"} {label}
        </button>
        {open && (
          <div className="pl-4 border-l">
            {entries.map(([k, v]) => (
              <Node
                key={k}
                label={k}
                value={v}
                path={`${path}.${k}`}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <button
      onClick={() => onSelect(path)}
      className="text-left w-full py-0.5 pl-4 text-sm hover:bg-muted px-1"
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
