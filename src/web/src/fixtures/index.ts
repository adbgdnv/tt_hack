import type { AgentAnswer, BlockKey, Counterparty } from '../types';


export const counterparties: Counterparty[] = [
  {
    name: 'ООО «МАКСМАРКЕТ»',
    inn: '7716512345',
    director: 'Максимов Сергей Петрович',
    legalForm: 'legal',
    status: 'Действующее',
    bankRisk: 'Низкий',
    bankLight: 'Зелёный',
    dataDate: '02.09.2026',
    dateIso: '2026-09-02',
    negativeFactors: [
      'arbitrationDefendant',
      'executionProceedings',
      'liquidationStatus',
      'invalidRegistrationData',
    ],
    summary:
      'Банк оценивает риск как низкий, ЗСК — зелёный. При этом во входных данных есть факты, которые стоит проверить отдельно: 4 арбитражных дела в роли ответчика, 54 активных исполнительных производства, предстоящее исключение из ЕГРЮЛ и падение выручки на 34% год к году.',
    questions: [
      'Что означают судебные дела для сделки?',
      'Что проверить из-за исключения из ЕГРЮЛ?',
      'Насколько существенно падение выручки?',
    ],
    financials: [
      { year: 2022, revenue: 210, profit: 12 },
      { year: 2023, revenue: 260, profit: 9 },
      { year: 2024, revenue: 240, profit: 4 },
      { year: 2025, revenue: 158, profit: -6 },
    ],
    blocks: {
      registration: {
        key: 'registration',
        title: 'Регистрация',
        signal: 'red',
        preview: ['8 лет с регистрации', 'Предстоящее исключение из ЕГРЮЛ'],
        details: [
          { label: 'Статус', value: 'Действующее' },
          { label: 'Возраст', value: '8 лет' },
          { label: 'ЕГРЮЛ', value: 'Принято решение о предстоящем исключении' },
          { label: 'Сведения', value: 'Есть недостоверные регистрационные сведения' },
        ],
        analysis:
          'Предстоящее исключение и недостоверные сведения могут повлиять на исполнение договора. Агент рекомендует проверить актуальную выписку и полномочия подписанта перед сделкой.',
        source: 'ЕГРЮЛ · 02.09.2026',
      },
      finances: {
        key: 'finances',
        title: 'Финансы',
        signal: 'yellow',
        preview: ['Выручка 158 млн ₽', '−34% г/г; прибыль −6 млн ₽'],
        details: [
          { label: 'Выручка 2025', value: '158 млн ₽' },
          { label: 'Динамика 2024 → 2025', value: '−34%' },
          { label: 'Чистая прибыль 2025', value: '−6 млн ₽' },
          { label: 'Бухотчётность за 2025', value: 'Не представлена' },
        ],
        analysis:
          'Снижение выручки и переход к убытку могут влиять на платёжеспособность. Полноценный вывод невозможен без бухгалтерской отчётности за 2025 год; стоит запросить её у контрагента.',
        source: 'Финансы · 02.09.2026',
      },
      courts: {
        key: 'courts',
        title: 'Суды',
        signal: 'red',
        preview: ['4 дела — во всех ответчик', '8,2 млн ₽ за последние 12 месяцев'],
        details: [
          { label: 'Арбитражных дел', value: '4' },
          { label: 'Роль', value: 'Ответчик во всех делах' },
          { label: 'Сумма требований', value: '8,2 млн ₽' },
          { label: 'Решения', value: 'Одно решение против контрагента' },
        ],
        analysis:
          'Иски в роли ответчика могут указывать на спорные обязательства. Важно сопоставить предметы дел с будущим договором и проверить исполнение решения против контрагента.',
        source: 'Картотека арбитражных дел · 02.09.2026',
      },
      enforcement: {
        key: 'enforcement',
        title: 'Исполнительные производства',
        signal: 'red',
        preview: ['54 активных производства', 'Требуется проверка обязательств'],
        details: [
          { label: 'Активные производства', value: '54' },
          { label: 'Статус данных', value: 'Подтверждено во входном отчёте' },
        ],
        analysis:
          'Большое число активных производств может влиять на способность своевременно исполнять новые обязательства. Сумма производств во входных данных не указана.',
        source: 'ФССП · 02.09.2026',
      },
      registries: {
        key: 'registries',
        title: 'Реестры',
        signal: 'unknown',
        preview: ['Бенефициары не раскрыты', 'Данных недостаточно'],
        details: [{ label: 'Бенефициары', value: 'Не раскрыты' }],
        analysis:
          'Структуру владения по входным данным оценить нельзя. Это пробел, а не подтверждение отсутствия связанных рисков.',
        source: 'Реестры · 02.09.2026',
        empty: true,
        workaround: 'Запросите структуру владения и проверьте руководителя и адрес по косвенным признакам.',
      },
      activity: {
        key: 'activity',
        title: 'ОКВЭД и деятельность',
        signal: 'green',
        preview: ['Оптовая торговля продуктами', 'Основной вид деятельности указан'],
        details: [
          { label: 'Основной ОКВЭД', value: 'Оптовая торговля пищевыми продуктами' },
          { label: 'Статус', value: 'Данные представлены' },
        ],
        analysis:
          'Основной вид деятельности указан. Сопоставьте его с предметом будущего договора — агент не может сделать это без условий сделки.',
        source: 'ЕГРЮЛ · 02.09.2026',
      },
    },
  },
  {
    name: 'ООО «Ромашка»',
    inn: '7701234567',
    director: 'Соколова Елена Игоревна',
    legalForm: 'legal',
    status: 'Действующее',
    bankRisk: 'Низкий',
    bankLight: 'Зелёный',
    dataDate: '02.09.2026',
    dateIso: '2026-09-02',
    negativeFactors: [],
    summary:
      'Банковский риск низкий, ЗСК — зелёный, негативные факторы во входных данных не обнаружены. Выручка растёт, но часть реестров не заполнена: отсутствие данных нельзя считать подтверждением отсутствия рисков.',
    questions: [
      'Какие данные подтверждают стабильность?',
      'Чего не хватает в реестрах?',
      'Что проверить перед предоплатой?',
    ],
    financials: [
      { year: 2022, revenue: 48, profit: 3 },
      { year: 2023, revenue: 61, profit: 5 },
      { year: 2024, revenue: 74, profit: 6 },
      { year: 2025, revenue: 89, profit: 8 },
    ],
    blocks: {
      registration: {
        key: 'registration', title: 'Регистрация', signal: 'green',
        preview: ['Действующее юрлицо', '6 лет с регистрации'],
        details: [{ label: 'Статус', value: 'Действующее' }, { label: 'Возраст', value: '6 лет' }],
        analysis: 'Негативных регистрационных факторов во входных данных не обнаружено.',
        source: 'ЕГРЮЛ · 02.09.2026',
      },
      finances: {
        key: 'finances', title: 'Финансы', signal: 'green',
        preview: ['Выручка растёт', 'Прибыль положительная'],
        details: [{ label: 'Выручка 2025', value: '89 млн ₽' }, { label: 'Чистая прибыль 2025', value: '8 млн ₽' }],
        analysis: 'По представленным годам выручка и прибыль растут. Условия сделки во входных данных отсутствуют, поэтому допустимый размер аванса агент не определяет.',
        source: 'Финансы · 02.09.2026',
      },
      courts: {
        key: 'courts', title: 'Суды', signal: 'green',
        preview: ['Негативных факторов нет', 'Дела не указаны'],
        details: [{ label: 'Негативные факторы', value: 'Не обнаружены' }],
        analysis: 'Судебные негативные факторы во входных данных не обнаружены.',
        source: 'Арбитраж · 02.09.2026',
      },
      enforcement: {
        key: 'enforcement', title: 'Исполнительные производства', signal: 'green',
        preview: ['Активные производства не указаны', 'Негативных факторов нет'],
        details: [{ label: 'Негативные факторы', value: 'Не обнаружены' }],
        analysis: 'Признаков активных исполнительных производств во входных данных не обнаружено.',
        source: 'ФССП · 02.09.2026',
      },
      registries: {
        key: 'registries', title: 'Реестры', signal: 'unknown',
        preview: ['Часть реестров не заполнена', 'Данных недостаточно'],
        details: [{ label: 'Статус', value: 'Недостаточно данных' }],
        analysis: 'По незаполненным реестрам оценка невозможна. Пустое поле не означает отсутствия записи.',
        source: 'Реестры · 02.09.2026', empty: true,
        workaround: 'Проверьте актуальные выписки и связанные косвенные признаки: адрес, руководителя и судебные дела.',
      },
      activity: {
        key: 'activity', title: 'ОКВЭД и деятельность', signal: 'green',
        preview: ['Розничная торговля', 'Основной ОКВЭД указан'],
        details: [{ label: 'Основной ОКВЭД', value: 'Розничная торговля' }],
        analysis: 'Основной вид деятельности представлен; сопоставьте его с предметом договора.',
        source: 'ЕГРЮЛ · 02.09.2026',
      },
    },
  },
  {
    name: 'ИП Кузнецов Андрей Викторович',
    inn: '771612345678',
    director: 'Кузнецов Андрей Викторович',
    legalForm: 'entrepreneur',
    status: 'Действующее',
    bankRisk: 'Низкий',
    bankLight: 'Зелёный',
    dataDate: '02.09.2026',
    dateIso: '2026-09-02',
    negativeFactors: ['executionProceedings'],
    summary:
      'Банковский риск низкий, ЗСК — зелёный. Во входных данных есть 2 исполнительных производства. У ИП не бывает учредителей, уставного капитала и бухгалтерской отчётности юрлица — эти поля не считаются пробелами.',
    questions: [
      'Что значат 2 исполнительных производства?',
      'Как оценить ИП без бухотчётности?',
      'Что проверить перед договором?',
    ],
    blocks: {
      registration: {
        key: 'registration', title: 'Регистрация', signal: 'green',
        preview: ['Действующий ИП', 'Учредителей и капитала не бывает'],
        details: [
          { label: 'Статус', value: 'Действующее' },
          { label: 'Учредители', value: 'У ИП такого не бывает' },
          { label: 'Уставный капитал', value: 'У ИП такого не бывает' },
        ],
        analysis: 'Регистрационный статус действующий. Учредители и уставный капитал неприменимы к ИП.',
        source: 'ЕГРИП · 02.09.2026',
      },
      finances: {
        key: 'finances', title: 'Финансы', signal: 'unknown',
        preview: ['У ИП нет бухотчётности юрлица', 'Оценка по косвенным признакам'],
        details: [{ label: 'Бухгалтерская отчётность', value: 'У ИП такого не бывает' }],
        analysis: 'Бухгалтерской отчётности юрлица у ИП не бывает. Платёжеспособность можно оценивать только косвенно — по производствам и судебным делам из входного отчёта.',
        source: 'Финансы · 02.09.2026', empty: true, notApplicable: true,
        workaround: 'Проверьте исполнительные производства, суды и запросите документы по условиям сделки.',
      },
      courts: {
        key: 'courts', title: 'Суды', signal: 'unknown',
        preview: ['Данных недостаточно', 'Проверьте косвенные признаки'],
        details: [{ label: 'Судебные дела', value: 'Недостаточно данных' }],
        analysis: 'По судебным делам во входном отчёте недостаточно данных для оценки.',
        source: 'Арбитраж · 02.09.2026', empty: true,
        workaround: 'Сопоставьте данные с исполнительными производствами и запросите актуальную выписку.',
      },
      enforcement: {
        key: 'enforcement', title: 'Исполнительные производства', signal: 'yellow',
        preview: ['2 активных производства', 'Сумма не указана'],
        details: [{ label: 'Активные производства', value: '2' }, { label: 'Сумма', value: 'Недостаточно данных' }],
        analysis: 'Два активных производства — повод уточнить основания и статус исполнения. Сумма во входных данных не указана.',
        source: 'ФССП · 02.09.2026',
      },
      registries: {
        key: 'registries', title: 'Реестры', signal: 'unknown',
        preview: ['Данных недостаточно', 'Связанные признаки не заполнены'],
        details: [{ label: 'Статус', value: 'Недостаточно данных' }],
        analysis: 'По реестрам во входных данных оценка невозможна.',
        source: 'Реестры · 02.09.2026', empty: true,
        workaround: 'Проверьте актуальные открытые выписки и сопоставьте их с договором.',
      },
      activity: {
        key: 'activity', title: 'ОКВЭД и деятельность', signal: 'green',
        preview: ['Грузовые перевозки', 'Основной ОКВЭД указан'],
        details: [{ label: 'Основной ОКВЭД', value: 'Деятельность автомобильного грузового транспорта' }],
        analysis: 'Вид деятельности указан. Сопоставьте его с предметом договора.',
        source: 'ЕГРИП · 02.09.2026',
      },
    },
  },
];

