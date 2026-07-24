import { createRoot } from "react-dom/client";
import "./styles.css";
import { productCopy } from "./content";

function App() {
  return (
    <main className="app-shell">
      <section className="masthead">
        <p className="eyebrow">An AI Timeline Mystery Creator</p>
        <h1>Paradox <em>Cast</em></h1>
        <p>{productCopy.tagline}</p>
      </section>
      <section className="paper-card">
        <h2>Project foundation is ready</h2>
        <p>{productCopy.foundation}</p>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
