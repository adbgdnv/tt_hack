import type { ReportSectionData } from './types';

export type VerdictLevel = 'clean' | 'clarify' | 'attention';

export type VerdictBullet = {
  sectionKey: string;
  sectionTitle: string;
  text: string;
};

export type Verdict = {
  level: VerdictLevel;
  label: string;
  bullets: VerdictBullet[];
  /** Заполнено, когда пробелов в разделах достаточно, чтобы вывод считался неполным. */
  coverageNote: string;
};

const LABEL: Record<VerdictLevel, string> = {
  clean: 'Выглядит чисто',
  clarify: 'Уточнить перед сделкой',
  attention: 'Обратить внимание',
};

function maxWeight(section: ReportSectionData): number {
  return section.factors.reduce((max, factor) => Math.max(max, factor.weight), 0);
}

/**
 * Второй, независимый взгляд по открытым данным — не банковский скоринг и не ответ
 * модели. Арифметика поверх уже показанных ниже разделов: какие сработали (`signal`)
 * и с каким весом фактора — тем же весом, что определяет порядок значимости в
 * собранном отчёте. Никаких новых полей и обращений к серверу.
 *
 * Кейсодатель прямо разрешил давать собственный вывод с ограниченным словарём —
 * «обратить внимание / уточнить / выглядит чисто» (см. docs/roles_situations.md,
 * ту же тройку значений закладывает `compare.Verdict.recommendation`). Вывод не
 * подменяет банковский risk signal и не заявляет большей точности, чем в фактах,
 * которые он пересказывает.
 */
export function deriveVerdict(sections: ReportSectionData[]): Verdict {
  const applicable = sections.filter((section) => section.state !== 'not_applicable');
  const signalSections = sections.filter((section) => section.state === 'signal');

  const bullets: VerdictBullet[] = [...signalSections]
    .sort((a, b) => maxWeight(b) - maxWeight(a))
    .slice(0, 3)
    .map((section) => ({
      sectionKey: section.key,
      sectionTitle: section.title,
      text: section.factors[0]?.explanation || section.note,
    }));

  const emptyCount = applicable.filter((section) => section.state === 'empty').length;
  const coverageNote = applicable.length > 0 && emptyCount >= Math.max(2, Math.ceil(applicable.length / 2))
    ? `Из ${emptyCount} разделов не хватает данных — вывод неполный.`
    : '';

  if (signalSections.length === 0) {
    return { level: 'clean', label: LABEL.clean, bullets: [], coverageNote };
  }

  const heavy = signalSections.some((section) => maxWeight(section) >= 3);
  if (heavy || signalSections.length >= 2) {
    return { level: 'attention', label: LABEL.attention, bullets, coverageNote };
  }
  return { level: 'clarify', label: LABEL.clarify, bullets, coverageNote };
}
