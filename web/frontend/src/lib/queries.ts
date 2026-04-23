import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "./api"
import type { VoiceResolveRequest } from "./types"

export const keys = {
  device: (id: string) => ["device", id] as const,
  schema: ["schema"] as const,
  phrases: (id: string) => ["phrases", id] as const,
  voice: (req: VoiceResolveRequest) => ["voice", req] as const,
  syxAnalysis: (id: string) => ["syx-analysis", id] as const,
}

export function useDevice(id: string) {
  return useQuery({
    queryKey: keys.device(id),
    queryFn: () => api.getDevice(id),
  })
}

export function useSchema() {
  return useQuery({
    queryKey: keys.schema,
    queryFn: api.getSchema,
    staleTime: Infinity,
  })
}

export function usePhrases(id: string) {
  return useQuery({
    queryKey: keys.phrases(id),
    queryFn: () => api.getPhrases(id),
    enabled: Boolean(id),
  })
}

export function useSyxAnalysis(id: string) {
  return useQuery({
    queryKey: keys.syxAnalysis(id),
    queryFn: () => api.getSyxAnalysis(id),
    enabled: Boolean(id),
    staleTime: Infinity,
  })
}

export function useVoiceName(req: VoiceResolveRequest | null) {
  return useQuery({
    queryKey: keys.voice(req!),
    queryFn: () => api.resolveVoice(req!),
    enabled: req !== null,
    staleTime: Infinity,
  })
}

export function usePatchField(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, value }: { path: string; value: unknown }) =>
      api.patchField(id, path, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.device(id) }),
  })
}
