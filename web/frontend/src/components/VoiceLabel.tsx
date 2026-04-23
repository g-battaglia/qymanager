import { useVoiceName } from "@/lib/queries"
import type { VoiceResolveRequest } from "@/lib/types"

export function VoiceLabel({
  bankMsb,
  bankLsb,
  program,
  channel,
  showRaw = false,
  showDrumBadge = true,
}: {
  bankMsb: number
  bankLsb: number
  program: number
  channel: number
  showRaw?: boolean
  showDrumBadge?: boolean
}) {
  const req: VoiceResolveRequest = {
    bank_msb: bankMsb,
    bank_lsb: bankLsb,
    program: program,
    channel: channel,
  }
  const { data } = useVoiceName(req)

  if (!data) {
    return (
      <span className="block truncate text-xs tabular-nums text-muted-foreground">
        {bankMsb}/{bankLsb}/{program}
      </span>
    )
  }

  const isDefault = bankMsb === 0 && bankLsb === 0 && program === 0

  return (
    <span className="flex min-w-0 items-center gap-1.5">
      <span
        className={`min-w-0 flex-1 truncate text-xs font-medium ${
          isDefault ? "text-muted-foreground" : "text-foreground"
        }`}
      >
        {data.name}
      </span>
      {data.is_drum && showDrumBadge && (
        <span className="shrink-0 rounded bg-amber-100 px-1 py-px text-[9px] font-semibold uppercase tracking-wider text-amber-800">
          DR
        </span>
      )}
      {data.is_sfx && (
        <span className="shrink-0 rounded bg-purple-100 px-1 py-px text-[9px] font-semibold uppercase tracking-wider text-purple-800">
          SFX
        </span>
      )}
      {showRaw && !isDefault && (
        <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground/50">
          {bankMsb}/{bankLsb}/{program}
        </span>
      )}
    </span>
  )
}
