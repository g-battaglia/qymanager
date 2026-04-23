import { useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { useDevice } from "@/lib/queries"
import { UDMTree } from "@/components/UDMTree"
import { ExportDialog } from "@/components/ExportDialog"
import { DeviceOverview } from "@/components/DeviceOverview"
import { SelectionPanel } from "@/components/SelectionPanel"
import { getByPath } from "@/lib/path"
import { Input } from "@/components/ui/input"
import { getNodeSummary } from "@/lib/udm"
import type { UdmDevice } from "@/lib/types"

const OVERVIEW_KEY = "__overview__"

function MetaPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-full border border-border/80 bg-background/80 px-3 py-1.5 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
      {label}: <span className="text-foreground">{value}</span>
    </div>
  )
}

export default function DeviceView() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, error } = useDevice(id!)
  const [selected, setSelected] = useState<string>(OVERVIEW_KEY)
  const [query, setQuery] = useState("")

  const device = useMemo(() => data?.device as UdmDevice | undefined, [data])
  const selectedValue = useMemo(() => {
    if (!device || selected === OVERVIEW_KEY) {
      return undefined
    }
    return getByPath(device, selected)
  }, [device, selected])

  if (isLoading) {
    return <div className="p-8">Loading device...</div>
  }
  if (error) {
    return <div className="p-8 text-red-500">{String(error)}</div>
  }
  if (!device) {
    return null
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(15,23,42,0.06),_transparent_32rem)]">
      <header className="border-b border-border/70 bg-background/85 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4 px-6 py-4 lg:px-8">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
              QYConv Web Editor
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">
              {String(device.model).toUpperCase()} Device Inspector
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <MetaPill label="Source" value={String(device.source_format ?? "unknown").toUpperCase()} />
            <MetaPill label="Patterns" value={String(device.patterns.length)} />
            <MetaPill label="Parts" value={String(device.multi_part.length)} />
            <ExportDialog
              deviceId={id!}
              currentModel={String(device.model).toUpperCase()}
            />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1600px] gap-0 px-4 py-4 lg:grid-cols-[380px_1fr] lg:px-6">
        <aside className="overflow-hidden rounded-[2rem] border border-border/70 bg-card shadow-sm lg:sticky lg:top-4 lg:h-[calc(100vh-7rem)]">
          <div className="border-b border-border/70 px-5 py-5">
            <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
              Navigator
            </p>
            <h2 className="mt-2 text-xl font-semibold">Understand the import</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Start from the overview, then inspect the UDM structure section by section.
            </p>

            <button
              type="button"
              onClick={() => setSelected(OVERVIEW_KEY)}
              className={`mt-4 w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
                selected === OVERVIEW_KEY
                  ? "border-primary/30 bg-primary/10"
                  : "border-border/70 bg-muted/35 hover:bg-muted/55"
              }`}
            >
              <p className="text-sm font-medium">Overview</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Summary, import context, editable scope
              </p>
            </button>

            <div className="mt-4">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search fields, paths, sections..."
              />
            </div>
          </div>

          <div className="h-[calc(100%-13.5rem)] overflow-auto px-3 py-3">
            <UDMTree
              device={device as Record<string, unknown>}
              onSelect={setSelected}
              selectedPath={selected === OVERVIEW_KEY ? null : selected}
              query={query}
            />
          </div>
        </aside>

        <main className="min-w-0 px-0 pt-4 lg:px-6 lg:pt-0">
          <div className="space-y-4">
            {selected === OVERVIEW_KEY ? (
              <DeviceOverview device={device} onSelectNode={setSelected} />
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-[2rem] border border-border/70 bg-card px-5 py-4 shadow-sm">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      Focused Node
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selected}
                    </p>
                  </div>
                  <div className="rounded-full border border-border/80 bg-background px-3 py-1.5 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    {getNodeSummary(selectedValue)}
                  </div>
                </div>

                <SelectionPanel
                  deviceId={id!}
                  path={selected}
                  value={selectedValue}
                />
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
