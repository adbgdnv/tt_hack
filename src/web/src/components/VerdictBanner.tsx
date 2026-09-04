import type { Verdict } from '../verdict';

const LEVEL_CLASS: Record<Verdict['level'], string> = {
  clean: 'verdict--clean',
  clarify: 'verdict--clarify',
  attention: 'verdict--attention',
};

/**
 * «Второй взгляд по открытым данным» — детерминированный, не AI-вывод (см. verdict.ts).
 * Показан отдельно и явно подписан, чтобы не читаться как банковская оценка.
 */
export function VerdictBanner({ verdict, showGaps, onOpenSection }: {
  verdict: Verdict;
  /** Чипы «чего светофоры не покрывают» — только когда есть с чем сравнивать. */
  showGaps: boolean;
  onOpenSection: (key: string) => void;
}) {
  return (
    <section className={`verdict ${LEVEL_CLASS[verdict.level]}`}>
      <span className="eyebrow">Второй взгляд по открытым данным · это не оценка банка</span>
      <div className="verdict__head">
        <h2>{verdict.label}</h2>
        <span className="verdict__hint">собран из фактов ниже · решение о работе принимаете вы</span>
      </div>

      {verdict.bullets.length > 0 && (
        <ul className="verdict__bullets">
          {verdict.bullets.map((bullet) => (
            <li key={bullet.sectionKey}>
              <span className="verdict__dot" aria-hidden="true" />
              <span>
                {bullet.text}{' '}
                <button type="button" onClick={() => onOpenSection(bullet.sectionKey)}>{bullet.sectionTitle} →</button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {verdict.coverageNote && <p className="verdict__coverage">{verdict.coverageNote}</p>}

      {showGaps && (
        <div className="verdict__gaps">
          <span>Чего два светофора выше не показывают:</span>
          <div>
            <span className="static-label">методология банка закрыта</span>
            <span className="static-label">жёлтый и красный ЗСК выведены серым</span>
            <span className="static-label">оба не учитывают динамику</span>
          </div>
        </div>
      )}
    </section>
  );
}
