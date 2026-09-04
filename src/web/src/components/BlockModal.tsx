import type { ReportSectionData } from '../types';
import { ReportSection } from './ReportSection';

type Props = {
  sections: ReportSectionData[];
  blockKey: string;
  highlighted: boolean;
  onClose: () => void;
  onOpenBlock: (key: string) => void;
};

/**
 * Деталь раздела. Раньше здесь жили две ветки — собранный отчёт и отдельная
 * разметка для урезанных данных (без стилей: классы `.detail-panel*` ни разу
 * не были определены в CSS). Теперь на входе всегда один и тот же контракт
 * `ReportSectionData` — единственная отрисовка для обоих случаев.
 */
export function BlockModal({ sections, blockKey, highlighted, onClose, onOpenBlock }: Props) {
  const section = sections.find((item) => item.key === blockKey);
  if (!section) return null;

  return (
    <section className={`section-detail${highlighted ? ' section-detail--highlighted' : ''}`} aria-live="polite">
      <button className="section-detail__back" type="button" onClick={onClose}>
        <span aria-hidden="true">←</span> Назад к разделам
      </button>

      <ReportSection section={section} mode="detail" />

      <nav className="other-blocks" aria-label="Другие разделы отчёта">
        <span>Открыть другой раздел</span>
        <div>
          {sections
            .filter((item) => item.key !== blockKey)
            .map((item) => <button key={item.key} type="button" onClick={() => onOpenBlock(item.key)}>{item.title}</button>)}
        </div>
      </nav>
    </section>
  );
}
