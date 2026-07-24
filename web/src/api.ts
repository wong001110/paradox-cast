import type { TimelineEvent } from "./content";

export type SimulationEvent = { type: string; at: number; details: Record<string, unknown> };
export type SimulationIntervention = { kind: string; reason: string; details?: Record<string, unknown> };
export type DemoRun = {
  case: { title: string; lobby_code: string; manifest_id: string; seed: number };
  original: { events: SimulationEvent[]; final_state: Record<string, unknown> };
  branched: { events: SimulationEvent[]; final_state: Record<string, unknown>; interventions: SimulationIntervention[] };
  divergence: { added_events: number; removed_events: number; final_state_changed: boolean };
};

const asString = (value: unknown): string | undefined => typeof value === "string" && value.length > 0 ? value : undefined;
const asStringArray = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
const pretty = (value: string) => value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const eventKind = (type: string): TimelineEvent["kind"] => {
  if (type.includes("movement") || type.includes("route") || type.includes("destination")) return "movement";
  if (type.includes("observation") || type.includes("overhearing") || type.includes("encounter")) return "observation";
  if (type.includes("dialogue") || type.includes("interception")) return "dialogue";
  return "intervention";
};

const formatTime = (offsetMinutes: number): string => {
  const totalMinutes = (19 * 60) + 10 + Math.max(0, offsetMinutes);
  const hour = Math.floor(totalMinutes / 60) % 24;
  const minute = totalMinutes % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
};

const eventTitle = (event: SimulationEvent, actorId: string | undefined, characterIds: string[]): string => {
  const actor = pretty(actorId ?? "timeline");
  const participants = characterIds.map(pretty).join(" & ");
  switch (event.type) {
    case "movement_started": return `${actor} starts moving`;
    case "route_segment_traversed": return `${actor} crosses a route segment`;
    case "movement_arrived": return `${actor} arrives`;
    case "destination_unchanged": return `${actor} remains in place`;
    case "observation": return `${actor} observes evidence`;
    case "dialogue": return `${actor} speaks`;
    case "partial_overhearing": return `${actor} overhears a fragment`;
    case "interception": return `${actor} intercepts information`;
    case "crossed_path_encounter": return `${participants || "Characters"} cross paths`;
    case "location_encounter": return `${participants || "Characters"} meet`;
    case "action_rejected": return `${actor}'s action is rejected`;
    case "wait": return `${actor} waits`;
    default: return pretty(event.type);
  }
};

const eventNarrative = (
  event: SimulationEvent,
  characterId: string | undefined,
  speakerId: string | undefined,
  characterIds: string[],
): string => {
  const details = event.details;
  const directContent = asString(details.content);
  if (directContent) return directContent;

  const actor = pretty(speakerId ?? characterId ?? "timeline");
  const from = pretty(asString(details.from_location_id) ?? "current location");
  const to = pretty(asString(details.to_location_id) ?? asString(details.destination_id) ?? "destination");
  const location = pretty(asString(details.location_id) ?? "location");
  const participants = characterIds.map(pretty).join(" and ");

  switch (event.type) {
    case "movement_started": return `${actor} leaves ${from} for ${to}.`;
    case "route_segment_traversed": return `${actor} travels from ${from} toward ${to}.`;
    case "movement_arrived": return `${actor} arrives at ${location}.`;
    case "destination_unchanged": return `${actor} remains at ${location}.`;
    case "crossed_path_encounter": return `${participants || "Two characters"} cross paths while travelling.`;
    case "location_encounter": return `${participants || "Two characters"} meet at ${location}.`;
    case "action_rejected": return `${pretty(asString(details.action) ?? "action")} rejected: ${pretty(asString(details.reason) ?? "unknown reason")}.`;
    case "wait": return `${actor} waits at ${location}.`;
    default: return eventTitle(event, speakerId ?? characterId, characterIds);
  }
};

export function timelineFromSimulation(
  events: SimulationEvent[],
  prefix: string,
  interventions: SimulationIntervention[] = [],
): TimelineEvent[] {
  const mapped = events.map((event, index): TimelineEvent => {
    const details = event.details;
    const characterIds = asStringArray(details.character_ids);
    const characterId = asString(details.character_id) ?? characterIds[0];
    const speakerId = asString(details.speaker_id);
    const source = asString(details.source);
    const locationId = asString(details.location_id)
      ?? (event.type === "movement_started" ? asString(details.from_location_id) : undefined)
      ?? asString(details.to_location_id)
      ?? asString(details.destination_id)
      ?? asString(details.from_location_id);
    const routeId = asString(details.route_id);
    const participantLabel = characterIds.length > 1
      ? characterIds.map(pretty).join(" & ")
      : pretty(speakerId ?? characterId ?? "timeline");
    const detailParts = [
      participantLabel,
      locationId ? `Location: ${pretty(locationId)}` : undefined,
      routeId ? `Route: ${pretty(routeId)}` : undefined,
      source ? `Source: ${pretty(source)}` : undefined,
    ].filter((item): item is string => Boolean(item));

    return {
      id: `${prefix}-${index}-${event.type}`,
      time: formatTime(event.at),
      kind: eventKind(event.type),
      title: eventTitle(event, speakerId ?? characterId, characterIds),
      detail: detailParts.join(" · "),
      characterId,
      characterIds: characterIds.length > 0 ? characterIds : undefined,
      speakerId,
      locationId,
      content: eventNarrative(event, characterId, speakerId, characterIds),
      source,
    };
  });

  const interventionEvents = interventions.map((intervention, index): TimelineEvent => {
    const actionId = asString(intervention.details?.action_id);
    return {
      id: `${prefix}-intervention-${index}-${intervention.kind}`,
      time: mapped[0]?.time ?? "19:10",
      kind: "intervention",
      title: `External intervention: ${pretty(intervention.kind)}`,
      detail: [intervention.reason, actionId ? `Action: ${pretty(actionId)}` : undefined].filter(Boolean).join(" · "),
      content: intervention.reason,
      source: "external_intervention",
    };
  });

  return [...interventionEvents, ...mapped];
}

export async function startDemoRun(): Promise<DemoRun> {
  const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
  const response = await fetch(`${base}/api/demo/run`, { method: "POST" });
  if (!response.ok) throw new Error(`Demo run failed (${response.status})`);
  return response.json() as Promise<DemoRun>;
}
