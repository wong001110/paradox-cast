import { createRoot } from "react-dom/client";
import { useMemo, useState, type CSSProperties } from "react";
import "./styles.css";
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

type View = "player" | "lobby" | "timeline" | "compare" | "admin";

const viewLabels: Record<View, string> = {
  player: "Case player",
  lobby: "Lobby",
  timeline: "Timeline",
  compare: "A/B compare",
  admin: "Admin overview",
};

function EventRow({ event }: { event: TimelineEvent }) {
  return (
    <li className={`event-row event-${event.kind}`}>
      <time>{event.time}</time>
      <span className="event-dot" aria-hidden="true" />
      <div>
        <strong>{event.title}</strong>
        <p>{event.detail}</p>
      </div>
    </li>
  );
}

function CastPortrait({ member, compact = false }: { member: (typeof defaultCast)[number]; compact?: boolean }) {
  return (
    <div className={`cast-portrait ${compact ? "cast-portrait-compact" : ""}`} style={{ "--portrait-color": member.color } as CSSProperties}>
      <span className="portrait-halo" aria-hidden="true" />
      <span className="portrait-head" aria-hidden="true" />
      <span className="portrait-body" aria-hidden="true" />
      <span className="portrait-initial">{member.name.slice(0, 1)}</span>
    </div>
  );
}

function Player({ events }: { events: TimelineEvent[] }) {
  const [entry, setEntry] = useState(0);
  const event = events[entry]!;
  const speaker = entry === 3 ? defaultCast[1] : defaultCast[0];
  const next = () => setEntry((current) => (current + 1) % events.length);

  return (
    <section className="player-layout" aria-label="Visual novel case player">
      <aside className="paper-side left-side">
        <p className="note-label">Location</p>
        <h2>Safehouse Lounge</h2>
        <div className="polaroid small-scene" aria-label="Illustrated night lounge fallback" />
        <div className="note-card">
          <p className="note-label">Today’s mood</p>
          <strong>Curious</strong>
          <p>○ ○ ○</p>
        </div>
      </aside>
      <section className="stage" aria-live="polite">
        <div className="stage-background">
          <span className="window-glow" />
          <span className="bookshelf" />
          <span className="desk-lamp" />
        </div>
        <div className="stage-cast">
          {defaultCast.slice(0, 3).map((member) => <CastPortrait key={member.id} member={member} />)}
        </div>
        <article className="dialogue-box">
          <span className="speaker-tag" style={{ backgroundColor: speaker.color }}>{speaker.name}</span>
          <p>{event.kind === "dialogue" ? "If this photo was taken five years ago, why does the train ticket say yesterday?" : event.title}</p>
          <button type="button" onClick={next}>Continue <span aria-hidden="true">→</span></button>
        </article>
      </section>
      <aside className="paper-side notes-side">
        <p className="note-label">Investigation notes</p>
        <h2>Key fragments</h2>
        <ul className="fragment-list">
          <li>Old photo</li><li>Train ticket</li><li>Coffee receipt</li><li>Handwritten note</li>
        </ul>
        <div className="objective-note"><p className="note-label">Current objective</p><strong>Trace the missing hour.</strong></div>
      </aside>
    </section>
  );
}

function Timeline({ events, label }: { events: TimelineEvent[]; label: string }) {
  return <section className="timeline-card"><header><p className="note-label">{label}</p><h2>{productCopy.caseTitle}</h2></header><ol className="event-list">{events.map((event) => <EventRow key={event.id} event={event} />)}</ol></section>;
}

