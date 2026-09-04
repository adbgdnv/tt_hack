import { Amount } from '@alfalab/core-components-amount';
import { Status } from '@alfalab/core-components-status';

import { ReportChart } from './ReportChart';
import type { ReportFact, ReportSectionData, SectionState } from '../types';

/**
 * Цвет состояния раздела. Пустой раздел серый, а не зелёный: «данных нет»
 * и «всё чисто» — разные утверждения, и путать их нельзя.
 */
const STATE_COLOR: Record<SectionState, 'red' | 'green' | 'grey'> = {
  signal: 'red',
  filled: 'green',
  empty: 'grey',
  not_applicable: 'grey',
};

const STATE_LABEL: Record<SectionState, string> = {
  signal: 'Обратить внимание',
  filled: 'Чисто',
  empty: 'Нет данных',
  not_applicable: 'Не применимо',
};

function FactValue({ fact }: { fact: ReportFact }) {
  if (fact.kind === 'money' && typeof fact.value === 'number') {
    // minority={1} — суммы приходят в целых рублях, а не в копейках
    return <Amount value={fact.value} minority={1} currency="RUR" />;
  }
  return <span>{String(fact.value)}</span>;
}

export function ReportSection({ section }: { section: ReportSectionData }) {
  const muted = section.state === 'empty' || section.state === 'not_applicable';
  return (
    <section className={muted ? 'report-section report-section--muted' : 'report-section'}>
      <header className="report-section__head">
        <h3>{section.title}</h3>
        <Status size={20} view="soft" color={STATE_COLOR[section.state]}>
          {STATE_LABEL[section.state]}
        </Status>
      </header>

      {/* Формулировка состояния приходит с сервера готовой — придумывать не надо */}
      <p className="report-section__note">{section.note}</p>

      {section.factors.length > 0 && (
        <ul className="report-section__factors">
          {section.factors.map((factor) => (
            <li key={factor.code}>
              <strong>{factor.heading}</strong>
              {/* Текст из выгрузки кейсодателя, дословно */}
              <p>{factor.explanation}</p>
            </li>
          ))}
        </ul>
      )}

      {/* Графики приходят готовыми: сервер уже решил, хватает ли данных.
          Пустых рамок здесь быть не может по контракту. */}
      {section.charts.map((chart) => (
        <ReportChart key={chart.key} spec={chart} />
      ))}

      {/* Молчание там, где график ожидается, читается как поломка вёрстки.
          Объяснение приходит с сервера готовым. */}
      {section.charts_note && <p className="report-section__chart-note">{section.charts_note}</p>}

      {section.facts.length > 0 && (
        <dl className="report-section__facts">
          {section.facts.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd><FactValue fact={fact} /></dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
