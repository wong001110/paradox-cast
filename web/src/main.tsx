import { createRoot } from "react-dom/client";
import { useEffect, useMemo, useState, type CSSProperties } from "react";

import "./styles.css";
import "./replay.css";
import "./integration.css";
import "./ai_flow.css";
import { startDemoRun, timelineFromSimulation, type DemoRun } from "./api";
import {
  adminSummary,
  branchedTimeline,
  defaultCast,
  differenceSummary,
  originalTimeline,
  productCopy,
  type TimelineEvent,
} from "./content";
import { IntegrationLab } from "./integration_lab";
import { LocalLobby } from "./local_lobby";

type View = "player" | "lobby" | "timeline" | "compare" | "integrations" | "admin";
type ReplayMode = "original" | "branch";

const viewLabels: Record<View, string> = {
  player: "Case player",
  lobby: "Lobby",
  timeline: "Timeline",
  compare: "A/B compare",
  integrations: "Integration lab",
  admin: "Admin overview",
};

const locationNames: Record<string, string> = {
  lounge: "Safehouse Lounge",
  station: "Old Station",
  cafe: "Café Nocturne",
};

const prettyId = (value: string) => value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const locationName = (locationId?: string) => locationId ? (locationNames[locationId] ?? prettyId(locationId)) : "Timeline Space";
const sourceName = (source?: string) => source ? prettyId(source) : "Simulation kernel";

function EventRow({ event }: { event: TimelineEvent }) {
  return (
    <li className={`event-row event-${event.kind}`}>
      <time>{event.time}</time>
      <span className="event-dot" aria-hidden="true" />
      <div><strong>{event.title}</strong><p>{event.detail}</p></div>
    </li>
  );
}

function CastPortrait({
  member,
  compact = false,
  active,
}: {
  member: (typeof defaultCast)[number];
  compact?: boolean;
  active?: boolean;
}) {
  const activityClass = active === undefined ? "" : active ? " is-active" : " is-muted";
  return (
    <div className={`cast-portrait has-art${compact ? " cast-portrait-compact" : ""}${activityClass}`} style={{ "--portrait-color": member.color } as CSSProperties}>
      <img
        className="portrait-art"
        src={member.portrait}
        alt={`${member.name}, ${member.role}`}
        onError={(event) => {
          event.currentTarget.hidden = true;
          event.currentTarget.parentElement?.classList.remove("has-art");
        }}
      />
      <span className="portrait-halo" aria-hidden="true" />
      <span className="portrait-head" aria-hidden="true" />
      <span className="portrait-body" aria-hidden="true" />
      <span className="portrait-initial">{member.name.slice(0, 1)}</span>
    </div>
  );
}