export const findFixtureByInn = (inn: string) =>
  counterparties.find((company) => company.inn === inn);

export const searchFixtures = (query: string) => {
  const normalized = query.trim().toLocaleLowerCase('ru-RU');
  if (!normalized) return [];
  return counterparties.filter((company) =>
    [company.name, company.inn, company.director]
      .join(' ')
      .toLocaleLowerCase('ru-RU')
      .includes(normalized),
  );
};

const answersByBlock: Record<BlockKey, (company: Counterparty) => AgentAnswer> = {
  registration: (company) => ({
    fact: company.blocks.registration.details.map((item) => `${item.label}: ${item.value}`).join('. '),
    interpretation: company.blocks.registration.analysis,
    gap: company.legalForm === 'entrepreneur' ? 'Учредители и уставный капитал к ИП неприменимы.' : 'Условия будущей сделки во входных данных отсутствуют.',
    next: 'Проверьте актуальную выписку и полномочия подписанта на дату договора.',
    proofs: [{ value: company.blocks.registration.details[1]?.value ?? company.status, label: 'регистрационные сведения', source: company.blocks.registration.source, block: 'registration' }],
  }),
  finances: (company) => ({
    fact: company.legalForm === 'entrepreneur' ? 'У ИП не бывает бухгалтерской отчётности юридического лица.' : company.blocks.finances.preview.join('. '),
    interpretation: company.blocks.finances.analysis,
    gap: company.legalForm === 'entrepreneur' ? 'Это неприменимое поле, а не отсутствие данных.' : company.inn === '7716512345' ? 'Бухгалтерская отчётность за 2025 год не представлена.' : 'Условия сделки и размер обязательства не указаны.',
    next: company.blocks.finances.workaround ?? 'Запросите актуальную отчётность и сопоставьте показатели с суммой сделки.',
    proofs: company.inn === '7716512345' ? [{ value: '−34%', label: 'выручка год к году', source: 'Финансы · 02.09.2026', block: 'finances' }, { value: '−6 млн ₽', label: 'чистая прибыль 2025', source: 'Финансы · 02.09.2026', block: 'finances' }] : [],
  }),
  courts: (company) => ({
    fact: company.inn === '7716512345' ? 'За последние 12 месяцев указаны 4 дела, во всех компания выступает ответчиком. Сумма требований — 8,2 млн ₽.' : company.blocks.courts.preview.join('. '),
    interpretation: company.blocks.courts.analysis,
    gap: company.blocks.courts.empty ? 'Данных недостаточно — отсутствие записи не подтверждает отсутствие дел.' : 'Предметы дел и тексты судебных актов во входных данных не раскрыты.',
    next: company.blocks.courts.workaround ?? 'Откройте карточки дел, уточните предмет требований и исполнение решений.',
    proofs: company.inn === '7716512345' ? [{ value: '4', label: 'дела в роли ответчика', source: 'Суды · 02.09.2026', block: 'courts' }, { value: '8,2 млн ₽', label: 'сумма требований', source: 'Суды · 02.09.2026', block: 'courts' }] : [],
  }),
  enforcement: (company) => ({
    fact: company.blocks.enforcement.preview.join('. '),
    interpretation: company.blocks.enforcement.analysis,
    gap: 'Основания и сумма каждого производства во входных данных не раскрыты.',
    next: 'Уточните основания производств и их текущий статус перед принятием решения.',
    proofs: [{ value: company.inn === '7716512345' ? '54' : company.inn === '771612345678' ? '2' : '0', label: 'активных производств', source: company.blocks.enforcement.source, block: 'enforcement' }],
  }),
  registries: (company) => ({
    fact: company.blocks.registries.preview.join('. '),
    interpretation: company.blocks.registries.analysis,
    gap: 'Данных недостаточно. Это ответ, а не нулевой риск.',
    next: company.blocks.registries.workaround ?? 'Запросите актуальные реестровые сведения.',
    proofs: [],
  }),
  activity: (company) => ({
    fact: company.blocks.activity.preview.join('. '),
    interpretation: company.blocks.activity.analysis,
    gap: 'Предмет будущего договора во входных данных отсутствует.',
    next: 'Сопоставьте основной ОКВЭД с предметом и масштабом сделки.',
    proofs: [],
  }),
};

