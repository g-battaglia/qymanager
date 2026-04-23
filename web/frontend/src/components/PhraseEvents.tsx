import { usePhrases } from "@/lib/queries"
import type { PhraseEvent, PhraseModel } from "@/lib/types"

function NoteBadge({
  noteName,
  velocity,
}: {
  noteName: string | null
  velocity: number | null
}) {
  if (!noteName) return null
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-medium">{noteName}</span>
      {velocity !== null && velocity > 0 && (
        <span className="text-muted-foreground/60">vel {velocity}</span>
      )}
    </span>
  )
}

function EventRow({ event, index }: { event: PhraseEvent; index: number }) {
  const isDrum = event.kind === "drum"
  const kindLabel =
    { drum: "Drum", note: "Note", alt_note: "Alt" }[event.kind] ?? event.kind

  return (
    <div
      className={`flex items-center gap-3 px-3 py-1 text-xs ${
        index % 2 === 0 ? "bg-transparent" : "bg-muted/40"
      }`}
    >
      <span className="w-8 shrink-0 tabular-nums text-muted-foreground/50">
        {index + 1}
      </span>
      <span
        className={`w-10 shrink-0 text-[10px] font-semibold uppercase tracking-wider ${
          isDrum ? "text-amber-600" : "text-foreground/60"
        }`}
      >
        {kindLabel}
      </span>
      <span className="w-16 shrink-0">
        <NoteBadge noteName={event.note_name} velocity={event.velocity} />
      </span>
      <span className="tabular-nums text-muted-foreground/50">
        ch{event.channel + 1}
      </span>
      {event.tick > 0 && (
        <span className="tabular-nums text-muted-foreground/50">
          +{event.tick}
        </span>
      )}
    </div>
  )
}

function PhraseBlock({ phrase }: { phrase: PhraseModel }) {
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2">
        <div>
          <p className="text-sm font-semibold">
            {phrase.name || "Unnamed Phrase"}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            Tempo {phrase.tempo} BPM
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] tabular-nums text-muted-foreground">
          <span>{phrase.note_count} notes</span>
          <span>·</span>
          <span>{phrase.event_count} events</span>
        </div>
      </div>

      <div className="max-h-64 overflow-auto rounded-md bg-muted/20">
        {phrase.events.length > 0 ? (
          phrase.events.map((event, i) => (
            <EventRow key={i} event={event} index={i} />
          ))
        ) : (
          <p className="px-4 py-3 text-xs text-muted-foreground">
            No note events in this phrase.
          </p>
        )}
      </div>
    </div>
  )
}

export function PhraseEvents({ deviceId }: { deviceId: string }) {
  const { data, isLoading, error } = usePhrases(deviceId)

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading phrase data...</p>
  }
  if (error) {
    return (
      <p className="text-sm text-muted-foreground">Could not load phrase data.</p>
    )
  }
  if (!data) return null

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Musical Events
        </p>
        <h3 className="mt-2 text-xl font-semibold">Phrase Data</h3>
      </div>

      {data.note && (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50 px-4 py-3 text-amber-950">
          <p className="text-sm leading-6">{data.note}</p>
        </div>
      )}

      {data.phrases.length > 0 ? (
        <div className="divide-y divide-border/40">
          {data.phrases.map((phrase, i) => (
            <div key={i} className="py-3 first:pt-0 last:pb-0">
              <PhraseBlock phrase={phrase} />
            </div>
          ))}
        </div>
      ) : !data.note ? (
        <p className="text-sm text-muted-foreground">
          No phrase data available for this file.
        </p>
      ) : null}
    </div>
  )
}
