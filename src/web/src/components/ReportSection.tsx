import { Amount } from '@alfalab/core-components-amount';
import { Divider } from '@alfalab/core-components-divider';
import { Indicator } from '@alfalab/core-components-indicator';
import { List } from '@alfalab/core-components-list';
import { Status } from '@alfalab/core-components-status';
import { Typography } from '@alfalab/core-components-typography';

import { ReportChart } from './ReportChart';
import type { ReportFact, ReportSectionData, SectionState } from '../types';

const STATE_COLOR: Record<SectionState, 'red' | 'green' | 'grey'> = {
  signal: 'red',
  filled: 'green',
  empty: 'grey',
  not_applicable: 'grey',
};

const DOT_COLOR: Record<SectionState, string> = {
  signal: '#ec2d20',
  filled: '#0d9336',
  empty: '#9a9da4',
  not_applicable: '#9a9da4',
};

export const STATE_LABEL: Record<SectionState, string> = {
  signal: 'Есть на что обратить внимание',
  filled: 'Значимых сигналов нет',
  empty: 'Недостаточно данных',
  not_applicable: 'Не применимо',
};

/**
 * Сколько проверок раздела компания прошла.
 *
 * Заменила строку «Нейтральная значимость · негативное направление»: та
 * повторяла бейдж состояния другими словами и стояла на каждой карточке, ничего
 * не добавляя. Счётчик отвечает на вопрос, который бейдж оставлял открытым, —
 * данных нет или данные есть и всё чисто.
 *
 * Раздел без единой проверки честно говорит об этом словами, а не молчанием:
 * пустая строка читается как «мы не показали», а не «источник не смотрел».
 */
function Checks({ section }: { section: ReportSectionData }) {
  const passed = section.checks_passed;
  const total = section.checks_total;

  // Раздел собран на клиенте: про проверки неизвестно ничего, и молчание здесь
  // честнее любой формулировки.
  if (passed === undefined || total === undefined) return null;

  if (total > 0) {
    return (
      <p className={`report-section__checks${passed === total ? ' report-section__checks--clean' : ''}`}>
        Пройдено проверок <strong>{passed} из {total}</strong>
      </p>
    );
  }
  if (section.state === 'empty') {
    return <p className="report-section__checks">Источник этот раздел не проверял</p>;
  }
  return null;
}

/** Что входит в раздел — коротко, для детального вида (ux_design.md, «Description»). */
const SECTION_DESCRIPTION: Record<string, string> = {
  registration: 'Статус, возраст, адрес и реквизиты по данным ЕГРЮЛ/ЕГРИП.',
  finances: 'Выручка, прибыль и структура активов по сданной бухгалтерской отчётности.',
  courts: 'Арбитражные дела: в какой роли компания участвует и на какие суммы.',
  enforcement: 'Исполнительные производства ФССП — действующие и завершённые.',
  registries: 'Реестры ФНС и профильных ведомств: массовые адреса, блокировки, банкротство и похожее.',
  activity: 'Основной и дополнительные виды деятельности по ОКВЭД.',
  management: 'Кто руководит компанией и на каком основании.',
  related: 'Организации, связанные через учредителей или руководство.',
};

const RAW_VALUE_LABEL: Record<string, string> = {
  CURRENT: 'Действующее',
  ACTIVE: 'Действующее',
  LIQUIDATED: 'Ликвидировано',
  CLOSED: 'Закрыто',
  BANKRUPT: 'В процедуре банкротства',
};

