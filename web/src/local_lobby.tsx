import { useEffect, useMemo, useState } from "react";

import {
  bootstrapLocal,
  createLobby,
  getLobby,
  joinLobby,
  lobbyWebSocketUrl,
  setLobbyReady,
  startLobby,
  type LobbyView,
  type LocalBootstrap,
  type RuntimeRecord,
} from "./api";
import {
  bindHostFundedAI,
  getPreferredRuntimeId,
  listRuntimes,
  runLobbyAI,
  setPreferredRuntimeId,
  type AIRun,
} from "./ai_api";
import { defaultCast } from "./content";

const LOCAL_IDENTITY_KEY = "paradox-cast-local-identity";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected local lobby error";
}

export function LocalLobby({ onRunComplete }: { onRunComplete: (run: AIRun) => void }) {
  const [bootstrap, setBootstrap] = useState<LocalBootstrap | null>(null);
  const [runtimes, setRuntimes] = useState<RuntimeRecord[]>([]);
  const [selectedRuntimeId, setSelectedRuntimeId] = useState<string | null>(() => getPreferredRuntimeId());
  const [identityId, setIdentityId] = useState(() => localStorage.getItem(LOCAL_IDENTITY_KEY) ?? "local-host");
  const [lobby, setLobby] = useState<LobbyView | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [socketState, setSocketState] = useState("offline");
  const [runState, setRunState] = useState("Waiting for a frozen manifest");

  useEffect(() => {
    bootstrapLocal()
      .then(async (nextBootstrap) => {
        setBootstrap(nextBootstrap);
        const hostId = nextBootstrap.users.find((user) => user.is_host)?.id;
        if (!hostId) return;
        const nextRuntimes = await listRuntimes(hostId);
        setRuntimes(nextRuntimes);
        const preferred = getPreferredRuntimeId();
        const selected = nextRuntimes.find((runtime) => runtime.id === preferred)
          ?? nextRuntimes.find((runtime) => runtime.provider !== "mock")
          ?? nextRuntimes[0];
        if (selected) {
          setSelectedRuntimeId(selected.id);
          setPreferredRuntimeId(selected.id);
        }
      })
      .catch((reason) => setError(messageOf(reason)));
  }, []);

  useEffect(() => {
    localStorage.setItem(LOCAL_IDENTITY_KEY, identityId);
  }, [identityId]);

  const identity = bootstrap?.users.find((user) => user.id === identityId) ?? bootstrap?.users[0];
  const member = lobby?.members.find((item) => item.user_id === identity?.id);
  const hostMember = lobby?.members.find((item) => item.user_id === lobby.host_id);
  const host = identity?.id === lobby?.host_id;
  const selectedRuntime = runtimes.find((runtime) => runtime.id === selectedRuntimeId);
  const boundRuntime = runtimes.find((runtime) => runtime.id === member?.runtime_profile_id);
  const allPlayersReady = Boolean(
    lobby?.members.filter((item) => item.role !== "spectator").length
    && lobby?.members.filter((item) => item.role !== "spectator").every((item) => item.ready),
  );

  useEffect(() => {
    if (!lobby || !identity || !member) return;
    const socket = new WebSocket(lobbyWebSocketUrl(lobby.id, identity.id));
    socket.onopen = () => setSocketState("live");
    socket.onclose = () => setSocketState("offline");
    socket.onerror = () => setSocketState("fallback polling");
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type?: string; lobby?: LobbyView };
      if (payload.type === "lobby.updated" && payload.lobby) setLobby(payload.lobby);
    };
    const fallback = window.setInterval(() => {
      getLobby(lobby.id).then(setLobby).catch(() => undefined);
    }, 4_000);
    return () => {
      window.clearInterval(fallback);
      socket.close();
    };
  }, [lobby?.id, identity?.id, member?.id]);

  const assignedCast = useMemo(() => {
    const byName = new Map(defaultCast.map((cast) => [cast.name, cast]));
    return new Map((bootstrap?.users ?? []).map((user) => [user.id, byName.get(user.character.name)]));
  }, [bootstrap]);

  const runtimeById = useMemo(() => new Map(runtimes.map((runtime) => [runtime.id, runtime])), [runtimes]);

  const act = async (operation: () => Promise<LobbyView | void>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await operation();
      if (next) setLobby(next);
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(false);
    }
  };

  const create = () => {
    if (!bootstrap || !identity) return;
    void act(async () => {
      const next = await createLobby(identity.id, bootstrap.scenario.id);
      setJoinCode(next.join_code);
      return next;
    });
  };

  const join = () => {
    if (!identity || !joinCode.trim()) return;
    void act(() => joinLobby(identity.id, joinCode.trim().toUpperCase()));
  };

  const chooseRuntime = (runtimeId: string) => {
    setSelectedRuntimeId(runtimeId);
    setPreferredRuntimeId(runtimeId);
  };

  const bind = () => {
    if (!identity || !lobby || !bootstrap) return;
    if (host && !selectedRuntimeId) {
      setError("Create or select an AI runtime in Integration Lab first.");
      return;
    }
    const slot = String(bootstrap.users.findIndex((item) => item.id === identity.id) + 1);
    void act(() => bindHostFundedAI(lobby.id, identity.id, {
      cast_slot: slot,
      character_card_id: identity.character.id,
      runtime_profile_id: host ? selectedRuntimeId : null,
    }));
  };

  const ready = () => {
    if (!identity || !lobby || !member) return;
    void act(() => setLobbyReady(lobby.id, identity.id, !member.ready));
  };

  const start = async () => {
    if (!identity || !lobby) return;
    setBusy(true);
    setError(null);
    setRunState("Locking manifest…");
    try {
      await startLobby(lobby.id, identity.id);
      setLobby(await getLobby(lobby.id));
      setRunState("Calling bound AI runtimes…");
      const run = await runLobbyAI(lobby.id, identity.id, 2);
      setRunState(run.case.fallback_used ? "Run completed with fallback actions" : "AI run completed");
      onRunComplete(run);
    } catch (reason) {
      setError(messageOf(reason));
      setRunState("AI run failed");
    } finally {
      setBusy(false);
    }
  };

  if (!bootstrap || !identity) {
    return <section className="lobby-shell"><p>{error ?? "Preparing local multiplayer identities…"}</p></section>;
  }

  const hostRuntimeReady = Boolean(hostMember?.runtime_profile_id);
  const bindingNeedsUpdate = !member?.character_card_id
    || (host && member.runtime_profile_id !== selectedRuntimeId);

  return (
    <section className="lobby-shell" aria-label="Local online lobby">
      <header className="lobby-heading">
        <div>
          <p className="eyebrow">Step 2 · Bind cast and AI runtime</p>
          <h2>{bootstrap.scenario.title}</h2>
          <p>The host supplies one encrypted runtime. Every AI decision is restricted to legal actions generated by Python.</p>
        </div>
        <aside className="join-code">
          <p className="note-label">Join code</p>
          <strong>{lobby?.join_code ?? "Not created"}</strong>
          <span>{lobby ? `${lobby.status} · ${socketState}` : "Create or join a lobby"}</span>
        </aside>
      </header>

      <div className="ai-flow-strip">
        <span className="is-complete">1 · Configure runtime</span>
        <span className={lobby ? "is-complete" : ""}>2 · Create lobby</span>
        <span className={allPlayersReady ? "is-complete" : ""}>3 · Bind & ready</span>
        <span className={lobby?.run_manifest ? "is-complete" : ""}>4 · AI replay</span>
      </div>

      <div className="local-lobby-controls">
        <label>
          Local identity
          <select value={identity.id} onChange={(event) => setIdentityId(event.target.value)}>
            {bootstrap.users.map((user) => <option key={user.id} value={user.id}>{user.display_name} · {user.character.name}</option>)}
          </select>
        </label>
        {identity.is_host && <label>
          Host-funded AI runtime
          <select
            value={selectedRuntimeId ?? ""}
            onChange={(event) => chooseRuntime(event.target.value)}
            disabled={lobby?.status === "running"}
          >
            <option value="" disabled>Select a runtime</option>
            {runtimes.map((runtime) => <option key={runtime.id} value={runtime.id}>
              {runtime.display_name} · {runtime.provider}/{runtime.model_id}
            </option>)}
          </select>
        </label>}
        {!lobby && identity.is_host && <button type="button" disabled={busy || !selectedRuntimeId} onClick={create}>Create AI lobby</button>}
        {!lobby && !identity.is_host && <>
          <label>Join code<input value={joinCode} onChange={(event) => setJoinCode(event.target.value)} placeholder="Paste host code" /></label>
          <button type="button" disabled={busy || !joinCode.trim()} onClick={join}>Join lobby</button>
        </>}
        {lobby && !member && <button type="button" disabled={busy} onClick={() => void act(() => joinLobby(identity.id, lobby.join_code))}>Join as this identity</button>}
      </div>

      {runtimes.length === 0 && identity.is_host && <p className="integration-error">No host runtime exists. Open Integration Lab, save an API key, and test a model first.</p>}
      {error && <p className="integration-error">{error}</p>}

      {lobby && <>
        <div className="lobby-meta">
          <span>Status: {lobby.status}</span>
          <span>Participants: {lobby.members.length}</span>
          <span>Realtime: {socketState}</span>
          <span>{runState}</span>
        </div>
        <div className="lobby-cast">
          {lobby.members.map((item) => {
            const local = bootstrap.users.find((user) => user.id === item.user_id);
            const cast = assignedCast.get(item.user_id);
            const runtime = runtimeById.get(item.runtime_profile_id ?? "");
            return <article className="lobby-card" key={item.id}>
              {cast && <img className="local-lobby-avatar" src={cast.portrait} alt={cast.name} />}
              <div>
                <p className="note-label">{item.role} · Slot {item.cast_slot ?? "unbound"}</p>
                <h3>{local?.display_name ?? item.user_id}</h3>
                <p>{local?.character.name ?? "No local profile"}</p>
                <small>{runtime ? `${runtime.provider} · ${runtime.model_id}` : "Waiting for host runtime binding"}</small>
              </div>
              <span className={`lobby-ready-state ${item.ready ? "is-ready" : ""}`}>{item.ready ? "✓ Ready" : "Not ready"}</span>
            </article>;
          })}
        </div>
        {member && lobby.status === "open" && <footer className="lobby-footer">
          <div>
            <p className="note-label">Your binding</p>
            <strong>{member.character_card_id
              ? `${identity.character.name} · ${boundRuntime?.display_name ?? "Host-funded runtime"}`
              : host
                ? `Bind ${identity.character.name} to ${selectedRuntime?.display_name ?? "a selected runtime"}.`
                : hostRuntimeReady
                  ? `Bind ${identity.character.name} to the host-funded runtime.`
                  : "Wait for the host to bind an AI runtime first."}</strong>
          </div>
          <div className="lobby-footer-actions">
            {bindingNeedsUpdate && <button type="button" disabled={busy || (!host && !hostRuntimeReady)} onClick={bind}>{member.character_card_id ? "Apply selected runtime" : "Bind my character"}</button>}
            {member.character_card_id && !bindingNeedsUpdate && <button className={member.ready ? "is-ready" : ""} type="button" disabled={busy} onClick={ready}>{member.ready ? "Mark not ready" : "Mark ready"}</button>}
            {host && <button className="start-run" type="button" disabled={busy || !allPlayersReady} onClick={() => void start()}>{busy ? runState : "Start AI run →"}</button>}
          </div>
        </footer>}
        {lobby.run_manifest && <aside className="manifest-result">
          <p className="note-label">Frozen run manifest</p>
          <strong>{lobby.run_manifest.id}</strong>
          <span>Seed {lobby.run_manifest.seed} · {lobby.run_manifest.cast.length} AI cast bindings</span>
        </aside>}
      </>}
    </section>
  );
}
