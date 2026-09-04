import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { TagDesktop } from '@alfalab/core-components-tag/desktop';

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
      <ButtonDesktop
        className="section-detail__back"
        size={40}
        view="text"
        leftAddons={<span aria-hidden="true">←</span>}
        onClick={onClose}
      >
        Назад к разделам
      </ButtonDesktop>

      <ReportSection section={section} mode="detail" />

      <nav className="other-blocks" aria-label="Другие разделы отчёта">
        <span>Открыть другой раздел</span>
        <div>
          {sections
            .filter((item) => item.key !== blockKey)
            .map((item) => (
              <TagDesktop key={item.key} size={40} onClick={() => onOpenBlock(item.key)}>
                {item.title}
              </TagDesktop>
            ))}
        </div>
      </nav>
    </section>
  );
}