const FACTOR_EXPLANATION: Record<string, string> = {
  massAddress: 'По этому адресу зарегистрировано много юрлиц — бывает у фиктивных фирм, стоит проверить фактическое присутствие.',
  massOkved: 'Заявлено необычно много видов деятельности — размытая специализация, сложнее оценить профильность.',
  arbitrationDefendant: 'К компании предъявляли требования в арбитраже — проверьте предметы и исходы дел до сделки.',
  executionProceedings: 'Есть действующие взыскания — они могут влиять на доступные деньги и исполнение новых обязательств.',
  fnsBlocking: 'Налоговая блокировала счета — уточните, сняты ли ограничения и доступны ли расчёты.',
  profit: 'В отчётности отражён убыток — сопоставьте его с выручкой, долгами и условиями оплаты.',
  invalidRegistrationData: 'Часть регистрационных сведений признана недостоверной — проверьте свежую выписку и полномочия подписанта.',
  invalidAddress: 'Адрес отмечен как недостоверный — стоит подтвердить, где компания фактически работает и получает корреспонденцию.',
  massAuthpersons: 'Руководитель или учредитель связан со многими компаниями — проверьте его реальную роль и полномочия.',
  invalidAuthpersonsData: 'Сведения о руководителе вызывают сомнения — подтвердите личность и право подписывать договор.',
  currentAssets: 'Оборотные активы равны нулю — у компании может не быть ресурсов для текущих расчётов.',
  liquidationStatus: 'Есть процедура прекращения деятельности или банкротства — проверьте актуальный статус до заключения договора.',
  dishonestProvider: 'Компания включалась в реестр недобросовестных поставщиков — уточните основание и срок записи.',
  taxArrears: 'Есть задолженность перед налоговой — она может привести к взысканию и ограничениям по счетам.',
  inspectionWithViolation: 'Проверки выявляли нарушения — важно понять их предмет, давность и устранены ли они.',
};

function displayValue(value: string | number): string | number {
  if (typeof value !== 'string') return value;
  return RAW_VALUE_LABEL[value.trim().toUpperCase()] ?? value;
}

/**
 * Изменение к прошлому году.
 *
 * Ради этой строки всё и затевалось: «Выручка 116 млрд» одинаково выглядит
 * у растущей компании и у падающей вдвое, а «116 млрд ↓ −38% к 2024» — уже нет.
 *
 * Цветом можно красить именно здесь: и у выручки, и у прибыли рост означает
 * одно и то же. Для величины, где больше не значит лучше, так делать нельзя.
 */
function Delta({ fact }: { fact: ReportFact }) {
  const delta = fact.delta;
  if (delta === null || delta === undefined) return null;

  const grew = delta > 0;
  const percent = Math.abs(delta) >= 0.1 ? Math.round(Math.abs(delta) * 100) : (Math.abs(delta) * 100).toFixed(1);
  return (
    <span className={`fact-delta fact-delta--${grew ? 'up' : 'down'}`}>
      <span aria-hidden="true">{grew ? '↑' : '↓'}</span>
      {grew ? '+' : '−'}{percent}%
      {fact.delta_note && <span className="fact-delta__note"> {fact.delta_note}</span>}
    </span>
  );
}

function FactValue({ fact }: { fact: ReportFact }) {
  if (fact.kind === 'money' && typeof fact.value === 'number') {
    // minority={1} — суммы приходят в целых рублях, а не в копейках.
    return <Amount value={fact.value} minority={1} currency="RUR" />;
  }
  if (fact.kind === 'ratio' && typeof fact.value === 'number') {
    // Запятая, а не точка: коэффициент читают как число, а не как код.
    return <span>{fact.value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}</span>;
  }
  return <span>{String(displayValue(fact.value))}</span>;
}

function normalizeLabel(value: string): string {
  return value.normalize('NFKC').toLocaleLowerCase('ru-RU').replace(/[^\p{L}\p{N}]+/gu, '');
}

/** Формулировки сервера, которые лишь повторяют «данных нет» и ничего не добавляют
 *  к бейджу «Недостаточно данных» — для пустого раздела их не показываем (DBG-61D108F1FE). */
const GENERIC_EMPTY_NOTES = new Set([
  normalizeLabel('Данных нет — оценить по этому критерию невозможно'),
  normalizeLabel('Нет данных'),
  normalizeLabel('Данных недостаточно'),
]);

function sectionNote(section: ReportSectionData): string {
  if (section.state === 'filled') return '';

  const note = section.note.trim()
    || (section.state === 'not_applicable' ? 'Раздел не применяется к этому типу контрагента.' : '');

  const normalized = normalizeLabel(note);
  if (normalized === normalizeLabel(STATE_LABEL[section.state])) return '';
  if (section.state === 'empty' && GENERIC_EMPTY_NOTES.has(normalized)) return '';
  return note;
}