function Player({ original, branched, live }: { original: TimelineEvent[]; branched: TimelineEvent[]; live: DemoRun | null }) {
  const [mode, setMode] = useState<ReplayMode>("original");
  const [entry, setEntry] = useState(0);
  const events = mode === "branch" ? branched : original;
  const safeEntry = Math.min(entry, Math.max(0, events.length - 1));
  const event = events[safeEntry] ?? originalTimeline[0]!;
  const actorId = event.speakerId ?? event.characterId ?? event.characterIds?.[0];
  const actor = defaultCast.find((member) => member.id === actorId);
  const activeIds = new Set(
    [event.characterId, event.speakerId, ...(event.characterIds ?? [])].filter((id): id is string => Boolean(id)),
  );
  const aiRun = Boolean(live && "mode" in live.case && live.case.mode === "ai");

  useEffect(() => {
    setMode("original");
    setEntry(0);
  }, [live?.case.manifest_id]);

  const changeMode = (nextMode: ReplayMode) => {
    setMode(nextMode);
    setEntry(0);
  };
  const previous = () => setEntry((current) => Math.max(0, current - 1));
  const next = () => setEntry((current) => current + 1 >= events.length ? 0 : current + 1);

  return (
    <section className="player-layout" aria-label="Visual novel case player">
      <aside className="paper-side left-side">
        <p className="note-label">Location</p>
        <h2>{locationName(event.locationId)}</h2>
        <div className={`polaroid small-scene scene-${event.locationId ?? "timeline"}`} aria-label={`Illustrated ${locationName(event.locationId)} fallback`} />
        <div className="note-card">
          <p className="note-label">Replay track</p>
          <strong>{mode === "original" ? "A · Original" : "B · Branch"}</strong>
          <p>{live ? aiRun ? "● AI manifest run" : "● Mock manifest run" : "○ Preview data"}</p>
        </div>
      </aside>

      <section className={`stage stage-${event.locationId ?? "timeline"}`} aria-live="polite">
        <div className="stage-background"><span className="window-glow" /><span className="bookshelf" /><span className="desk-lamp" /></div>
        <header className="replay-toolbar">
          <div><p className="note-label">{aiRun ? "AI decision replay" : "Authoritative event replay"}</p><strong>{live ? `Seed ${live.case.seed} · ${live.case.manifest_id.slice(0, 8)}` : "Prepared MVP preview"}</strong></div>
          <div className="replay-mode" aria-label="Replay timeline">
            <button type="button" className={mode === "original" ? "active" : ""} aria-pressed={mode === "original"} onClick={() => changeMode("original")}>A · Original</button>
            <button type="button" className={mode === "branch" ? "active" : ""} aria-pressed={mode === "branch"} onClick={() => changeMode("branch")}>B · Branch</button>
          </div>
        </header>
        <div className="stage-cast">
          {defaultCast.slice(0, 3).map((member) => <CastPortrait key={member.id} member={member} active={activeIds.size === 0 ? undefined : activeIds.has(member.id)} />)}
        </div>
        <article className={`dialogue-box dialogue-${event.kind}`}>
          <span className="speaker-tag" style={{ backgroundColor: actor?.color ?? "#76586f" }}>{actor?.name ?? "Timeline"}</span>
          <div className="event-kicker"><time>{event.time}</time><span>{prettyId(event.kind)}</span><span>{sourceName(event.source)}</span></div>
          <p>{event.content ?? event.title}</p>
          <small className="event-detail">{event.detail}</small>
          <div className="dialogue-actions">
            <button type="button" onClick={previous} disabled={safeEntry === 0}>← Back</button>
            <span>{safeEntry + 1} / {events.length}</span>
            <button type="button" onClick={next}>{safeEntry + 1 === events.length ? "Replay ↺" : "Continue →"}</button>
          </div>
        </article>
      </section>

      <aside className="paper-side notes-side">
        <p className="note-label">Event trace</p><h2>{event.title}</h2>
        <ul className="fragment-list trace-list"><li>{event.detail}</li><li>Decision source: {sourceName(event.source)}</li><li>Authority: deterministic Python simulation</li></ul>
        <div className="objective-note"><p className="note-label">Current objective</p><strong>Explain event {safeEntry + 1} of {events.length}.</strong></div>
      </aside>
    </section>
  );
}

function Timeline({ events, label }: { events: TimelineEvent[]; label: string }) {
  return <section className="timeline-card"><header><p className="note-label">{label}</p><h2>{productCopy.caseTitle}</h2></header><ol className="event-list">{events.map((event) => <EventRow key={event.id} event={event} />)}</ol></section>;
}

