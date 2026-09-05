import { Link } from '@alfalab/core-components-link';
import { Typography } from '@alfalab/core-components-typography';

import type { ReportTrigger } from '../types';

/**
 * Противоречия между разделами отчёта.
 *
 * Стоит над разделами, а не среди них, потому что живёт между ними: «оценки
 * зелёные, а по судам тяжело» принадлежит и разделу оценок, и разделу судов
 * сразу, и приписать его одному значит потерять вторую половину.
 *
 * Ради этого блока продукт и сделан: пользователь приходит за решением, а не
 * за чтением восьми карточек. Замерено — у 147 компаний из 200 здесь пусто,
 * и это тоже ответ, причём самый быстрый.
 *
 * Пустой случай проговаривается словами. Пустое место читается как «блок
 * не загрузился», а не как «противоречий нет».
 */
export function TriggersBlock({
  triggers,
  onOpenSection,
}: {
  triggers: ReportTrigger[];
  onOpenSection: (key: string) => void;
}) {
  return (
    <section className="triggers" aria-label="Противоречия в данных">
      <header className="triggers__head">
        <Typography.Title tag="h2" view="xsmall" font="styrene" weight="bold">
          Что не сходится
        </Typography.Title>
        <p className="triggers__note">
          Разделы отчёта, которые противоречат друг другу. Найдено сопоставлением —
          источник этого готовым не даёт.
        </p>
      </header>

      {triggers.length === 0 ? (
        <p className="triggers__empty">
          Противоречий между разделами не нашлось. Это не значит «рисков нет» —
          значит, что разделы друг другу не противоречат.
        </p>
      ) : (
        <ul className="triggers__list">
          {triggers.map((trigger) => (
            <li key={trigger.key} className="trigger">
              <p className="trigger__title">{trigger.title}</p>
              <p className="trigger__explanation">{trigger.explanation}</p>
              {trigger.evidence.length > 0 && (
                <ul className="trigger__evidence">
                  {trigger.evidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
              {/* Ссылка на раздел обязательна: утверждение, которое негде
                  проверить, — это утверждение на веру. */}
              <Link Component="button" view="default" onClick={() => onOpenSection(trigger.section)}>
                Проверить в отчёте →
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
