// One bar per bucket of the window; height and colour show uptime in that bucket.
export default function Sparkline({ points, target }) {
  const width = 240;
  const height = 36;
  const gap = 2;
  const barWidth = points.length ? (width - gap * (points.length - 1)) / points.length : 0;
  const floor = Math.min(target / 100 - 0.01, 0.9); // zoom in on the interesting range

  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Uptime over the window">
      {points.map((point, i) => {
        const x = i * (barWidth + gap);
        if (point === null) {
          return <rect key={i} x={x} y={height - 3} width={barWidth} height={3} rx={1} className="bar-empty" />;
        }
        const scaled = Math.max(0, (point - floor) / (1 - floor));
        const barHeight = Math.max(3, scaled * height);
        const tone = point * 100 >= target ? "bar-good" : point >= floor ? "bar-warn" : "bar-bad";
        return <rect key={i} x={x} y={height - barHeight} width={barWidth} height={barHeight} rx={1} className={tone} />;
      })}
    </svg>
  );
}
