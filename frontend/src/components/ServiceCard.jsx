import Sparkline from "./Sparkline.jsx";
import { ago, burnLevel, duration, pct } from "../format.js";

export default function ServiceCard({ service, report, hasToken, onBeat, onDelete, busy }) {
  const status = report?.status ?? service.status;
  const remaining = report?.budget_remaining_ratio;
  const budgetWidth = remaining === null || remaining === undefined ? 0 : Math.max(0, Math.min(1, remaining)) * 100;
  const level = burnLevel(report?.burn_rate);

  return (
    <article className={`card status-${status}`}>
      <header className="card-head">
        <div>
          <h3>{service.name}</h3>
          <code className="slug">{service.slug}</code>
        </div>
        <span className={`pill pill-${status}`}>{status}</span>
      </header>

      <div className="metrics">
        <div>
          <span className="label">Uptime</span>
          <strong className="big">{pct(report?.uptime, 3)}</strong>
        </div>
        <div>
          <span className="label">SLO</span>
          <strong>{service.slo_target}%</strong>
        </div>
        <div>
          <span className="label">Burn rate</span>
          <strong className={`burn burn-${level}`}>
            {report?.burn_rate === null || report?.burn_rate === undefined ? "—" : `${report.burn_rate.toFixed(2)}×`}
          </strong>
        </div>
      </div>

      <div className="budget">
        <div className="budget-label">
          <span>Error budget left</span>
          {remaining !== null && remaining !== undefined && remaining < 0 ? (
            <span className="exhausted">exhausted</span>
          ) : (
            <span>
              {pct(remaining, 1)}
              {report ? ` of ${duration(report.allowed_downtime_s)}` : ""}
            </span>
          )}
        </div>
        <div className="budget-track">
          <div className={`budget-fill ${remaining !== null && remaining < 0.25 ? "low" : ""}`} style={{ width: `${budgetWidth}%` }} />
        </div>
      </div>

      {report && <Sparkline points={report.sparkline} target={service.slo_target} />}

      <footer className="card-foot">
        <span>
          every {duration(service.heartbeat_interval_s)} · last beat {ago(service.last_beat_at)}
        </span>
        <span className="actions">
          {hasToken && (
            <>
              <button className="ghost" disabled={busy} onClick={() => onBeat("ok")}>beat</button>
              <button className="ghost warn" disabled={busy} onClick={() => onBeat("fail")}>fail</button>
            </>
          )}
          <button className="ghost danger" disabled={busy} onClick={onDelete} title="Delete service">✕</button>
        </span>
      </footer>
    </article>
  );
}
