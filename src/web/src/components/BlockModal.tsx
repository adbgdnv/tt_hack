import type { BlockKey, Counterparty, CounterpartyReport } from '../types';
import { ReportSection } from './ReportSection';

type Props = {
  company: Counterparty;
  report: CounterpartyReport | null;
  blockKey: string;
  highlighted: boolean;
  onClose: () => void;
  onOpenBlock: (key: string) => void;
};

const orderedBlocks: BlockKey[] = ['registration', 'finances', 'courts', 'enforcement', 'registries', 'activity'];

function isBlockKey(value: string): value is BlockKey {
  return orderedBlocks.includes(value as BlockKey);
}

export function BlockModal({ company, report, blockKey, highlighted, onClose, onOpenBlock }: Props) {
  const section = report?.sections.find((item) => item.key === blockKey);
  const block = !section && isBlockKey(blockKey) ? company.blocks[blockKey] : null;
  if (!section && !block) return null;

  return (
    <section className={`detail-panel${highlighted ? ' detail-panel--highlighted' : ''}`} aria-live="polite">
      <button className="detail-panel__back" type="button" onClick={onClose}>
        <span aria-hidden="true">←</span> Назад к разделам
      </button>

      {section ? (
        <ReportSection section={section} mode="detail" />
      ) : block ? (
        <div className="report-section report-section--detail">
          <header className="report-section__head">
            <h3>{block.title}</h3>
            <span className="static-label">Ориентир по данным раздела</span>
          </header>
          <p className="report-section__significance">
            {block.signal === 'unknown' ? 'Значимость не оценена' : 'Оценка значимости по данным раздела'}
          </p>

          {block.details.length > 0 && (
            <dl className="detail-grid">
              {block.details.map((item) => (
                <div key={item.label}>
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
          )}

          {block.empty && (
            <section className="empty-detail">
              <span className="empty-detail__icon">{block.notApplicable ? '—' : '?'}</span>
              <div>
                <h3>{block.notApplicable ? 'Не применимо' : 'Недостаточно данных'}</h3>
                {block.workaround && <p><strong>Что можно сделать:</strong> {block.workaround}</p>}
              </div>
            </section>
          )}

          <section className="ai-analysis">
            <div className="ai-analysis__eyebrow">Комментарий к фактам</div>
            <p>{block.analysis}</p>
            <p className="ai-analysis__guardrail">Это пояснение для проверки, а не вердикт о компании.</p>
          </section>
          <div className="source-link">Источник: <span>{block.source}</span></div>
        </div>
      ) : null}

      <nav className="other-blocks" aria-label="Другие разделы отчёта">
        <span>Открыть другой раздел</span>
        <div>
          {report
            ? report.sections.filter((item) => item.key !== blockKey).map((item) => (
              <button key={item.key} type="button" onClick={() => onOpenBlock(item.key)}>{item.title}</button>
            ))
            : orderedBlocks.filter((key) => key !== blockKey).map((key) => (
              <button key={key} type="button" onClick={() => onOpenBlock(key)}>{company.blocks[key].title}</button>
            ))}
        </div>
      </nav>
    </section>
  );
}
