import { Collapse } from '@alfalab/core-components-collapse';

import type { ChartSpec, ToolCall } from '../types';
import { ReportChart } from './ReportChart';

/**
 * Вызов инструмента в ленте чата — вместе со своим результатом.
 *
 * Раньше вызов был разорван на три места: отметка сверху сообщения, график
 * в середине, ссылки в самом низу. Пользователь читал ответ и не связывал
 * «искал» наверху с ссылками внизу. Теперь это один блок на своём месте
 * в ходе разговора.
 *
 * Свёрнут по умолчанию: работа агента — шум второго плана, внимание должно
 * оставаться на ответе.
 */

const MARKS: Record<ToolCall['state'], string> = {
  running: '⋯',
  ok: '✓',
  failed: '✕',
  aborted: '—',
};

const NOTES: Record<ToolCall['state'], string> = {
  running: 'Выполняется…',
  ok: 'Данные для ответа взяты отсюда.',
  // Пользователь должен понимать, на что ответ ниже НЕ опирается: иначе шаг,
  // который тихо не сработал, неотличим от сработавшего.
  failed: 'Шаг не удался — то, что ниже, на него не опирается.',
  aborted: 'Ответ прервался, шаг не доведён до конца.',
};

export function ToolBlock({
  call,
  chart,
  expanded,
  onToggle,
}: {
  call: ToolCall;
  /** Описание графика из уже загруженного отчёта. Событие несёт только ключ,
   *  поэтому числа в чате не могут разойтись с дашбордом. */
  chart?: ChartSpec;
  expanded: boolean;
  onToggle: () => void;
}) {
  // Пока вызов идёт, показывать нечего — раскрывать нечего.
  const openable = call.state !== 'running';
  const hasBody = Boolean(chart) || Boolean(call.sources?.length);

  return (
    <div className={`tool-block tool-block--${call.state}`}>
      <button
        type="button"
        className="tool-block__head"
        onClick={onToggle}
        disabled={!openable}
        aria-expanded={openable ? expanded : undefined}
      >
        <span className="tool-block__mark" aria-hidden="true">
          {MARKS[call.state]}
        </span>
        <span className="tool-block__title">{call.title}</span>
      </button>

      {/* Без подписей Collapse не рисует собственный переключатель — только
          анимирует раскрытие. Шапка у нас своя: в ней состояние и подпись. */}
      <Collapse expanded={openable && expanded}>
        <div className="tool-block__body">
          <p className="tool-block__note">{NOTES[call.state]}</p>

          {chart && (
            <div className="tool-block__chart">
              <ReportChart spec={chart} />
            </div>
          )}

          {call.sources && call.sources.length > 0 && (
            <div className="tool-block__sources">
              <span>Внешние источники — отчётом не подтверждены:</span>
              <ul>
                {call.sources.map((source) => (
                  <li key={source.url}>
                    <a href={source.url} target="_blank" rel="noopener noreferrer nofollow">
                      {source.title || source.url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Инструмент отработал без выхлопа — так и говорим. Пустое раскрытие
              выглядело бы как потерянный результат. */}
          {call.state === 'ok' && !hasBody && (
            <p className="tool-block__note">Показывать нечего — инструмент ничего не вернул.</p>
          )}
        </div>
      </Collapse>
    </div>
  );
}