function Facts({ facts }: { facts: ReportFact[] }) {
  if (facts.length === 0) return null;
  return (
    <dl className="report-section__facts">
      {facts.map((fact) => (
        <div key={fact.label}>
          <dt>{fact.label}</dt>
          <dd><FactValue fact={fact} /><Delta fact={fact} /></dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Модификатор карточки — визуальное «вычитание»: сигнальные разделы заметны,
 * спокойные (данные есть, ничего не сработало) — нейтральны, недостающие или
 * неприменимые — приглушены. Порядок разделов при этом не меняется нигде выше:
 * значимость выражена стилем, а не местом в сетке.
 */
function stateModifier(state: SectionState): string {
  if (state === 'signal') return 'report-section--signal';
  if (state === 'empty' || state === 'not_applicable') return 'report-section--muted';
  return 'report-section--filled';
}

export function ReportSection({ section, onOpen, mode = 'preview' }: {
  section: ReportSectionData;
  onOpen?: () => void;
  mode?: 'preview' | 'detail';
}) {
  const factors = section.factors ?? [];
  const facts = section.facts ?? [];
  const charts = section.charts ?? [];
  const passed = section.passed_checks ?? [];
  const note = sectionNote(section);
  const preview = mode === 'preview';
  // Раздел с несколькими сработавшими факторами занимает всю ширину сетки —
  // ему действительно нужно больше места, а не потому что так решил порядок.
  const wide = preview && factors.length >= 3;

  const content = (
    <>
      <header className="report-section__head">
        <div className="report-section__title">
          <Indicator size={8} backgroundColor={DOT_COLOR[section.state]} />
          <Typography.Title tag="h3" view="xsmall" font="styrene" weight="bold">{section.title}</Typography.Title>
        </div>
        <Status size={20} view="soft" color={STATE_COLOR[section.state]}>
          {STATE_LABEL[section.state]}
        </Status>
      </header>
      {!preview && SECTION_DESCRIPTION[section.key] && (
        <p className="report-section__description">{SECTION_DESCRIPTION[section.key]}</p>
      )}
      <Checks section={section} />
      {note && <p className="report-section__note">{note}</p>}

      <Facts facts={preview ? facts.slice(0, 2) : facts} />

      {factors.length > 0 && (
        <ul className="report-section__factors">
          {(preview ? factors.slice(0, wide ? 4 : 1) : factors).map((factor) => (
            <li key={factor.code}>
              <strong>{factor.heading}</strong>
              {!preview && <p>{FACTOR_EXPLANATION[factor.code] ?? factor.explanation}</p>}
            </li>
          ))}
        </ul>
      )}

      {/* Что именно проверено — только в детальном виде. На карточке этот список
          вытеснил бы всё остальное: у «Реестров» его длина доходит до девяти
          строк, а сигналов там от силы четыре. */}
      {!preview && passed.length > 0 && (
        <div className="report-section__passed">
          <Divider />
          <Typography.Text tag="p" view="secondary-medium" weight="bold">
            Пройденные проверки
          </Typography.Text>
          <List tag="ul" marker="✓" colorMarker="positive">
            {passed.map((label) => (
              <List.Item key={label}>{label}</List.Item>
            ))}
          </List>
        </div>
      )}

      {preview && charts[0] && (
        <>
          <Divider className="report-section__divider" />
          <ReportChart spec={charts[0]} compact />
        </>
      )}
      {!preview && charts.map((chart) => <ReportChart key={chart.key} spec={chart} />)}
      {!preview && section.charts_note && (
        <p className="report-section__chart-note">{section.charts_note}</p>
      )}
      {preview && <span className="report-section__action">Подробнее <span aria-hidden="true">→</span></span>}
    </>
  );

  const className = `report-section report-section--${preview ? 'preview' : 'detail'} ${stateModifier(section.state)}${wide ? ' report-section--wide' : ''}`;

  if (preview) {
    return (
      <button className={className} type="button" onClick={onOpen}>
        {content}
      </button>
    );
  }

  return <section className={className}>{content}</section>;
}
