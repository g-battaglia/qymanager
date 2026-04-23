import type { UdmDevice } from "@/lib/types"
import {
  getEffects,
  getMultiParts,
  panLabel,
  type MultiPartInfo,
} from "@/lib/udm"

function EffectBlock({
  label,
  typeCode,
  returnLevel,
  params,
}: {
  label: string
  typeCode: number
  returnLevel: number
  params: Record<string, number>
}) {
  const hasParams = Object.keys(params).length > 0
  return (
    <div className="rounded-2xl border border-border/70 bg-muted/35 px-4 py-4">
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <div className="mt-2 flex items-baseline gap-3">
        <span className="text-lg font-semibold">
          Type {typeCode}
        </span>
        <span className="text-sm text-muted-foreground">
          Return {returnLevel}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-foreground/5">
        <div
          className="h-full rounded-full bg-foreground/20"
          style={{ width: `${Math.round((returnLevel / 127) * 100)}%` }}
        />
      </div>
      {hasParams && (
        <div className="mt-3 space-y-1">
          {Object.entries(params).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{key.replace(/_/g, " ")}</span>
              <span className="font-medium tabular-nums">{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function EffectsSection({ device }: { device: UdmDevice }) {
  const effects = getEffects(device)
  const blocks = [
    effects.reverb ? { label: "Reverb", ...effects.reverb } : null,
    effects.chorus ? { label: "Chorus", ...effects.chorus } : null,
    effects.variation ? { label: "Variation", ...effects.variation } : null,
  ].filter(Boolean) as Array<{ label: string; typeCode: number; returnLevel: number; params: Record<string, number> }>

  if (blocks.length === 0) return null

  return (
    <div>
      <p className="mb-3 text-xs uppercase tracking-[0.2em] text-muted-foreground">
        Effects
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {blocks.map((b) => (
          <EffectBlock key={b.label} {...b} />
        ))}
      </div>
    </div>
  )
}

function PartStrip({
  part,
  onSelect,
}: {
  part: MultiPartInfo
  onSelect: (path: string) => void
}) {
  const hasVoice = part.voice.bank_msb !== 0 || part.voice.bank_lsb !== 0 || part.voice.program !== 0
  return (
    <button
      type="button"
      onClick={() => onSelect(part.path)}
      className="w-full rounded-2xl border border-border/60 bg-card px-3 py-2.5 text-left transition-colors hover:border-foreground/15 hover:bg-muted/40"
    >
      <div className="flex items-center gap-2">
        <span className="w-4 shrink-0 text-[11px] font-semibold tabular-nums text-muted-foreground">
          {part.partIndex + 1}
        </span>
        <span className="inline-flex h-5 min-w-[1.75rem] items-center justify-center rounded-md bg-foreground/5 px-1.5 text-[10px] font-semibold tabular-nums text-foreground/60">
          {part.rxChannel + 1}
        </span>
        <div className="min-w-0 flex-1">
          {hasVoice ? (
            <p className="truncate text-xs font-medium">
              {part.voice.bank_msb}/{part.voice.bank_lsb}/{part.voice.program}
            </p>
          ) : (
            <p className="truncate text-xs text-muted-foreground">Default</p>
          )}
        </div>
        <span className="text-[10px] font-semibold tabular-nums text-muted-foreground">
          {part.volume}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-2 pl-6 text-[9px] tabular-nums text-muted-foreground/60">
        <span>Pan {panLabel(part.pan)}</span>
        {part.reverbSend > 0 && <span>Rev {part.reverbSend}</span>}
        {part.chorusSend > 0 && <span>Cho {part.chorusSend}</span>}
        {part.cutoff !== 0 && <span>Cut {part.cutoff}</span>}
        <span>{part.monoPoly}</span>
      </div>
    </button>
  )
}

function MultiPartsSection({
  device,
  onSelectNode,
}: {
  device: UdmDevice
  onSelectNode: (path: string) => void
}) {
  const parts = getMultiParts(device)
  if (parts.length === 0) return null

  return (
    <div>
      <p className="mb-3 text-xs uppercase tracking-[0.2em] text-muted-foreground">
        Multi Part ({parts.length} parts)
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {parts.map((part) => (
          <PartStrip key={part.partIndex} part={part} onSelect={onSelectNode} />
        ))}
      </div>
    </div>
  )
}

export function SoundOverview({
  device,
  onSelectNode,
}: {
  device: UdmDevice
  onSelectNode: (path: string) => void
}) {
  const effects = getEffects(device)
  const multiParts = getMultiParts(device)
  const hasEffects = effects.reverb || effects.chorus || effects.variation
  const hasParts = multiParts.length > 0

  if (!hasEffects && !hasParts) return null

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Sound Configuration
        </p>
        <h3 className="mt-2 text-xl font-semibold">Effects & Multi Parts</h3>
      </div>

      {hasEffects && <EffectsSection device={device} />}
      {hasParts && <MultiPartsSection device={device} onSelectNode={onSelectNode} />}
    </div>
  )
}
