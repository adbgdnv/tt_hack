import { Chart } from '@alfalab/core-components-chart';

import type { ChartSpec } from '../types';

/**
 * Описание графика → разметка.
 *
 * Форм ровно две, и рисуются они по-разному не из вкуса, а по смыслу:
 *
 * - `bars` — две величины рядом (истец/ответчик, капитал/обязательства,
 *   активные/завершённые). Горизонтальные полосы с числом на каждой читаются
 *   без осей и наведения мышью и не ломаются в узкой карточке. Раньше через
 *   библиотеку шли все, кроме «В какой роли судится», — столбиковая диаграмма
 *   ради двух значений давала оси, сетку и легенду вокруг двух чисел.
 * - `lines` — ряд по годам, две серии, максимум четыре года. В детальном виде
 *   это компонент дизайн-системы, в карточке — свои столбики: библиотека внутри
 *   кнопки вешает свои обработчики мыши и стоит куда дороже восьми прямоугольников.
 *
 * `compact` — вид для карточки раздела: без источника и с мелкой типографикой.
 * Числа остаются в обоих видах: на печати наведения мышью нет, и график без
 * подписей превращается в картинку без данных.
 */

const PALETTE = ['#64788a', '#9a7761', '#8c8f95', '#708775'];

/**
 * Строка, которую честно окрасить тревожным цветом: она означает произошедшее
 * событие, а не долю в составе величины. У «Чем обеспечены активы» такой строки
 * нет — обязательства это устройство баланса, а не происшествие.
 */
const ACCENT_ROW: Record<string, number> = {
  plaintiff_defendant: 1, // «Как ответчик»
  proceedings: 0, // «Активные»
};

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

function Values({ spec }: { spec: ChartSpec }) {
  return (
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
  );
}

/**
 * Две величины рядом. Масштаб берётся по модулю: собственный капитал бывает
 * отрицательным — у 11 компаний из 200, — и это ровно тот случай, ради которого
 * на график и смотрят. Полоса нулевой длины выдала бы его за отсутствие данных.
 */
function Bars({ spec }: { spec: ChartSpec }) {
  const series = spec.series[0];
  if (!series) return null;

  const unit = series.unit;
  const values = series.values;
  const max = Math.max(...values.map((v) => Math.abs(v ?? 0)), 1);
  const accent = ACCENT_ROW[spec.key];

  return (
    <div className="role-chart">
      {spec.labels.map((label, index) => {
        const value = values[index] ?? 0;
        // Ноль не бывает тревожным: «Как ответчик — 0 ₽» это отсутствие события,
        // а не событие. Красным его красить значит пугать пустотой.
        const alarming = value < 0 || (index === accent && value > 0);
        const tone = alarming ? ' role-chart__row--accent' : '';
        return (
          <div className={`role-chart__row${tone}`} key={label}>
            <div>
              <span>{label}</span>
              <strong>{full(value, unit)}</strong>
            </div>
            <span className="role-chart__track" aria-hidden="true">
              <span
                style={{
                  width: `${Math.max((Math.abs(value) / max) * 100, value !== 0 ? 3 : 0)}%`,
                }}
              />
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Ряд по годам в карточке: сгруппированные столбики без осей и библиотеки. */
function MiniColumns({ spec }: { spec: ChartSpec }) {
  const numbers = spec.series.flatMap((s) =>
    s.values.filter((v): v is number => v !== null).map(Math.abs),
  );
  const max = Math.max(...numbers, 1);

  return (
    <div className="mini-columns" aria-hidden="true">
      {spec.labels.map((label, index) => (
        <div className="mini-columns__group" key={label}>
          <div className="mini-columns__bars">
            {spec.series.map((s, si) => {
              const value = s.values[index];
              return (
                <span
                  key={s.name}
                  className="mini-columns__bar"
                  style={{
                    // null — год без данных, а не ноль: столбика просто нет.
                    height: value === null ? 0 : `${Math.max((Math.abs(value) / max) * 100, 4)}%`,
                    background: PALETTE[si % PALETTE.length],
                  }}
                />
              );
            })}
          </div>
          <span className="mini-columns__label">{label}</span>
        </div>
      ))}
    </div>
  );
}

export function ReportChart({ spec, compact = false }: { spec: ChartSpec; compact?: boolean }) {
  const unit = spec.series[0]?.unit ?? '';

  const body =
    spec.form === 'bars' ? (
      <Bars spec={spec} />
    ) : compact ? (
      <MiniColumns spec={spec} />
    ) : (
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
          series={spec.series.map((s, index) => ({
            chart: 'line' as const,
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
          }))}
          labels={spec.labels}
        />
      </div>
    );

  return (
    <figure
      className={`report-chart report-chart--${spec.form}${compact ? ' report-chart--compact' : ''}`}
      aria-label={spec.title}
    >
      <figcaption className="report-chart__title">{spec.title}</figcaption>
      {body}
      {/* Столбики скрыты от чтения с экрана — числа несёт этот список.
          Для горизонтальных полос число уже стоит на самой полосе. */}
      {spec.form === 'lines' && <Values spec={spec} />}
      {!compact && <p className="report-chart__source">Источник: {spec.source}</p>}
    </figure>
  );
}
