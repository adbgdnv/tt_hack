import { Chart } from '@alfalab/core-components-chart';

import type { ChartSpec } from '../types';

/**
 * Описание графика → пропсы компонента дизайн-системы.
 *
 * Компонент многословен: у каждой серии обязательны `icon`, `offset`, `gradient`
 * и `properties`. Весь этот перевод живёт здесь одним местом, чтобы каждый график
 * не собирал его заново.
 */

const PALETTE = ['#64788a', '#9a7761', '#8c8f95', '#708775'];

/** Крупные суммы нечитаемы целиком: 279 815 832 000 ₽ на оси не помещается. */
function short(value: number, unit: string): string {
  const abs = Math.abs(value);
  if (unit !== '₽') return String(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(1)} млрд`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)} млн`;
  if (abs >= 1e3) return `${Math.round(value / 1e3)} тыс`;
  return String(Math.round(value));
}

function full(value: number, unit: string): string {
  const formatted = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value);
  return unit ? `${formatted} ${unit}` : formatted;
}

export function ReportChart({ spec }: { spec: ChartSpec }) {
  const unit = spec.series[0]?.unit ?? '';

  if (spec.key === 'plaintiff_defendant' && spec.series[0]) {
    const values = spec.series[0].values;
    const max = Math.max(...values.map((value) => value ?? 0), 1);
    return (
      <figure className="report-chart report-chart--roles" aria-label={spec.title}>
        <figcaption className="report-chart__title">{spec.title}</figcaption>
        <div className="role-chart">
          {spec.labels.map((label, index) => {
            const value = values[index] ?? 0;
            return (
              <div className="role-chart__row" key={label}>
                <div><span>{label}</span><strong>{full(value, unit)}</strong></div>
                <span className="role-chart__track" aria-hidden="true">
                  <span style={{ width: `${Math.max((value / max) * 100, value > 0 ? 3 : 0)}%` }} />
                </span>
              </div>
            );
          })}
        </div>
        <p className="report-chart__source">Источник: {spec.source}</p>
      </figure>
    );
  }

  const series = spec.series.map((s, index) => ({
    chart: (spec.form === 'lines' ? 'line' : 'bar') as 'line' | 'bar',
    icon: 'filledCircle' as const,
    offset: 0,
    fill: PALETTE[index % PALETTE.length],
    gradient: { gid: `${spec.key}-${index}`, points: [] },
    properties: {
      name: s.name,
      dataKey: 'value',
      stroke: PALETTE[index % PALETTE.length],
      fill: PALETTE[index % PALETTE.length],
      strokeWidth: 2,
    },
    // null остаётся null: год без данных — не ноль, и линия должна прерваться
    data: s.values.map((value, i) => ({ label: spec.labels[i], value: value as number })),
  }));

  return (
    <figure className={`report-chart report-chart--${spec.form}`} aria-label={spec.title}>
      <figcaption className="report-chart__title">{spec.title}</figcaption>
      <div className="report-chart__canvas">
        <Chart
          id={`chart-${spec.key}`}
          composeChart={{ margin: { top: 8, right: 8, left: 8, bottom: 0 } }}
          xAxis={{ dataKey: 'label', axisLine: false, type: 'category' }}
          yAxis={{
            axisLine: false,
            type: 'number',
            tickFormatter: (value: number) => short(value, unit),
          }}
          legend={spec.series.length > 1 ? { align: 'left', verticalAlign: 'bottom' } : undefined}
          series={series}
          labels={spec.labels}
        />
      </div>
      {/* Значения текстом: на печати нет наведения мышью, и график без них
          превращается в картинку без чисел. */}
      <dl className="report-chart__values">
        {spec.series.map((s) => (
          <div key={s.name}>
            <dt>{s.name}</dt>
            <dd>
              {s.values
                .map((v, i) => (v === null ? null : `${spec.labels[i]}: ${short(v, s.unit)}`))
                .filter(Boolean)
                .join(' · ')}
            </dd>
          </div>
        ))}
      </dl>
      <p className="report-chart__source">Источник: {spec.source}</p>
    </figure>
  );
}
