import type { TimelineEvent } from "./content";

export type SimulationEvent = { type: string; at: number; details: Record<string, unknown> };
export type SimulationIntervention = { kind: string; reason: string; details?: Record<string, unknown> };
export type DemoRun = {
  case: { title: string; lobby_code: string; manifest_id: string; seed: number };
  original: { events: SimulationEvent[]; final_state: Record<string, unknown> };
  branched: { events: SimulationEvent[]; final_state: Record<string, unknown>; interventions: SimulationIntervention[] };
  divergence: { added_events: number; removed_events: number; final_state_changed: boolean };
};

export type LocalBootstrapUser = {
  id: string;
  display_name: string;
  is_host: boolean;
  character: { id: string; name: string; adult_age: number };
  runtime: { id: string; display_name: string; provider: string; model_id: string };
};
export type LocalBootstrap = {
  enabled: boolean;
  users: LocalBootstrapUser[];
  scenario: { id: string; title: string; owner_id: string; version: number };
  instructions: string;
};
export type LobbyMember = {
  id: string;
  user_id: string;
  role: "host" | "participant" | "spectator";
  cast_slot: string | null;
  character_card_id: string | null;
  runtime_profile_id: string | null;
  funding_model: "host_funded" | "bring_your_own";
  ready: boolean;
};
export type RunManifest = {
  id: string;
  lobby_id: string;
  scenario_version: number;
  cast: Array<Record<string, unknown>>;
  runtime_bindings: Array<Record<string, unknown>>;
  rules: Record<string, unknown>;
  seed: number;
  asset_versions: Record<string, number>;
  intervention_rules: Record<string, unknown>;
  frozen_at: string;
};
export type LobbyView = {
  id: string;
  host_id: string;
  scenario_id: string;
  join_code: string;
  visibility: "private" | "unlisted" | "public";
  status: "open" | "locked" | "running" | "closed";
  rules: Record<string, unknown>;
  members: LobbyMember[];
  run_manifest?: RunManifest;
};
export type SystemStatus = {
  app_env: string;
  database: { dialect: string; configured: boolean; reachable: boolean; error?: string | null };
  object_storage: { configured: boolean; reachable: boolean; bucket?: string | null; error?: string };
  credential_encryption: { persistent_key_configured: boolean };
  local_bootstrap_enabled: boolean;
};
export type CredentialRecord = { id: string; provider: string; label: string; masked_identifier: string };
export type RuntimeRecord = {
  id: string;
  display_name: string;
  provider: string;
  model_id: string;
  credential_id: string | null;
};
export type AssetRecord = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number | null;
  visibility: "private" | "unlisted" | "public";
  status: "pending" | "ready" | "failed";
  created_at: string;
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

export const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json() as { detail?: unknown };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (payload.detail) message = JSON.stringify(payload.detail);
    } catch {
      // Keep the HTTP status when the body is not JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const query = (values: Record<string, string | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value) params.set(key, value); });
  return params.toString();
};

export async function startDemoRun(): Promise<DemoRun> {
  return apiFetch<DemoRun>("/api/demo/run", { method: "POST" });
}

export const bootstrapLocal = () => apiFetch<LocalBootstrap>("/api/local/bootstrap", { method: "POST" });
export const getSystemStatus = () => apiFetch<SystemStatus>("/api/system/status");

export const createLobby = (ownerId: string, scenarioId: string) => apiFetch<LobbyView>(
  `/api/lobbies?${query({ owner_id: ownerId })}`,
  { method: "POST", body: JSON.stringify({ scenario_id: scenarioId, visibility: "unlisted", rules: { memory_editing: "forbidden" } }) },
);
export const joinLobby = (userId: string, joinCode: string) => apiFetch<LobbyView>(
  `/api/lobbies/join?${query({ user_id: userId })}`,
  { method: "POST", body: JSON.stringify({ join_code: joinCode, role: "participant" }) },
);
export const getLobby = (lobbyId: string) => apiFetch<LobbyView>(`/api/lobbies/${lobbyId}`);
export const bindLobbyMember = (
  lobbyId: string,
  userId: string,
  payload: { cast_slot: string; character_card_id: string; runtime_profile_id: string; funding_model: "host_funded" | "bring_your_own" },
) => apiFetch<LobbyView>(
  `/api/lobbies/${lobbyId}/binding?${query({ user_id: userId })}`,
  { method: "PUT", body: JSON.stringify(payload) },
);
export const setLobbyReady = (lobbyId: string, userId: string, ready: boolean) => apiFetch<LobbyView>(
  `/api/lobbies/${lobbyId}/ready?${query({ user_id: userId })}`,
  { method: "PUT", body: JSON.stringify({ ready }) },
);
export const startLobby = (lobbyId: string, ownerId: string) => apiFetch<RunManifest>(
  `/api/lobbies/${lobbyId}/start?${query({ owner_id: ownerId })}`,
  { method: "POST", body: JSON.stringify({ intervention_rules: { allowed: ["delay_information", "reveal_evidence", "redirect_information"] } }) },
);

export function lobbyWebSocketUrl(lobbyId: string, userId: string): string {
  const origin = apiBase || window.location.origin;
  const url = new URL(`/api/lobbies/${lobbyId}/ws`, origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("user_id", userId);
  return url.toString();
}

export const createCredential = (ownerId: string, provider: string, label: string, apiSecret: string) => apiFetch<CredentialRecord>(
  `/api/credentials?${query({ owner_id: ownerId })}`,
  { method: "POST", body: JSON.stringify({ provider, label, api_secret: apiSecret }) },
);
export const createRuntime = (
  ownerId: string,
  payload: { display_name: string; provider: string; model_id: string; credential_id?: string; temperature?: number },
) => apiFetch<RuntimeRecord>(
  `/api/runtimes?${query({ owner_id: ownerId })}`,
  { method: "POST", body: JSON.stringify(payload) },
);
export const testRuntime = (ownerId: string, runtimeId: string) => apiFetch<Record<string, unknown>>(
  `/api/runtimes/${runtimeId}/decide?${query({ owner_id: ownerId })}`,
  {
    method: "POST",
    body: JSON.stringify({
      character_id: "hana",
      legal_actions: [
        { kind: "wait", reason: "observe the room" },
        { kind: "move", destination_id: "station" },
      ],
      context: { location: "lounge", objective: "trace the missing hour" },
    }),
  },
);

export const listAssets = (ownerId: string) => apiFetch<AssetRecord[]>(`/api/assets?${query({ owner_id: ownerId })}`);
export const uploadAsset = async (ownerId: string, file: File): Promise<AssetRecord> => {
  const signed = await apiFetch<{
    asset: AssetRecord;
    upload: { method: string; url: string; headers: Record<string, string> };
  }>(`/api/assets/presign-upload?${query({ owner_id: ownerId })}`, {
    method: "POST",
    body: JSON.stringify({ filename: file.name, content_type: file.type || "application/octet-stream", visibility: "private" }),
  });
  const uploadResponse = await fetch(signed.upload.url, {
    method: signed.upload.method,
    headers: signed.upload.headers,
    body: file,
  });
  if (!uploadResponse.ok) throw new Error(`Object upload failed (${uploadResponse.status})`);
  return apiFetch<AssetRecord>(`/api/assets/${signed.asset.id}/complete?${query({ owner_id: ownerId })}`, {
    method: "POST",
    body: JSON.stringify({ expected_size_bytes: file.size }),
  });
};
export const getAssetDownload = (assetId: string, viewerId: string) => apiFetch<{ url: string }>(
  `/api/assets/${assetId}/download?${query({ viewer_id: viewerId })}`,
);
