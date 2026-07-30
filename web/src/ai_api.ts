import {
  apiBase,
  type DemoRun,
  type LobbyView,
  type RuntimeRecord,
} from "./api";

export type AIRun = DemoRun & {
  case: DemoRun["case"] & {
    mode: "ai";
    turns: number;
    fallback_used: boolean;
    provider_summary: Array<{
      runtime_profile_id: string;
      display_name: string;
      provider: string;
      model_id: string;
    }>;
  };
  decisions: Array<{
    action_id: string;
    turn: number;
    character_id: string;
    character_name: string;
    runtime_profile_id: string;
    provider: string;
    source: string;
    model_id: string;
    accepted: boolean;
    reason: string;
    action: Record<string, unknown>;
  }>;
  runtime_failures: Array<{
    character_id: string;
    runtime_profile_id: string;
    provider: string;
    error: string;
  }>;
};

export const PREFERRED_RUNTIME_KEY = "paradox-cast-preferred-host-runtime";

const query = (values: Record<string, string | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params.toString();
};

async function aiFetch<T>(path: string, init?: RequestInit): Promise<T> {
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
      // Preserve the HTTP status when the body is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const listRuntimes = (ownerId: string) => aiFetch<RuntimeRecord[]>(
  `/api/runtimes?${query({ owner_id: ownerId })}`,
);

export const bindHostFundedAI = (
  lobbyId: string,
  userId: string,
  payload: {
    cast_slot: string;
    character_card_id: string;
    runtime_profile_id: string | null;
  },
) => aiFetch<LobbyView>(
  `/api/lobbies/${lobbyId}/ai-binding?${query({ user_id: userId })}`,
  {
    method: "PUT",
    body: JSON.stringify({ ...payload, funding_model: "host_funded" }),
  },
);

export const runLobbyAI = (
  lobbyId: string,
  ownerId: string,
  turns = 2,
) => aiFetch<AIRun>(
  `/api/lobbies/${lobbyId}/run-ai?${query({
    owner_id: ownerId,
    turns: String(turns),
    allow_fallback: "true",
  })}`,
  { method: "POST" },
);

export function getPreferredRuntimeId(): string | null {
  return localStorage.getItem(PREFERRED_RUNTIME_KEY);
}

export function setPreferredRuntimeId(runtimeId: string): void {
  localStorage.setItem(PREFERRED_RUNTIME_KEY, runtimeId);
}
