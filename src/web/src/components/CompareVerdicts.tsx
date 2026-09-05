import { Indicator } from '@alfalab/core-components-indicator';
import { Link } from '@alfalab/core-components-link';
import { Typography } from '@alfalab/core-components-typography';

import type { CompareLevel, CompareSummary, CompareVerdict } from '../types';

const ЦВЕТ: Record<CompareLevel, string> = {
  clean: '#0d9336',
  clarify: '#ea8313',
  attention: '#ec2d20',
};

/**
 * Вывод по пулу и карточки контрагентов.
 *
 * Порядок — от чистого к спорному: выбирают лучшего, и ответ на «кто лучше»
 * должен стоять первым. Порядковых номеров у карточек нет намеренно: «1-е
 * место» читается как выставленная оценка, а оценок кейсодатель просил
 * не выставлять — «ранжирование в виде какого-то скора не требуется».
 *
 * Число пройденных проверок стоит у каждой карточки, а нехватка данных
 * названа словами. Наверху списка это единственное, что отличает «проверили
 * и чисто» от «проверять было нечем»: замерено, компания проходит 14 проверок
 * из 14 при двух разделах без данных и читается как безупречная.
 */
export function CompareVerdicts({
  verdicts,
  summary,
  onOpenReport,
}: {
  verdicts: CompareVerdict[];
  summary: CompareSummary;
  onOpenReport: (inn: string, section?: string) => void;
}) {
  const ведущий = verdicts[0];

  return (
    <div className="compare">
      <section className={`compare__summary compare__summary--${ведущий?.level ?? 'clean'}`}>
        <Typography.Title tag="h2" view="small" font="styrene" weight="bold">
          {summary.headline}
        </Typography.Title>
        <p className="compare__detail">{summary.detail}</p>
        <p className="compare__note">
          Порядок — от того, к кому меньше вопросов, к тому, у кого их больше.
          Это порядок, а не оценка: баллов контрагентам не выставляем.
        </p>
      </section>

      <div className="compare__list">
        {verdicts.map((в, индекс) => (
          <article
            className={`verdict-card verdict-card--${в.level}${индекс === 0 ? ' verdict-card--lead' : ''}`}
            key={в.inn}
          >
            <div className="verdict-card__body">
              <header className="verdict-card__head">
                <Indicator size={8} backgroundColor={ЦВЕТ[в.level]} />
                <span className="verdict-card__name">{в.name}</span>
                <span className="verdict-card__label">{в.recommendation}</span>
              </header>

              {в.reasons.length > 0 ? (
                <ul className="verdict-card__reasons">
                  {в.reasons.map((причина, i) => (
                    <li key={причина}>
                      {причина}{' '}
                      {/* Причина открывает раздел, из которого взята: утверждение,
                          которое негде проверить, — утверждение на веру. */}
                      <Link
                        Component="button"
                        view="default"
                        onClick={() => onOpenReport(в.inn, в.sections[i])}
                      >
                        проверить →
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="verdict-card__clean">
                  Противоречий между разделами не нашлось.
                </p>
              )}

              {в.gaps.length > 0 && (
                <p className="verdict-card__gaps">
                  {в.gaps.length === 1 ? 'По разделу' : 'По разделам'} «{в.gaps.join('», «')}»
                  данных нет — проверить было нечем.
                </p>
              )}
            </div>

            <div className="verdict-card__aside">
              <span>
                Проверок пройдено <b>{в.checks_passed} из {в.checks_total}</b>
              </span>
              <Link Component="button" view="default" onClick={() => onOpenReport(в.inn)}>
                Открыть отчёт →
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
