import { findFixtureByInn, searchFixtures } from './fixtures';
import type { BlockKey, Counterparty, CounterpartyReport, ReportBlock, Signal } from './types';

const apiBase = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '');

const wait = (duration: number) => new Promise((resolve) => window.setTimeout(resolve, duration));

type SlimApiReport = {
  название?: string;
  инн?: string;
  форма?: 'ИП' | 'юрлицо';
  лет_с_регистрации?: number | null;
  статус?: string | null;
  риск_банка?: string | null;
  светофор_зск?: string | null;
  негативные_факторы?: string[];
  арбитраж_всего_дел?: number | null;
  как_ответчик_сумма?: number | null;
  производств_активных?: number | null;
  производств_сумма_активных?: number | null;
  финотчётность?: unknown;
  коэффициенты?: unknown;
  основной_оквэд?: string | null;
};

const labels: Record<BlockKey, string> = {
  registration: 'Регистрация',
  finances: 'Финансы',
  courts: 'Суды',
  enforcement: 'Исполнительные производства',
  registries: 'Реестры',
  activity: 'ОКВЭД и деятельность',
};

function unknownBlock(key: BlockKey, details: ReportBlock['details'], source: string, options?: Partial<ReportBlock>): ReportBlock {
  return {
    key,
    title: labels[key],
    signal: 'unknown',
    preview: ['Данных недостаточно', 'Откройте блок для подробностей'],
    details,
    analysis: 'Во входном ответе API недостаточно данных для более точной интерпретации.',
    source,
    empty: details.length === 0,
    workaround: 'Проверьте связанные косвенные признаки и запросите актуальные документы.',
    ...options,
  };
}

/**
 * Скоринг банка приходит значениями LOW / MEDIUM / HIGH / UNKNOWN.
 *
 * Прежнее сопоставление сравнивало их с русскими подстроками и с 'red'/'yellow',
 * из-за чего не срабатывала ни одна ветвь и все четыре значения давали «Низкий» —
 * включая высокий риск и «нет данных». Затрагивало 11 компаний из 200.
 *
 * UNKNOWN означает «оценить невозможно» и не сводится ни к низкому, ни к высокому.
 */
const asRisk = (value?: string | null): Counterparty['bankRisk'] => {
  switch (value?.trim().toUpperCase()) {
    case 'LOW': return 'Низкий';
    case 'MEDIUM': return 'Средний';
    case 'HIGH': return 'Высокий';
    default: return 'Нет данных';
  }
};

/** Платформа ЗСК Банка России: GREEN / YELLOW / RED. Отсутствие значения — не «зелёный». */
const asLight = (value?: string | null): Counterparty['bankLight'] => {
  switch (value?.trim().toUpperCase()) {
    case 'GREEN': return 'Зелёный';
    case 'YELLOW': return 'Жёлтый';
    case 'RED': return 'Красный';
    default: return 'Нет данных';
  }
};

