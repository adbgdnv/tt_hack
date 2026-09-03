import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { ModalDesktop } from '@alfalab/core-components-modal/desktop';
import { TagDesktop as Tag } from '@alfalab/core-components-tag/desktop';
import type { BlockKey, Counterparty } from '../types';
import { FinancialChart } from './FinancialChart';

type Props = {
  company: Counterparty;
  blockKey: BlockKey | null;
  highlighted: boolean;
  onClose: () => void;
  onOpenBlock: (key: BlockKey) => void;
};

const orderedBlocks: BlockKey[] = ['registration', 'finances', 'courts', 'enforcement', 'registries', 'activity'];

export function BlockModal({ company, blockKey, highlighted, onClose, onOpenBlock }: Props) {
  const block = blockKey ? company.blocks[blockKey] : null;
  if (!block) return null;

  return (
    <ModalDesktop open={Boolean(blockKey)} size={800} hasCloser onClose={onClose} dataTestId="block-modal">
      <ModalDesktop.Header title={block.title} />
      <ModalDesktop.Content>
        <div className={`modal-content ${highlighted ? 'modal-content--highlighted' : ''}`}>
          <div className="modal-source-row">
            <Tag size={32} view="muted">{block.source}</Tag>
            <span className={`signal signal--${block.signal}`} aria-label={`Индикатор блока: ${block.signal}`} />
            <span className="muted">Ориентир по данным блока</span>
          </div>

          {block.empty ? (
            <section className="empty-detail">
              <span className="empty-detail__icon">{block.notApplicable ? '—' : '?'}</span>
              <div>
                <h3>{block.notApplicable ? 'У ИП такого не бывает' : 'Данных недостаточно'}</h3>
                <p>{block.analysis}</p>
                {block.workaround && <p><strong>Обходное решение:</strong> {block.workaround}</p>}
                <p className="muted">Проверьте связанные косвенные признаки — они перечислены во входном отчёте и соседних блоках.</p>
              </div>
            </section>
          ) : (
            <dl className="detail-grid">
              {block.details.map((item) => (
                <div key={item.label}>
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
          )}

          {block.key === 'finances' && company.financials && <FinancialChart data={company.financials} />}

          <section className="ai-analysis">
            <div className="ai-analysis__eyebrow">AI-разбор блока</div>
            <h3>{block.key === 'courts' ? 'Как это связано с обязательствами' : block.key === 'finances' ? 'Что это говорит о платёжеспособности' : 'На что обратить внимание'}</h3>
            <p>{block.analysis}</p>
            <p className="ai-analysis__guardrail">Это рекомендация по проверке, а не вердикт о компании.</p>
          </section>

          <div className="source-link">Источник: <span>{block.source}</span></div>
          <div className="other-blocks">
            <span>Открыть другой блок</span>
            <div>
              {orderedBlocks.filter((key) => key !== block.key).map((key) => (
                <button key={key} type="button" onClick={() => onOpenBlock(key)}>{company.blocks[key].title}</button>
              ))}
            </div>
          </div>
        </div>
      </ModalDesktop.Content>
      <ModalDesktop.Footer layout="start">
        <ButtonDesktop size={48} view="secondary" onClick={onClose}>Закрыть</ButtonDesktop>
      </ModalDesktop.Footer>
    </ModalDesktop>
  );
}
