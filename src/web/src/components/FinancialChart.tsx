import type { FinancialPoint } from '../types';

type Props = { data: FinancialPoint[] };

export function FinancialChart({ data }: Props) {
  const width = 720;
  const height = 260;
  const plot = { left: 58, right: 662, top: 28, bottom: 208 };
  const maxRevenue = Math.max(...data.map((point) => point.revenue), 100);
  const profitMin = Math.min(...data.map((point) => point.profit), -10);
  const profitMax = Math.max(...data.map((point) => point.profit), 15);
  const slot = (plot.right - plot.left) / data.length;
  const revenueY = (value: number) => plot.bottom - (value / maxRevenue) * (plot.bottom - plot.top);
  const profitY = (value: number) => plot.bottom - ((value - profitMin) / (profitMax - profitMin)) * (plot.bottom - plot.top);
  const profitPath = data.map((point, index) => `${index === 0 ? 'M' : 'L'} ${plot.left + slot * index + slot / 2} ${profitY(point.profit)}`).join(' ');
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <figure className="chart" aria-label="Динамика выручки и чистой прибыли по годам">
      <figcaption className="chart__caption">
        <span><i className="chart__legend chart__legend--bar" />Выручка, млн ₽</span>
        <span><i className="chart__legend chart__legend--line" />Чистая прибыль, млн ₽</span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="chart-title chart-desc">
        <title id="chart-title">Финансовая динамика</title>
        <desc id="chart-desc">Столбцы показывают выручку, линия — чистую прибыль. Для прибыли показана нулевая линия.</desc>
        {ticks.map((tick) => {
          const y = plot.bottom - tick * (plot.bottom - plot.top);
          return (
            <g key={tick}>
              <line x1={plot.left} y1={y} x2={plot.right} y2={y} className="chart__grid" />
              <text x={plot.left - 12} y={y + 4} textAnchor="end" className="chart__label">{Math.round(maxRevenue * tick)}</text>
            </g>
          );
        })}
        <line x1={plot.left} y1={profitY(0)} x2={plot.right} y2={profitY(0)} className="chart__zero" />
        <text x={plot.right + 10} y={profitY(0) + 4} className="chart__label">0</text>
        {data.map((point, index) => {
          const center = plot.left + slot * index + slot / 2;
          const top = revenueY(point.revenue);
          return (
            <g key={point.year}>
              <rect x={center - 28} y={top} width={56} height={plot.bottom - top} rx={7} className="chart__bar" />
              <text x={center} y={top - 8} textAnchor="middle" className="chart__value">{point.revenue}</text>
              <text x={center} y={236} textAnchor="middle" className="chart__year">{point.year}</text>
            </g>
          );
        })}
        <path d={profitPath} className="chart__path" />
        {data.map((point, index) => {
          const x = plot.left + slot * index + slot / 2;
          const y = profitY(point.profit);
          return (
            <g key={`profit-${point.year}`}>
              <circle cx={x} cy={y} r={5} className="chart__dot" />
              <text x={x + 10} y={y - 9} className="chart__profit-value">{point.profit > 0 ? '+' : ''}{point.profit}</text>
            </g>
          );
        })}
        <text x={plot.left} y={18} className="chart__axis-title">млн ₽</text>
        <text x={plot.right + 10} y={18} className="chart__axis-title">прибыль</text>
      </svg>
    </figure>
  );
}
