import { useState } from "react"
import type { UdmDevice } from "@/lib/types"
import {
  getSectionsWithTracks,
  isDrumChannel,
  panLabel,
  type SectionInfo,
  type TrackInfo,
} from "@/lib/udm"

function LevelBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="h-1.5 w-full rounded-full bg-foreground/5">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function PanIndicator({ value }: { value: number }) {
  const normalized = (value / 127) * 2 - 1
  const isCenter = value === 64
  const isRandom = value === 0
  const left = 50 - normalized * 40
  return (
    <div className="relative h-1.5 w-full rounded-full bg-foreground/5">
      {!isRandom && (
        <div
          className={`absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full ${
            isCenter ? "bg-foreground/40" : "bg-foreground/60"
          }`}
          style={{ left: `${left}%` }}
        />
      )}
      {isRandom && (
        <div className="absolute inset-0 flex items-center justify-center text-[8px] text-foreground/30">
          ?
        </div>
      )}
    </div>
  )
}

function ChannelBadge({ ch }: { ch: number }) {
  const isDrum = isDrumChannel(ch)
  return (
    <span
      className={`inline-flex h-5 min-w-[1.75rem] items-center justify-center rounded-md px-1.5 text-[10px] font-semibold tabular-nums ${
        isDrum
          ? "bg-amber-100 text-amber-800"
          : "bg-foreground/5 text-foreground/60"
      }`}
    >
      {isDrum ? "DR" : ch + 1}
    </span>
  )
}

function TrackStrip({
  track,
  onSelect,
}: {
  track: TrackInfo
  onSelect: (path: string) => void
}) {
  const isDrum = isDrumChannel(track.midiChannel)
  const hasVoice = track.voice.bank_msb !== 0 || track.voice.bank_lsb !== 0 || track.voice.program !== 0
  const isMuted = track.mute

  return (
    <button
      type="button"
      onClick={() => onSelect(track.path)}
      className={`group w-full rounded-2xl border px-3 py-2.5 text-left transition-colors ${
        isMuted
          ? "border-border/40 bg-muted/20 opacity-50"
          : "border-border/60 bg-card hover:border-foreground/15 hover:bg-muted/40"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="w-4 shrink-0 text-[11px] font-semibold tabular-nums text-muted-foreground">
          {track.index + 1}
        </span>

        <ChannelBadge ch={track.midiChannel} />

        <div className="min-w-0 flex-1">
          {hasVoice ? (
            <p className="truncate text-xs font-medium">
              {isDrum ? "Drum Kit" : `Voice ${track.voice.bank_msb}/${track.voice.bank_lsb}/${track.voice.program}`}
            </p>
          ) : (
            <p className="truncate text-xs text-muted-foreground">
              {isDrum ? "Default Drum Kit" : "Default Piano"}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <span className="text-[10px] font-semibold tabular-nums text-muted-foreground">
            {track.volume}
          </span>
        </div>
      </div>

      <div className="mt-1.5 space-y-1 pl-6">
        <LevelBar value={track.volume} max={127} color="bg-foreground/25 group-hover:bg-foreground/35" />
        <PanIndicator value={track.pan} />
      </div>

      <div className="mt-1.5 flex items-center gap-2 pl-6">
        <span className="text-[9px] tabular-nums text-muted-foreground/60">
          Pan {panLabel(track.pan)}
        </span>
        {track.reverbSend > 0 && (
          <span className="text-[9px] tabular-nums text-muted-foreground/60">
            Rev {track.reverbSend}
          </span>
        )}
        {track.chorusSend > 0 && (
          <span className="text-[9px] tabular-nums text-muted-foreground/60">
            Cho {track.chorusSend}
          </span>
        )}
        {isMuted && (
          <span className="text-[9px] font-medium uppercase tracking-wider text-foreground/30">
            Mute
          </span>
        )}
      </div>
    </button>
  )
}

function SectionCard({
  section,
  isActive,
  onActivate,
  onSelectTrack,
}: {
  section: SectionInfo
  isActive: boolean
  onActivate: () => void
  onSelectTrack: (path: string) => void
}) {
  const mutedCount = section.tracks.filter((t) => t.mute).length
  const drumTracks = section.tracks.filter((t) => isDrumChannel(t.midiChannel))
  const melodicTracks = section.tracks.filter((t) => !isDrumChannel(t.midiChannel))

  return (
    <div className="rounded-[2rem] border border-border/70 bg-card shadow-sm">
      <button
        type="button"
        onClick={onActivate}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
      >
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Section
          </p>
          <h3 className="mt-1 text-lg font-semibold">{section.name.replace(/_/g, " ")}</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-foreground/5 px-3 py-1 text-xs tabular-nums text-muted-foreground">
            {section.tracks.length} tracks
          </span>
          {mutedCount > 0 && (
            <span className="rounded-full bg-foreground/5 px-3 py-1 text-xs tabular-nums text-muted-foreground">
              {mutedCount} muted
            </span>
          )}
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              section.enabled
                ? "bg-emerald-50 text-emerald-700"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {section.enabled ? "Active" : "Inactive"}
          </span>
        </div>
      </button>

      {isActive && (
        <div className="border-t border-border/50 px-4 py-4">
          {drumTracks.length > 0 && (
            <div className="mb-4">
              <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-600">
                Rhythm
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {drumTracks.map((t) => (
                  <TrackStrip key={t.index} track={t} onSelect={onSelectTrack} />
                ))}
              </div>
            </div>
          )}

          {melodicTracks.length > 0 && (
            <div>
              <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-foreground/50">
                melodic
              </p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {melodicTracks.map((t) => (
                  <TrackStrip key={t.index} track={t} onSelect={onSelectTrack} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function PatternOverview({
  device,
  onSelectNode,
}: {
  device: UdmDevice
  onSelectNode: (path: string) => void
}) {
  const sections = getSectionsWithTracks(device)
  const [activeSection, setActiveSection] = useState<string>(
    sections[0]?.name ?? "",
  )

  if (sections.length === 0) {
    return (
      <div className="rounded-[2rem] border border-dashed border-border/80 px-6 py-8 text-center">
        <p className="text-sm text-muted-foreground">
          No pattern sections with tracks found in this file.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Pattern Structure
        </p>
        <h3 className="mt-2 text-xl font-semibold">Tracks per Section</h3>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Click a track strip to inspect or edit its parameters.
        </p>
      </div>

      {sections.map((section) => (
        <SectionCard
          key={section.name}
          section={section}
          isActive={activeSection === section.name}
          onActivate={() =>
            setActiveSection(activeSection === section.name ? "" : section.name)
          }
          onSelectTrack={onSelectNode}
        />
      ))}
    </div>
  )
}
