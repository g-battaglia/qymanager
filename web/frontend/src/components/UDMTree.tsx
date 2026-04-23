import { useEffect, useMemo, useState } from "react"
import {
  getNodeSummary,
  getRootEntries,
  humanizeKey,
  joinPath,
} from "@/lib/udm"

type NodeProps = {
  label: string
  value: unknown
  path: string
  onSelect: (path: string) => void
  selectedPath: string | null
  query: string
  depth?: number
}

function matchesQuery(label: string, path: string, query: string): boolean {
  if (!query.trim()) {
    return true
  }
  const needle = query.trim().toLowerCase()
  return label.toLowerCase().includes(needle) || path.toLowerCase().includes(needle)
}

function hasMatchingDescendant(value: unknown, path: string, query: string): boolean {
  if (!query.trim() || value === null || typeof value !== "object") {
    return false
  }

  const entries = Array.isArray(value)
    ? value.map((item, index) => [`[${index}]`, item] as const)
    : Object.entries(value as Record<string, unknown>)

  return entries.some(([key, child]) => {
    const childPath = joinPath(path, key)
    const childLabel = humanizeKey(key)
    return matchesQuery(childLabel, childPath, query) || hasMatchingDescendant(child, childPath, query)
  })
}

function Node({
  label,
  value,
  path,
  onSelect,
  selectedPath,
  query,
  depth = 0,
}: NodeProps) {
  const isObject = value !== null && typeof value === "object"
  const entries = isObject
    ? Array.isArray(value)
      ? value.map((item, index) => [`[${index}]`, item] as const)
      : Object.entries(value as Record<string, unknown>)
    : []

  const visible =
    matchesQuery(label, path, query) || hasMatchingDescendant(value, path, query)
  const defaultOpen = depth === 0 || Boolean(query.trim())
  const [open, setOpen] = useState(defaultOpen)

  useEffect(() => {
    if (query.trim()) {
      setOpen(true)
    }
  }, [query])

  const isSelected = selectedPath === path
  const rowClass = isSelected
    ? "border-primary/30 bg-primary/10 text-foreground"
    : "border-transparent text-foreground/85 hover:border-border/80 hover:bg-muted/55"

  if (!visible) {
    return null
  }

  return (
    <div className="space-y-1">
      <div className={`flex items-center gap-1 rounded-2xl border px-2 py-1.5 transition-colors ${rowClass}`}>
        {isObject ? (
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            className="flex size-7 shrink-0 items-center justify-center rounded-xl text-muted-foreground hover:bg-background/80"
            aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
          >
            {open ? "−" : "+"}
          </button>
        ) : (
          <div className="size-7 shrink-0" />
        )}

        <button
          type="button"
          onClick={() => onSelect(path)}
          className="min-w-0 flex-1 text-left"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{label}</p>
              <p className="truncate text-xs text-muted-foreground">{path}</p>
            </div>
            <span className="shrink-0 rounded-full bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground">
              {getNodeSummary(value)}
            </span>
          </div>
        </button>
      </div>

      {isObject && open ? (
        <div className="ml-4 border-l border-border/60 pl-3">
          {entries.map(([key, child]) => (
            <Node
              key={joinPath(path, key)}
              label={humanizeKey(key)}
              value={child}
              path={joinPath(path, key)}
              onSelect={onSelect}
              selectedPath={selectedPath}
              query={query}
              depth={depth + 1}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function UDMTree({
  device,
  onSelect,
  selectedPath,
  query = "",
}: {
  device: Record<string, unknown>
  onSelect: (path: string) => void
  selectedPath: string | null
  query?: string
}) {
  const entries = useMemo(() => getRootEntries(device), [device])

  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <Node
          key={key}
          label={humanizeKey(key)}
          value={value}
          path={key}
          onSelect={onSelect}
          selectedPath={selectedPath}
          query={query}
        />
      ))}
      {!entries.some(([key, value]) => hasMatchingDescendant(value, key, query) || matchesQuery(humanizeKey(key), key, query)) ? (
        <div className="rounded-2xl border border-dashed border-border/80 px-4 py-5 text-sm text-muted-foreground">
          No fields match this search.
        </div>
      ) : null}
    </div>
  )
}

export { matchesQuery }
