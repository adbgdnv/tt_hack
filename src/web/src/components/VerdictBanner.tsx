import { Link } from '@alfalab/core-components-link';
import { Typography } from '@alfalab/core-components-typography';

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
export function VerdictBanner({ verdict, onOpenSection }: {
  verdict: Verdict;
  onOpenSection: (key: string) => void;
}) {
  return (
    <section className={`verdict ${LEVEL_CLASS[verdict.level]}`}>
      <div className="verdict__head">
        <Typography.Title tag="h2" view="small" font="styrene" weight="bold">{verdict.label}</Typography.Title>
        {verdict.checksNote && <span className="verdict__checks">{verdict.checksNote}</span>}
      </div>

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

      {verdict.coverageNote && <p className="verdict__coverage">{verdict.coverageNote}</p>}
    </section>
  );
}
