import { useCallback, useEffect, useState } from "react";
import { api, tokens } from "./api.js";
import FleetSummary from "./components/FleetSummary.jsx";
import RegisterForm from "./components/RegisterForm.jsx";
import ServiceCard from "./components/ServiceCard.jsx";

const WINDOWS = ["1h", "24h", "7d"];
const REFRESH_MS = 5000;
const VERSION = import.meta.env.VITE_APP_VERSION || "dev"; // "sha-<40 hex>" from CI
const COMMIT = VERSION.startsWith("sha-") ? VERSION.slice(4) : null;

function initialRange() {
  const fromUrl = new URLSearchParams(window.location.search).get("window");
  return WINDOWS.includes(fromUrl) ? fromUrl : "24h";
}

export default function App() {
  const [range, setRange] = useState(initialRange);
  const [services, setServices] = useState([]);
  const [reports, setReports] = useState({});
  const [fleet, setFleet] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [list, summary] = await Promise.all([api.services(), api.fleet(range)]);
      const uptimes = await Promise.all(list.map((s) => api.uptime(s.id, range).catch(() => null)));
      setServices(list);
      setFleet(summary);
      setReports(Object.fromEntries(list.map((s, i) => [s.id, uptimes[i]])));
      setError("");
    } catch (err) {
      setError(`Cannot reach the Argus API (${err.message}).`);
    } finally {
      setLoaded(true);
    }
  }, [range]);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("window", range);
    window.history.replaceState(null, "", url);
  }, [range]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  async function register(body) {
    const created = await api.register(body);
    tokens.set(created.id, created.ingest_token);
    await refresh();
    return created;
  }

  async function act(id, action) {
    setBusy(id);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <ellipse cx="16" cy="16" rx="13" ry="8" fill="none" stroke="currentColor" strokeWidth="2.5" />
            <circle cx="16" cy="16" r="4" fill="currentColor" />
          </svg>
          <div>
            <h1>Argus</h1>
            <p className="tagline">Every service watched. Every error budget accounted for. Every deploy traced to a commit.</p>
          </div>
        </div>
        <nav className="windows" aria-label="Reporting window">
          {WINDOWS.map((w) => (
            <button key={w} className={w === range ? "active" : ""} onClick={() => setRange(w)}>
              {w}
            </button>
          ))}
        </nav>
      </header>

      {error && <div className="banner">{error}</div>}
      <FleetSummary fleet={fleet} />

      <main>
        {loaded && services.length === 0 && !error && (
          <p className="empty">No services yet. Register one below, or start the simulator.</p>
        )}
        <div className="grid">
          {services.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              report={reports[service.id]}
              hasToken={Boolean(tokens.get(service.id))}
              busy={busy === service.id}
              onBeat={(status) => act(service.id, () => api.beat(service.id, tokens.get(service.id), status))}
              onDelete={() =>
                act(service.id, async () => {
                  await api.remove(service.id);
                  tokens.forget(service.id);
                })
              }
            />
          ))}
        </div>
        <RegisterForm onRegister={register} />
      </main>

      <footer className="foot">
        Argus · build{" "}
        {COMMIT ? (
          <a href={`https://github.com/arnav-yadav/argus/commit/${COMMIT}`}>
            <code>sha-{COMMIT.slice(0, 7)}</code>
          </a>
        ) : (
          <code>{VERSION}</code>
        )}{" "}
        · refreshes every {REFRESH_MS / 1000}s
      </footer>
    </div>
  );
}
