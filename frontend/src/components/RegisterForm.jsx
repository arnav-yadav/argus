import { useState } from "react";

const blank = { name: "", heartbeat_interval_s: 30, slo_target: 99.5 };

export default function RegisterForm({ onRegister }) {
  const [form, setForm] = useState(blank);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const service = await onRegister({
        name: form.name.trim(),
        heartbeat_interval_s: Number(form.heartbeat_interval_s),
        slo_target: Number(form.slo_target),
      });
      setCreated(service);
      setForm(blank);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const curl = created
    ? `curl -X POST ${window.location.origin}/api/services/${created.id}/heartbeat \\\n  -H "X-Argus-Token: ${created.ingest_token}" \\\n  -H "Content-Type: application/json" -d '{"status":"ok"}'`
    : "";

  return (
    <section className="panel">
      <h2>Register a service</h2>
      <form onSubmit={submit} className="register">
        <label>
          Name
          <input required minLength={2} maxLength={80} value={form.name} onChange={update("name")} placeholder="Checkout API" />
        </label>
        <label>
          Heartbeat every (s)
          <input type="number" min={5} max={3600} value={form.heartbeat_interval_s} onChange={update("heartbeat_interval_s")} />
        </label>
        <label>
          SLO target (%)
          <input type="number" min={50} max={99.999} step="0.001" value={form.slo_target} onChange={update("slo_target")} />
        </label>
        <button type="submit" disabled={saving}>{saving ? "Registering…" : "Register"}</button>
      </form>
      {error && <p className="error">{error}</p>}
      {created && (
        <div className="token-box">
          <p>
            <strong>{created.name}</strong> registered. Its ingest token is shown only once, and this
            browser keeps a copy so the card's buttons work.
          </p>
          <pre>{curl}</pre>
          <button className="ghost" onClick={() => setCreated(null)}>Dismiss</button>
        </div>
      )}
    </section>
  );
}
