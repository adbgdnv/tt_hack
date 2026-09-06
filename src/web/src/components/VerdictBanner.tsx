import { Link } from '@alfalab/core-components-link';
import { Typography } from '@alfalab/core-components-typography';

import { tone } from './SourceLights';
import type { Verdict } from '../verdict';

const LEVEL_CLASS: Record<Verdict['level'], string> = {
  clean: 'verdict--clean',
  clarify: 'verdict--clarify',
  attention: 'verdict--attention',
};

type Light = { known: boolean; value: string };

/**
 * «Второй взгляд по открытым данным» — детерминированный, не AI-вывод (см. verdict.ts).
 * Показан отдельно и явно подписан, чтобы не читаться как банковская оценка.
 *
 * Плашки в ряду светофоров у этого вывода нет намеренно: она говорила то же
 * самое одним словом за двадцать пикселей до заголовка, и объяснить себя не
 * могла. Здесь место есть — и подпись о происхождении, и разбор по разделам.
 */
export function VerdictBanner({ verdict, bank, zsk, onOpenSection }: {
  verdict: Verdict;
  bank?: Light;
  zsk?: Light;
  onOpenSection: (key: string) => void;
}) {
  // Оба чужих светофора молчат, а мы — нет. Ровно тот случай, ради которого
  // сервис сделан, и назвать его надо словами: иначе читатель решает, что
  // кто-то из троих ошибся, вместо того чтобы увидеть — они смотрят разное.
  const обаЗелёные = bank && zsk && tone(bank) === 'green' && tone(zsk) === 'green';
  const расхождение = обаЗелёные && verdict.level !== 'clean';

  const пробелы = verdict.coverageNote;

  return (
    <section className={`verdict ${LEVEL_CLASS[verdict.level]}`}>
      <span className="verdict__source">Проверка контрагента · по открытым данным</span>

      <div className="verdict__head">
        <Typography.Title tag="h2" view="small" font="styrene" weight="bold">{verdict.label}</Typography.Title>
        {verdict.checksNote && <span className="verdict__checks">{verdict.checksNote}</span>}
      </div>

      {расхождение && (
        <p className="verdict__contrast">
          Оба светофора выше зелёные. ЗСК оценивает риск операций, методику
          своего скоринга банк не раскрывает — отсутствия судов, взысканий
          и записей в реестрах ни один из них не обещает.
        </p>
      )}

      {verdict.bullets.length > 0 && (
        <ul className="verdict__bullets">
          {verdict.bullets.map((bullet) => (
            <li key={bullet.sectionKey}>
              <span className="verdict__dot" aria-hidden="true" />
              <span>
                {bullet.text}{' '}
                <Link
                  Component="button"
                  view="default"
                  onClick={() => onOpenSection(bullet.sectionKey)}
                >
                  {bullet.sectionTitle} →
                </Link>
              </span>
            </li>
          ))}
        </ul>
      )}

      {пробелы && <p className="verdict__coverage">{пробелы}</p>}
    </section>
  );
}