export function scenarioAnswer(company: Counterparty, question: string, context?: BlockKey): AgentAnswer {
  const lowered = question.toLocaleLowerCase('ru-RU');
  let block = context;
  if (lowered.includes('суд') || lowered.includes('иск')) block = 'courts';
  else if (lowered.includes('выруч') || lowered.includes('финанс') || lowered.includes('прибыл') || lowered.includes('бух')) block = 'finances';
  else if (lowered.includes('исключ') || lowered.includes('егрюл') || lowered.includes('регистра')) block = 'registration';
  else if (lowered.includes('производств') || lowered.includes('фссп')) block = 'enforcement';
  else if (lowered.includes('реестр') || lowered.includes('бенефициар')) block = 'registries';
  else if (lowered.includes('оквэд') || lowered.includes('деятельност')) block = 'activity';
  return answersByBlock[block ?? 'registration'](company);
}

export const blockQuestions: Record<BlockKey, string[]> = {
  registration: ['Что означает текущий статус?', 'Какие сведения проверить в выписке?', 'Как проверить полномочия подписанта?'],
  finances: ['Как менялась выручка?', 'Что известно о прибыли?', 'Каких финансовых данных не хватает?'],
  courts: ['В какой роли компания в судах?', 'Какова сумма требований?', 'Что проверить в судебных актах?'],
  enforcement: ['Сколько активных производств?', 'Известна ли их сумма?', 'Как это может повлиять на обязательства?'],
  registries: ['Каких реестровых данных нет?', 'Можно ли считать пустое поле хорошим знаком?', 'Какие косвенные признаки проверить?'],
  activity: ['Какой основной ОКВЭД?', 'Совпадает ли он с предметом сделки?', 'Что ещё проверить по деятельности?'],
};

