import { burnLevel } from "../format.js";

export default function FleetSummary({ fleet }) {
  if (!fleet) return null;
  const stats = [
    { label: "Services", value: fleet.services },
    { label: "Meeting SLO", value: fleet.meeting_slo, tone: "good" },
    { label: "Breaching", value: fleet.breaching_slo, tone: fleet.breaching_slo ? "bad" : "" },
    { label: "No data", value: fleet.no_data },
    {
      label: "Worst burn",
      value: fleet.worst_burn_rate === null ? "—" : `${fleet.worst_burn_rate.toFixed(1)}×`,
      tone: { critical: "bad", warning: "warn", ok: "good" }[burnLevel(fleet.worst_burn_rate)] || "",
    },
  ];
  return (
    <section className="fleet">
      {stats.map((s) => (
        <div key={s.label} className={`stat ${s.tone || ""}`}>
          <span className="label">{s.label}</span>
          <strong>{s.value}</strong>
        </div>
      ))}
    </section>
  );
}
