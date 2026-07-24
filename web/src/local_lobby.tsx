import { useEffect, useMemo, useState } from "react";

import {
  bindLobbyMember,
  bootstrapLocal,
  createLobby,
  getLobby,
  joinLobby,
  lobbyWebSocketUrl,
  setLobbyReady,
  startLobby,
  type LobbyView,
  type LocalBootstrap,
} from "./api";
import { defaultCast } from "./content";

const LOCAL_IDENTITY_KEY = "paradox-cast-local-identity";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected local lobby error";
}

export function LocalLobby() {
  const [bootstrap, setBootstrap] = useState<LocalBootstrap | null>(null);
  const [identityId, setIdentityId] = useState(() => localStorage.getItem(LOCAL_IDENTITY_KEY) ?? "local-host");
  const [lobby, setLobby] = useState<LobbyView | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [socketState, setSocketState] = useState("offline");

  useEffect(() => {
    bootstrapLocal().then(setBootstrap).catch((reason) => setError(messageOf(reason)));
  }, []);

  useEffect(() => {
    localStorage.setItem(LOCAL_IDENTITY_KEY, identityId);
  }, [identityId]);

  const identity = bootstrap?.users.find((user) => user.id === identityId) ?? bootstrap?.users[0];
  const member = lobby?.members.find((item) => item.user_id === identity?.id);
  const host = identity?.id === lobby?.host_id;
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

  const bind = () => {
    if (!identity || !lobby || !bootstrap) return;
    const slot = String(bootstrap.users.findIndex((item) => item.id === identity.id) + 1);
    void act(() => bindLobbyMember(lobby.id, identity.id, {
      cast_slot: slot,
      character_card_id: identity.character.id,
      runtime_profile_id: identity.runtime.id,
      funding_model: "bring_your_own",
    }));
  };

  const ready = () => {
    if (!identity || !lobby || !member) return;
    void act(() => setLobbyReady(lobby.id, identity.id, !member.ready));
  };

  const start = () => {
    if (!identity || !lobby) return;
    void act(async () => {
      await startLobby(lobby.id, identity.id);
      return getLobby(lobby.id);
    });
  };

  if (!bootstrap || !identity) {
    return <section className="lobby-shell"><p>{error ?? "Preparing local multiplayer identities…"}</p></section>;
  }

  return (
    <section className="lobby-shell" aria-label="Local online lobby">
      <header className="lobby-heading">
        <div>
          <p className="eyebrow">Database-backed lobby · WebSocket snapshots</p>
          <h2>{bootstrap.scenario.title}</h2>
          <p>Use separate browser profiles, choose different identities, and join the same code.</p>
        </div>
        <aside className="join-code">
          <p className="note-label">Join code</p>
          <strong>{lobby?.join_code ?? "Not created"}</strong>
          <span>{lobby ? `${lobby.status} · ${socketState}` : "Create or join a lobby"}</span>
        </aside>
      </header>

      <div className="local-lobby-controls">
        <label>
          Local identity
          <select value={identity.id} onChange={(event) => setIdentityId(event.target.value)}>
            {bootstrap.users.map((user) => <option key={user.id} value={user.id}>{user.display_name} · {user.character.name}</option>)}
          </select>
        </label>
        {!lobby && identity.is_host && <button type="button" disabled={busy} onClick={create}>Create real lobby</button>}
        {!lobby && !identity.is_host && <>
          <label>Join code<input value={joinCode} onChange={(event) => setJoinCode(event.target.value)} placeholder="Paste host code" /></label>
          <button type="button" disabled={busy || !joinCode.trim()} onClick={join}>Join lobby</button>
        </>}
        {lobby && !member && <button type="button" disabled={busy} onClick={() => void act(() => joinLobby(identity.id, lobby.join_code))}>Join as this identity</button>}
      </div>

      {error && <p className="integration-error">{error}</p>}

      {lobby && <>
        <div className="lobby-meta">
          <span>Status: {lobby.status}</span>
          <span>Participants: {lobby.members.length}</span>
          <span>Realtime: {socketState}</span>
          <span>Database source of truth</span>
        </div>
        <div className="lobby-cast">
          {lobby.members.map((item) => {
            const local = bootstrap.users.find((user) => user.id === item.user_id);
            const cast = assignedCast.get(item.user_id);
            return <article className="lobby-card" key={item.id}>
              {cast && <img className="local-lobby-avatar" src={cast.portrait} alt={cast.name} />}
              <div>
                <p className="note-label">{item.role} · Slot {item.cast_slot ?? "unbound"}</p>
                <h3>{local?.display_name ?? item.user_id}</h3>
                <p>{local?.character.name ?? "No local profile"} · {local?.runtime.provider ?? "No runtime"}</p>
              </div>
              <span className={`lobby-ready-state ${item.ready ? "is-ready" : ""}`}>{item.ready ? "✓ Ready" : "Not ready"}</span>
            </article>;
          })}
        </div>
        {member && lobby.status === "open" && <footer className="lobby-footer">
          <div>
            <p className="note-label">Your binding</p>
            <strong>{member.character_card_id ? `${identity.character.name} · ${identity.runtime.display_name}` : "Bind your local card and runtime first."}</strong>
          </div>
          <div className="lobby-footer-actions">
            {!member.character_card_id && <button type="button" disabled={busy} onClick={bind}>Bind my character</button>}
            {member.character_card_id && <button className={member.ready ? "is-ready" : ""} type="button" disabled={busy} onClick={ready}>{member.ready ? "Mark not ready" : "Mark ready"}</button>}
            {host && <button className="start-run" type="button" disabled={busy || !allPlayersReady} onClick={start}>Lock manifest →</button>}
          </div>
        </footer>}
        {lobby.run_manifest && <aside className="manifest-result">
          <p className="note-label">Frozen run manifest</p>
          <strong>{lobby.run_manifest.id}</strong>
          <span>Seed {lobby.run_manifest.seed} · {lobby.run_manifest.cast.length} cast bindings</span>
        </aside>}
      </>}
    </section>
  );
}
