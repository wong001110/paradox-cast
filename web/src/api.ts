import type { TimelineEvent } from "./content";

export type SimulationEvent = { type: string; at: number; details: Record<string, unknown> };
export type DemoRun = {
  case: { title: string; lobby_code: string; manifest_id: string; seed: number };
  original: { events: SimulationEvent[]; final_state: Record<string, unknown> };
  branched: { events: SimulationEvent[]; final_state: Record<string, unknown>; interventions: Array<{ kind: string; reason: string }> };
  divergence: { added_events: number; removed_events: number; final_state_changed: boolean };
};

const eventKind = (type: string): TimelineEvent["kind"] => {
  if (type.includes("movement") || type.includes("route")) return "movement";
  if (type.includes("observation") || type.includes("overhearing")) return "observation";
  if (type.includes("dialogue") || type.includes("interception")) return "dialogue";
  return "intervention";
};

const pretty = (type: string) => type.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export function timelineFromSimulation(events: SimulationEvent[], prefix: string): TimelineEvent[] {
  return events.slice(0, 8).map((event, index) => {
    const details = event.details;
    const source = typeof details.source === "string" ? ` · ${details.source}` : "";
    const subject = typeof details.character_id === "string" ? details.character_id : typeof details.speaker_id === "string" ? details.speaker_id : "timeline";
    return {
      id: `${prefix}-${index}-${event.type}`,
      time: `19:${String(10 + event.at).padStart(2, "0")}`,
      kind: eventKind(event.type),
      title: pretty(event.type),
      detail: `${String(subject)}${source}`,
    };
  });
}

export async function startDemoRun(): Promise<DemoRun> {
  const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
  const response = await fetch(`${base}/api/demo/run`, { method: "POST" });
  if (!response.ok) throw new Error(`Demo run failed (${response.status})`);
  return response.json() as Promise<DemoRun>;
}