function adaptApiReport(raw: Counterparty | SlimApiReport): Counterparty {
  if ('blocks' in raw) return raw;
  // Ответ сервера показывается всегда. Заготовленные примеры — запасной путь
  // на случай недоступного сервера, и подставляются в searchCounterparties /
  // getCounterparty до обращения, а не поверх уже полученных данных.
  const inn = String(raw.инн ?? '');

  const legalForm = raw.форма === 'ИП' ? 'entrepreneur' : 'legal';
  const courtsSignal: Signal = raw.арбитраж_всего_дел ? 'yellow' : 'unknown';
  const enforcementSignal: Signal = raw.производств_активных ? 'yellow' : 'unknown';
  const source = 'API · дата не указана';
  const status = raw.статус?.toLocaleLowerCase('ru-RU').includes('ликвид') ? 'Ликвидировано' : 'Действующее';
  const company: Counterparty = {
    name: raw.название || 'Контрагент без названия',
    inn,
    director: 'Недостаточно данных',
    legalForm,
    status,
    bankRisk: asRisk(raw.риск_банка),
    bankLight: asLight(raw.светофор_зск),
    dataDate: 'дата не указана',
    dateIso: '',
    negativeFactors: raw.негативные_факторы ?? [],
    summary: 'Показаны только факты, полученные из ответа API. Поля, которых нет в сокращённом отчёте, явно отмечены как недостаточные данные.',
    questions: ['Какие факты требуют внимания?', 'Чего не хватает в отчёте?', 'Что проверить перед сделкой?'],
    blocks: {
      registration: unknownBlock('registration', [
        { label: 'Статус', value: status },
        { label: 'Лет с регистрации', value: raw.лет_с_регистрации == null ? 'Недостаточно данных' : String(raw.лет_с_регистрации) },
      ], source, {
        signal: raw.негативные_факторы?.some((item) => ['liquidationStatus', 'invalidRegistrationData', 'invalidAddress'].includes(item)) ? 'red' : 'green',
        empty: false,
        preview: [status, raw.лет_с_регистрации == null ? 'Возраст не указан' : String(raw.лет_с_регистрации) + ' лет с регистрации'],
      }),
      finances: unknownBlock('finances', [], source, {
        notApplicable: legalForm === 'entrepreneur',
        preview: [legalForm === 'entrepreneur' ? 'У ИП такого не бывает' : 'Сокращённые данные API', 'Откройте блок для пояснения'],
      }),
      courts: unknownBlock('courts', raw.арбитраж_всего_дел == null ? [] : [
        { label: 'Арбитражных дел', value: String(raw.арбитраж_всего_дел) },
        { label: 'Сумма как ответчик', value: raw.как_ответчик_сумма == null ? 'Недостаточно данных' : raw.как_ответчик_сумма.toLocaleString('ru-RU') + ' ₽' },
      ], source, {
        signal: courtsSignal,
        empty: raw.арбитраж_всего_дел == null,
        preview: [raw.арбитраж_всего_дел == null ? 'Данных недостаточно' : String(raw.арбитраж_всего_дел) + ' арбитражных дел', 'Смотрите детали блока'],
      }),
      enforcement: unknownBlock('enforcement', raw.производств_активных == null ? [] : [
        { label: 'Активные производства', value: String(raw.производств_активных) },
        { label: 'Сумма', value: raw.производств_сумма_активных == null ? 'Недостаточно данных' : raw.производств_сумма_активных.toLocaleString('ru-RU') + ' ₽' },
      ], source, {
        signal: enforcementSignal,
        empty: raw.производств_активных == null,
        preview: [raw.производств_активных == null ? 'Данных недостаточно' : String(raw.производств_активных) + ' активных производства', 'Смотрите детали блока'],
      }),
      registries: unknownBlock('registries', [], source),
      activity: unknownBlock('activity', raw.основной_оквэд ? [{ label: 'Основной ОКВЭД', value: raw.основной_оквэд }] : [], source, {
        signal: raw.основной_оквэд ? 'green' : 'unknown',
        empty: !raw.основной_оквэд,
        preview: [raw.основной_оквэд ?? 'Данных недостаточно', 'Основной вид деятельности'],
      }),
    },
  };
  return company;
}

export async function searchCounterparties(query: string): Promise<Counterparty[]> {
  if (!apiBase) {
    await wait(260);
    return searchFixtures(query);
  }
  const response = await fetch(`${apiBase}/counterparties/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) throw new Error('Не удалось выполнить поиск');
  const raw = await response.json() as Array<Counterparty | SlimApiReport>;
  return raw.map(adaptApiReport);
}

export async function getCounterparty(inn: string): Promise<Counterparty | undefined> {
  if (!apiBase) {
    await wait(620);
    return findFixtureByInn(inn);
  }
  const response = await fetch(`${apiBase}/counterparties/${encodeURIComponent(inn)}`);
  if (response.status === 404) return undefined;
  if (!response.ok) throw new Error('Не удалось загрузить отчёт');
  const raw = await response.json() as Counterparty | SlimApiReport;
  return adaptApiReport(raw);
}

/**
 * Собранный отчёт с сервера.
 *
 * Порядок разделов и формулировки приходят готовыми: интерфейс их показывает,
 * а не вычисляет. Заготовленных примеров здесь нет вовсе — отчёт либо настоящий,
 * либо его нет.
 */
export async function getReport(inn: string): Promise<CounterpartyReport | undefined> {
  if (!apiBase) return undefined;
  const response = await fetch(`${apiBase}/counterparties/${encodeURIComponent(inn)}/report`);
  if (response.status === 404) return undefined;
  if (!response.ok) throw new Error('Не удалось загрузить отчёт');
  return (await response.json()) as CounterpartyReport;
}
