import { useParams } from "react-router-dom"
import { useDevice } from "@/lib/queries"
import { UDMTree } from "@/components/UDMTree"
import { FieldEditor } from "@/components/FieldEditor"
import { ExportDialog } from "@/components/ExportDialog"
import { getByPath } from "@/lib/path"
import { useState } from "react"

export default function DeviceView() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, error } = useDevice(id!)
  const [selected, setSelected] = useState<string | null>(null)

  if (isLoading) return <div className="p-8">Loading...</div>
  if (error) return <div className="p-8 text-red-500">{String(error)}</div>
  if (!data) return null

  const device = data.device as Record<string, unknown>

  return (
    <div className="h-screen flex flex-col">
      <header className="border-b px-8 py-3 flex items-center justify-between shrink-0">
        <h1 className="text-lg font-semibold">
          {String(device.model).toUpperCase()}
        </h1>
        <ExportDialog
          deviceId={id!}
          currentModel={String(device.model).toUpperCase()}
        />
      </header>
      <div className="flex-1 grid grid-cols-[320px_1fr] overflow-hidden">
        <aside className="border-r overflow-auto p-4">
          <UDMTree device={device} onSelect={setSelected} />
        </aside>
        <main className="p-8 overflow-auto">
          {selected ? (
            <>
              <h2 className="text-xl font-bold mb-4">{selected}</h2>
              <FieldEditor
                deviceId={id!}
                path={selected}
                currentValue={getByPath(device, selected)}
              />
            </>
          ) : (
            <p className="text-muted-foreground">
              Select a field from the tree
            </p>
          )}
        </main>
      </div>
    </div>
  )
}
