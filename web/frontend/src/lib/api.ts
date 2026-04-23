import type {
  UploadResponse,
  DeviceResponse,
  FieldPatchResponse,
  SchemaResponse,
  DiffChange,
  ExportResult,
  VoiceResolveRequest,
  VoiceResolveResponse,
  PhrasesResponse,
  SyxAnalysisResponse,
} from "./types"

const BASE = "/api"

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  uploadDevice: async (file: File): Promise<UploadResponse> => {
    const fd = new FormData()
    fd.append("file", file)
    return handle<UploadResponse>(
      await fetch(`${BASE}/devices`, { method: "POST", body: fd }),
    )
  },

  getDevice: async (id: string): Promise<DeviceResponse> =>
    handle<DeviceResponse>(await fetch(`${BASE}/devices/${id}`)),

  patchField: async (
    id: string,
    path: string,
    value: unknown,
  ): Promise<FieldPatchResponse> =>
    handle<FieldPatchResponse>(
      await fetch(`${BASE}/devices/${id}/field`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ path, value }),
      }),
    ),

  deleteDevice: async (id: string): Promise<{ ok: boolean }> =>
    handle<{ ok: boolean }>(
      await fetch(`${BASE}/devices/${id}`, { method: "DELETE" }),
    ),

  validateDevice: async (
    id: string,
  ): Promise<{ errors: string[] }> =>
    handle<{ errors: string[] }>(
      await fetch(`${BASE}/devices/${id}/validate`, { method: "POST" }),
    ),

  getSchema: async (): Promise<SchemaResponse> =>
    handle<SchemaResponse>(await fetch(`${BASE}/schema`)),

  diff: async (
    id_a: string,
    id_b: string,
  ): Promise<{ changes: DiffChange[] }> =>
    handle<{ changes: DiffChange[] }>(
      await fetch(`${BASE}/diff`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id_a, id_b }),
      }),
    ),

  exportDevice: async (
    id: string,
    opts: {
      format: string
      target_model?: string
      keep?: string[]
      drop?: string[]
    },
  ): Promise<ExportResult> => {
    const res = await fetch(`${BASE}/devices/${id}/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(opts),
    })
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
    const warnings = (res.headers.get("X-Warnings") ?? "")
      .split("|")
      .filter(Boolean)
    const blob = await res.blob()
    return { blob, warnings }
  },

  resolveVoice: async (req: VoiceResolveRequest): Promise<VoiceResolveResponse> =>
    handle<VoiceResolveResponse>(
      await fetch(`${BASE}/resolve-voice`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(req),
      }),
    ),

  getPhrases: async (id: string): Promise<PhrasesResponse> =>
    handle<PhrasesResponse>(await fetch(`${BASE}/devices/${id}/phrases`)),

  getSyxAnalysis: async (id: string): Promise<SyxAnalysisResponse> =>
    handle<SyxAnalysisResponse>(
      await fetch(`${BASE}/devices/${id}/syx-analysis`),
    ),
}