function Compare({ original, branched, live }: { original: TimelineEvent[]; branched: TimelineEvent[]; live: DemoRun | null }) {
  const differences = live ? [
    `Run manifest: ${live.case.manifest_id.slice(0, 8)} · lobby ${live.case.lobby_code}`,
    `${live.divergence.added_events} added and ${live.divergence.removed_events} removed simulation events.`,
    live.divergence.final_state_changed ? "The final character state diverged." : "The event sequence changed without altering the final state.",
  ] : differenceSummary;
  return <section className="compare-shell"><div className="compare-heading"><p className="eyebrow">Frozen snapshot · {live ? `Seed ${live.case.seed}` : "19:10"}</p><h2>One external change, two explainable timelines.</h2><p>The simulation records source, confidence, timing, route, and encounter effects rather than rewriting private memories.</p></div><div className="compare-grid"><Timeline label="A · Original" events={original} /><Timeline label="B · External delay" events={branched} /></div><aside className="difference-note"><p className="note-label">Divergence notes</p><ul>{differences.map((difference) => <li key={difference}>{difference}</li>)}</ul></aside></section>;
}

function Admin() {
  return <section className="admin-shell"><header className="admin-header"><div><p className="eyebrow">Restricted surface · overview only</p><h2>Admin Console</h2><p>Platform health and moderation signals. Use Integration Lab for live database, object storage, and provider checks.</p></div><span className="system-pill">● System healthy</span></header><div className="admin-grid">{adminSummary.map(([label, value, detail]) => <article className="metric-card" key={label}><p>{label}</p><strong>{value}</strong><small>{detail}</small></article>)}</div></section>;
}

function App() {
  const [view, setView] = useState<View>("player");
  const [liveRun, setLiveRun] = useState<DemoRun | null>(null);
  const [runState, setRunState] = useState<"idle" | "loading" | "error">("idle");
  const original = useMemo(() => liveRun ? timelineFromSimulation(liveRun.original.events, "original") : originalTimeline, [liveRun]);
  const branched = useMemo(() => liveRun ? timelineFromSimulation(liveRun.branched.events, "branch", liveRun.branched.interventions) : branchedTimeline, [liveRun]);

  const runDemo = async () => {
    setRunState("loading");
    try {
      const run = await startDemoRun();
      setLiveRun(run);
      setView("player");
      setRunState("idle");
    } catch {
      setRunState("error");
    }
  };

  let currentView;
  if (view === "lobby") currentView = <LocalLobby onRunComplete={(run) => { setLiveRun(run); setView("player"); }} />;
  else if (view === "timeline") currentView = <Timeline label={liveRun ? "Live simulation timeline" : "Original timeline"} events={original} />;
  else if (view === "compare") currentView = <Compare original={original} branched={branched} live={liveRun} />;
  else if (view === "integrations") currentView = <IntegrationLab />;
  else if (view === "admin") currentView = <Admin />;
  else currentView = <Player original={original} branched={branched} live={liveRun} />;

  const runIdentifier = liveRun ? `${liveRun.case.manifest_id.slice(0, 8)} · Seed ${liveRun.case.seed}` : "PXC-APR14-001 · Preview seed";

  return <main className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top" onClick={(event) => { event.preventDefault(); setView("player"); }}><span>Paradox</span><em>Cast</em><small>AI Timeline Mystery Creator</small></a>
      <nav aria-label="Application sections">{(Object.keys(viewLabels) as View[]).map((item) => <button key={item} type="button" className={view === item ? "active" : ""} onClick={() => setView(item)}>{viewLabels[item]}</button>)}</nav>
      <button className="publish-button" type="button" onClick={runDemo} disabled={runState === "loading"}>{runState === "loading" ? "Starting…" : liveRun ? "Run mock again" : "Run mock demo"} <span>↗</span></button>
    </header>
    <section className="case-ribbon"><p><span>Case file</span>{productCopy.caseTitle}</p><div className="timeline-pips" aria-label="Current point in the timeline"><i /><i /><i className="current" /><i /><i /></div><p className="run-id">{runIdentifier}</p></section>
    {currentView}
    {runState === "error" && <p className="run-error">Could not reach the FastAPI server. Start the backend, then try the mock demo again.</p>}
    <footer className="app-footer"><span>AI chooses legal intentions · Python remains authoritative</span><span>Local integration stack ready</span></footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<App />);
