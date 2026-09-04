import { Chart } from '@alfalab/core-components-chart';

import type { ChartSpec } from '../types';

/**
 * Описание графика → компонент дизайн-системы.
 *
 * Рисует всё `@alfalab/core-components-chart`: и ряд по годам, и сравнение двух
 * величин, и в карточке раздела, и в детальном виде. Своей отрисовки здесь нет.
 *
 * **Ключ серии обязан быть уникальным.** Компонент склеивает серии в одну таблицу
 * по `properties.dataKey` (см. `hooks/useSettings/utils/setDatas`), и две серии
 * с общим ключом затирают друг друга. Так и было: «Выручка и активы по годам»
 * рисовал одну линию вместо двух, причём по шкале активов — выручка молча
 * пропадала, а подпись оставалась.
 *
 * `compact` — вид для карточки раздела: ниже, без оси значений и без источника.
 * Числа остаются в обоих видах: на печати наведения мышью нет, и график без
 * подписей превращается в картинку без данных.
 */

// Цвета заливки задаются числом, а не токеном: recharts кладёт их в атрибут
// `fill`, а `var(--negative)` в атрибуте презентации не работает — только
// в свойстве CSS. Значения соответствуют токенам темы.
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

type Seria = Parameters<typeof Chart>[0]['series'][number];

/**
 * Подпись деления оси — короче числа в списке под графиком.
 *
 * На оси важен порядок величины, точное значение стоит строкой ниже. «750.0 млн»
 * не помещалось в отведённую компонентом ширину и переносилось на две строки,
 * а верхнее деление вдобавок обрезалось сверху.
 */
function axisTick(value: number, unit: string): string {
  const abs = Math.abs(value);
  if (unit !== '₽') return String(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(1)} млрд`;
  if (abs >= 1e6) return `${Math.round(value / 1e6)} млн`;
  if (abs >= 1e3) return `${Math.round(value / 1e3)} тыс`;
  return String(Math.round(value));
}

function seria(
  name: string,
  key: string,
  fill: string,
  kind: 'bar' | 'line',
  unit: string,
  data: Seria['data'],
): Seria {
  return {
    chart: kind,
    icon: 'filledCircle',
    offset: 0,
    fill,
    radius: kind === 'bar' ? { top: 4, bottom: 0 } : undefined,
    gradient: { gid: key, points: [] },
    properties: {
      name,
      dataKey: key,
      stroke: fill,
      fill,
      strokeWidth: 2,
      // Без форматтера подсказка показывает «52596000» — число, которое
      // читают по разрядам вручную и ошибаются на порядок.
      formatter: (value: number) => short(value, unit),
    },
    data,
  };
}

/**
 * Сравнение двух величин — одной серией на весь график.
 *
 * Серия на столбец дала бы каждому свой цвет, но компонент отводит каждой серии
 * собственный слот внутри категории: столбцы уезжали из-под своих подписей,
 * а у пары «есть значение / ноль» единственный столбец вставал между делениями.
 * Подпись под столбцом важнее оттенка — на сигнальном разделе и без того
 * красные рамка и бейдж.
 */
function barSeries(spec: ChartSpec): Seria[] {
  const source = spec.series[0];
  if (!source) return [];

  return [
    seria(
      source.name,
      'value',
      PALETTE[0],
      'bar',
      source.unit,
      spec.labels.map((label, index) => ({ label, value: source.values[index] ?? 0 })),
    ),
  ];
}

/** Ряд по годам: серия на показатель, ключ на серию. */
function lineSeries(spec: ChartSpec): Seria[] {
  return spec.series.map((s, index) =>
    seria(
      s.name,
      `v${index}`,
      PALETTE[index % PALETTE.length],
      'line',
      s.unit,
      // null — год без данных, а не ноль: точка пропускается, линия рвётся.
      s.values
        .map((value, i) => ({ label: spec.labels[i], value: value as number }))
        .filter((point) => point.value !== null),
    ),
  );
}

export function ReportChart({ spec, compact = false }: { spec: ChartSpec; compact?: boolean }) {
  const bars = spec.form === 'bars';
  const unit = spec.series[0]?.unit ?? '';
  const series = bars ? barSeries(spec) : lineSeries(spec);

  return (
    <figure
      className={`report-chart report-chart--${spec.form}${compact ? ' report-chart--compact' : ''}`}
      aria-label={spec.title}
    >
      <figcaption className="report-chart__title">{spec.title}</figcaption>
      <div className="report-chart__canvas">
        <Chart
          id={`chart-${spec.key}${compact ? '-compact' : ''}`}
          // Поля задаются через `initMargin`, а не `margin`: компонент считает
          // `margin` сам из `initMargin` (см. `setComposedChartsMargin`) и наши
          // значения молча выбрасывал. Из-за этого крайние подписи упирались
          // в границу полотна: «2023» превращался в «23», «2025» в «20».
          // Замерено: подпись года выходит за край на 19 пикселей.
          composeChart={{
            initMargin: { top: 12, right: 24, left: compact ? 24 : 8, bottom: 0 },
            maxBarSize: 64,
          }}
          // interval 0 — иначе компонент прореживает подписи и год молча пропадает:
          // на «Выручке и активах» с экрана исчезал 2023-й.
          xAxis={{ dataKey: 'label', axisLine: false, tickLine: false, type: 'category', interval: 0 }}
          yAxis={{
            axisLine: false,
            tickLine: false,
            type: 'number',
            // В карточке ось значений не нужна: числа стоят списком под графиком,
            // а на 430 пикселях ширины подписи вида «2.6 млрд» съедают четверть.
            hide: compact,
            tickFormatter: (value: number) => axisTick(value, unit),
          }}
          // Столбцы подписаны осью, повторять их в легенде незачем. У рядов по
          // годам легенда единственное, что различает показатели.
          legend={!bars && spec.series.length > 1 ? { align: 'left', verticalAlign: 'bottom' } : undefined}
          tooltip={{ arrow: true, filterNull: true }}
          series={series}
          labels={[...spec.labels]}
        />
      </div>
      {/* Значения текстом: на печати наведения мышью нет, а в карточке ось
          значений скрыта — без этого списка график остаётся без чисел. */}
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
      {!compact && <p className="report-chart__source">Источник: {spec.source}</p>}
    </figure>
  );
}
