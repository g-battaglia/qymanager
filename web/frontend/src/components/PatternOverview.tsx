import { useState } from "react"
import type { UdmDevice } from "@/lib/types"
import {
  getSectionsWithTracks,
  isDrumChannel,
  panLabel,
  type SectionInfo,
  type TrackInfo,
} from "@/lib/udm"
import { VoiceLabel } from "@/components/VoiceLabel"

function LevelBar({ value, max }: { value: number; max: number }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="h-1 w-full rounded-full bg-foreground/5">
      <div
        className="h-full rounded-full bg-foreground/30 transition-all"
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
    <div className="relative h-1 w-full rounded-full bg-foreground/5">
      {!isRandom && (
        <div
          className={`absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full ${
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
      className={`inline-flex h-5 min-w-[1.75rem] shrink-0 items-center justify-center rounded px-1.5 text-[10px] font-semibold tabular-nums ${
        isDrum
          ? "bg-amber-100 text-amber-800"
          : "bg-foreground/5 text-foreground/60"
      }`}
    >
      {isDrum ? "DR" : ch + 1}
    </span>
  )
}

function TrackRow({
  track,
  onSelect,
}: {
  track: TrackInfo
  onSelect: (path: string) => void
}) {
  const isMuted = track.mute
  return (
    <button
      type="button"
      onClick={() => onSelect(track.path)}
      className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/60 ${
        isMuted ? "opacity-50" : ""
      }`}
    >
      <span className="mt-0.5 w-4 shrink-0 text-[11px] font-semibold tabular-nums text-muted-foreground">
        {track.index + 1}
      </span>
      <ChannelBadge ch={track.midiChannel} />
      <div className="min-w-0 flex-1 space-y-1">
        <VoiceLabel
          bankMsb={track.voice.bank_msb}
          bankLsb={track.voice.bank_lsb}
          program={track.voice.program}
          channel={track.midiChannel + 1}
          showDrumBadge={false}
        />
        <div className="grid grid-cols-2 gap-1.5">
          <LevelBar value={track.volume} max={127} />
          <PanIndicator value={track.pan} />
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9px] tabular-nums text-muted-foreground/70">
          <span>Vol {track.volume}</span>
          <span>Pan {panLabel(track.pan)}</span>
          {track.reverbSend > 0 && <span>Rev {track.reverbSend}</span>}
          {track.chorusSend > 0 && <span>Cho {track.chorusSend}</span>}
          {isMuted && (
            <span className="font-medium uppercase tracking-wider text-foreground/40">
              Mute
            </span>
          )}
        </div>
      </div>
    </button>
  )
}

function SectionBlock({
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
  const melodicTracks = section.tracks.filter(
    (t) => !isDrumChannel(t.midiChannel),
  )

  return (
    <div>
      <button
        type="button"
        onClick={onActivate}
        className="group flex w-full items-center justify-between gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-muted/40"
      >
        <div className="flex items-center gap-2">
          <span className="w-3 text-sm text-muted-foreground">
            {isActive ? "▾" : "▸"}
          </span>
          <span className="text-sm font-semibold">
            {section.name.replace(/_/g, " ")}
          </span>
          {!section.enabled && (
            <span className="rounded bg-muted px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
              Inactive
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px] tabular-nums text-muted-foreground">
          <span>{section.tracks.length} tracks</span>
          {mutedCount > 0 && <span>· {mutedCount} muted</span>}
        </div>
      </button>

      {isActive && (
        <div className="ml-3 mt-1 space-y-3 border-l border-border/40 pl-3">
          {drumTracks.length > 0 && (
            <div>
              <p className="mb-1 text-[9px] font-semibold uppercase tracking-[0.2em] text-amber-600">
                Rhythm
              </p>
              <div className="grid gap-0.5 sm:grid-cols-2 xl:grid-cols-3">
                {drumTracks.map((t) => (
                  <TrackRow key={t.index} track={t} onSelect={onSelectTrack} />
                ))}
              </div>
            </div>
          )}

          {melodicTracks.length > 0 && (
            <div>
              <p className="mb-1 text-[9px] font-semibold uppercase tracking-[0.2em] text-foreground/50">
                Melodic
              </p>
              <div className="grid gap-0.5 sm:grid-cols-2 xl:grid-cols-3">
                {melodicTracks.map((t) => (
                  <TrackRow key={t.index} track={t} onSelect={onSelectTrack} />
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

  return (
    <div>
      <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
        Pattern Structure
      </p>
      <h3 className="mt-2 text-xl font-semibold">Tracks per Section</h3>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">
        Click a track to inspect or edit its parameters.
      </p>

      {sections.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">
          No pattern sections with tracks found in this file.
        </p>
      ) : (
        <div className="mt-4 divide-y divide-border/40">
          {sections.map((section) => (
            <div key={section.name} className="py-1.5">
              <SectionBlock
                section={section}
                isActive={activeSection === section.name}
                onActivate={() =>
                  setActiveSection(
                    activeSection === section.name ? "" : section.name,
                  )
                }
                onSelectTrack={onSelectNode}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
