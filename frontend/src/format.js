export const pct = (ratio, digits = 2) =>
  ratio === null || ratio === undefined ? "—" : `${(ratio * 100).toFixed(digits)}%`;

export const burnLevel = (rate) => {
  if (rate === null || rate === undefined) return "none";
  if (rate >= 14.4) return "critical"; // would exhaust a 30-day budget in ~2 days
  if (rate >= 1) return "warning"; // spending faster than the SLO allows
  return "ok";
};

export function duration(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 600) return `${(seconds / 60).toFixed(1)}m`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

export function ago(iso) {
  if (!iso) return "never";
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  return seconds < 5 ? "just now" : `${duration(seconds)} ago`;
}