function Lobby({ onStart, loading, live }: { onStart: () => Promise<void>; loading: boolean; live: DemoRun | null }) {
  const cast = defaultCast.slice(0, 3);
  const [ready, setReady] = useState<Record<string, boolean>>({ hana: true, rei: true, mira: true });
  const allReady = cast.every((member) => ready[member.id]);

  return <section className="lobby-shell" aria-label="Online lobby">
    <header className="lobby-heading">
      <div><p className="eyebrow">Online lobby · Host / Director</p><h2>{productCopy.caseTitle}</h2><p>Choose the cast, bind an approved runtime, and lock one explainable timeline.</p></div>
      <aside className="join-code"><p className="note-label">Join code</p><strong>{live?.case.lobby_code ?? "PXC·14TH"}</strong><span>{live ? "Latest run created" : "Unlisted demo lobby"}</span></aside>
    </header>
    <div className="lobby-meta"><span>Scenario: The Vanishing of April 14th</span><span>Visibility: Unlisted</span><span>Runtime funding: Host-funded</span><span>Participants: 3 / 4</span></div>
    <div className="lobby-cast">
      {cast.map((member, index) => <article className="lobby-card" key={member.id}>
        <span className="slot-number">{index + 1}</span><CastPortrait member={member} compact />
        <div><p className="note-label">{index === 0 ? "Host · Director" : "Participant"}</p><h3>{member.name}</h3><p>{member.role}</p><label className="runtime-select">AI runtime<select aria-label={`${member.name} runtime`} defaultValue="host"><option value="host">Mock Detective · Host funded</option><option value="byo">Personal runtime · BYO grant</option></select></label></div>
        <button className={`ready-toggle ${ready[member.id] ? "is-ready" : ""}`} type="button" onClick={() => setReady((current) => ({ ...current, [member.id]: !current[member.id] }))}>{ready[member.id] ? "✓ Ready" : "Mark ready"}</button>
      </article>)}
      <article className="empty-slot"><span>4</span><strong>Open cast slot</strong><p>Invite a participant or keep this role in the deterministic demo cast.</p></article>
    </div>
    <footer className="lobby-footer"><div><p className="note-label">Run manifest</p><strong>{allReady ? "Ready to freeze scenario, cast, runtimes, seed and asset versions." : "Every selected participant must be ready before the manifest can lock."}</strong></div><button className="start-run" type="button" disabled={!allReady || loading} onClick={onStart}>{loading ? "Locking manifest…" : "Start run →"}</button></footer>
  </section>;
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
  return <section className="admin-shell"><header className="admin-header"><div><p className="eyebrow">Restricted surface · overview only</p><h2>Admin Console</h2><p>Platform health and moderation signals. Private scenarios and character content are not displayed by default.</p></div><span className="system-pill">● System healthy</span></header><div className="admin-grid">{adminSummary.map(([label, value, detail]) => <article className="metric-card" key={label}><p>{label}</p><strong>{value}</strong><small>{detail}</small></article>)}</div><div className="admin-lists"><article className="admin-panel"><h3>Recent audit events</h3><ul><li><b>Run manifest locked</b><span>PXC-APR14-001 · 19:09</span></li><li><b>Public card flagged for review</b><span>Visibility unchanged · 18:46</span></li><li><b>Mock runtime fallback used</b><span>No credential value logged · 18:32</span></li></ul></article><article className="admin-panel"><h3>Moderation queue</h3><p>No private content is listed here. Review requires an explicit, audited moderation action.</p><button type="button">Open public-content queue</button></article></div></section>;
}

function App() {
  const [view, setView] = useState<View>("player");
  const [liveRun, setLiveRun] = useState<DemoRun | null>(null);
  const [runState, setRunState] = useState<"idle" | "loading" | "error">("idle");
  const original = liveRun ? timelineFromSimulation(liveRun.original.events, "original") : originalTimeline;
  const branched = liveRun ? timelineFromSimulation(liveRun.branched.events, "branch") : branchedTimeline;
  const runDemo = async () => {
    setRunState("loading");
    try { setLiveRun(await startDemoRun()); setView("compare"); setRunState("idle"); }
    catch { setRunState("error"); }
  };
  const currentView = useMemo(() => {
    if (view === "lobby") return <Lobby onStart={runDemo} loading={runState === "loading"} live={liveRun} />;
    if (view === "timeline") return <Timeline label={liveRun ? "Live simulation timeline" : "Original timeline"} events={original} />;
    if (view === "compare") return <Compare original={original} branched={branched} live={liveRun} />;
    if (view === "admin") return <Admin />;
    return <Player events={original} />;
  }, [view, original, branched, liveRun, runState]);

  return <main className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top" onClick={(event) => { event.preventDefault(); setView("player"); }}><span>Paradox</span><em>Cast</em><small>AI Timeline Mystery Creator</small></a>
      <nav aria-label="Application sections">{(Object.keys(viewLabels) as View[]).map((item) => <button key={item} type="button" className={view === item ? "active" : ""} onClick={() => setView(item)}>{viewLabels[item]}</button>)}</nav>
      <button className="publish-button" type="button" onClick={runDemo} disabled={runState === "loading"}>{runState === "loading" ? "Starting…" : "Run demo case"} <span>↗</span></button>
    </header>
    <section className="case-ribbon"><p><span>Case file</span>{productCopy.caseTitle}</p><div className="timeline-pips" aria-label="Current point in the timeline"><i /><i /><i className="current" /><i /><i /></div><p className="run-id">PXC-APR14-001 · Seed locked</p></section>
    {currentView}
    {runState === "error" && <p className="run-error">Could not reach the FastAPI server. Start the backend, then try the demo again.</p>}
    <footer className="app-footer"><span>Visual-novel presentation · Python simulation stays authoritative</span><span>Official MVP scrapbook theme</span></footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<App />);
