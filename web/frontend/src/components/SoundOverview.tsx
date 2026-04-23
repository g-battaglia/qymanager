import type { UdmDevice } from "@/lib/types"
import {
  getEffects,
  getMultiParts,
  panLabel,
  type MultiPartInfo,
} from "@/lib/udm"
import { VoiceLabel } from "@/components/VoiceLabel"

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
    <div className="space-y-1.5">
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <div className="flex items-baseline gap-2">
        <span className="text-base font-semibold">Type {typeCode}</span>
        <span className="text-xs text-muted-foreground">
          Return {returnLevel}
        </span>
      </div>
      <div className="h-1 w-full rounded-full bg-foreground/5">
        <div
          className="h-full rounded-full bg-foreground/25"
          style={{ width: `${Math.round((returnLevel / 127) * 100)}%` }}
        />
      </div>
      {hasParams && (
        <div className="space-y-0.5 pt-1">
          {Object.entries(params).map(([key, value]) => (
            <div
              key={key}
              className="flex items-center justify-between text-[10px]"
            >
              <span className="text-muted-foreground">
                {key.replace(/_/g, " ")}
              </span>
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
  ].filter(Boolean) as Array<{
    label: string
    typeCode: number
    returnLevel: number
    params: Record<string, number>
  }>

  if (blocks.length === 0) return null

  return (
    <div>
      <p className="mb-3 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Effects
      </p>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        {blocks.map((b) => (
          <EffectBlock key={b.label} {...b} />
        ))}
      </div>
    </div>
  )
}

function PartRow({
  part,
  onSelect,
}: {
  part: MultiPartInfo
  onSelect: (path: string) => void
}) {
  const hasVoice =
    part.voice.bank_msb !== 0 ||
    part.voice.bank_lsb !== 0 ||
    part.voice.program !== 0
  return (
    <button
      type="button"
      onClick={() => onSelect(part.path)}
      className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/60"
    >
      <span className="mt-0.5 w-4 shrink-0 text-[11px] font-semibold tabular-nums text-muted-foreground">
        {part.partIndex + 1}
      </span>
      <span className="mt-0.5 inline-flex h-5 min-w-[1.75rem] shrink-0 items-center justify-center rounded bg-foreground/5 px-1.5 text-[10px] font-semibold tabular-nums text-foreground/60">
        {part.rxChannel + 1}
      </span>
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <VoiceLabel
              bankMsb={part.voice.bank_msb}
              bankLsb={part.voice.bank_lsb}
              program={part.voice.program}
              channel={part.rxChannel + 1}
              showRaw={hasVoice}
            />
          </div>
          <span className="shrink-0 text-[10px] font-semibold tabular-nums text-muted-foreground">
            {part.volume}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9px] tabular-nums text-muted-foreground/70">
          <span>Pan {panLabel(part.pan)}</span>
          {part.reverbSend > 0 && <span>Rev {part.reverbSend}</span>}
          {part.chorusSend > 0 && <span>Cho {part.chorusSend}</span>}
          {part.cutoff !== 0 && <span>Cut {part.cutoff}</span>}
          <span>{part.monoPoly}</span>
        </div>
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
      <p className="mb-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Multi Part · {parts.length} parts
      </p>
      <div className="grid gap-0.5 sm:grid-cols-2 xl:grid-cols-3">
        {parts.map((part) => (
          <PartRow key={part.partIndex} part={part} onSelect={onSelectNode} />
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
    <div className="space-y-5">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Sound Configuration
        </p>
        <h3 className="mt-2 text-xl font-semibold">Effects &amp; Multi Parts</h3>
      </div>

      {hasEffects && <EffectsSection device={device} />}
      {hasParts && <MultiPartsSection device={device} onSelectNode={onSelectNode} />}
    </div>
  )
}
