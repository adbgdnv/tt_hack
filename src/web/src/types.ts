export type Signal = 'green' | 'yellow' | 'red' | 'unknown';

export type BlockKey =
  | 'registration'
  | 'finances'
  | 'courts'
  | 'enforcement'
  | 'registries'
  | 'activity';

export type FinancialPoint = {
  year: number;
  revenue: number;
  profit: number;
};

export type ReportBlock = {
  key: BlockKey;
  title: string;
  signal: Signal;
  preview: string[];
  details: Array<{ label: string; value: string }>;
  analysis: string;
  source: string;
  empty?: boolean;
  notApplicable?: boolean;
  workaround?: string;
};

export type Counterparty = {
  name: string;
  inn: string;
  director: string;
  legalForm: 'legal' | 'entrepreneur';
  status: 'Действующее' | 'Ликвидировано';
  /** Скоринг банка. «Нет данных» — отдельное состояние: оценить невозможно, а не низкий риск. */
  bankRisk: 'Низкий' | 'Средний' | 'Высокий' | 'Нет данных';
  /** Платформа ЗСК Банка России. Это другая организация, не банковский скоринг. */
  bankLight: 'Зелёный' | 'Жёлтый' | 'Красный' | 'Нет данных';
  dataDate: string;
  dateIso: string;
  negativeFactors: string[];
  summary: string;
  questions: string[];
  financials?: FinancialPoint[];
  blocks: Record<BlockKey, ReportBlock>;
};

export type Proof = {
  value: string;
  label: string;
  source: string;
  block: BlockKey;
};

export type AgentAnswer = {
  fact: string;
  interpretation: string;
  gap: string;
  next: string;
  proofs: Proof[];
};

export type ChatMessage =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'agent'; text: string; answer: AgentAnswer };

export type HistoryItem = Pick<Counterparty, 'name' | 'inn' | 'bankRisk' | 'dataDate'>;

// ─────────── Собранный отчёт: приходит с сервера готовым ───────────
// Интерфейс его отображает, а не собирает. Правило «что важнее» — доменное знание,
// и держать вторую его реализацию здесь значит гарантированно разойтись с сервером.

/** Четыре разных «пусто». Смешивать их — значит выдавать «мы не знаем» за «всё чисто». */
export type SectionState = 'signal' | 'filled' | 'empty' | 'not_applicable';

export type ReportFactor = {
  code: string;
  /** Короткий заголовок для карточки. */
  heading: string;
  /** Текст из выгрузки кейсодателя, дословно. */
  explanation: string;
  weight: number;
};

export type ReportFact = {
  label: string;
  value: string | number;
  /** 'money' форматируется компонентом дизайн-системы, а не вручную.
   *  'ratio' — коэффициент источника, показывается как есть, без толкования. */
  kind: 'text' | 'count' | 'money' | 'ratio';
  /** Изменение к предыдущему году долей: 0.16 это +16%.
   *  Отсутствует, когда сравнивать не с чем — это не то же самое, что «не изменилось». */
  delta?: number | null;
  /** С чем сравнили — «к 2024». */
  delta_note?: string;
};

export type ReportSectionData = {
  key: string;
  title: string;
  state: SectionState;
  /** Формулировка сервера; UI может заменить её на согласованный продуктовый текст. */
  note: string;
  factors: ReportFactor[];
  /** То, что пользователь может сверить с источником. */
  facts: ReportFact[];
  /** Графики раздела. Пустой список означает, что данных на график не хватило. */
  charts: ChartSpec[];
  /** Почему графика нет. Пусто, когда график есть или когда его тут не бывает. */
  charts_note: string;
  /** Сколько проверок раздела источник провёл и сколько компания прошла.
   *  «0 из 0» означает, что раздел не проверялся вовсе — это не то же самое,
   *  что «проверен и ничего не нашлось».
   *
   *  Поля необязательны, и отсутствие значимо: разделы, собранные на клиенте
   *  при недоступном сервере, про проверки не знают ничего. Утверждать там
   *  «источник не проверял» значило бы выдавать сбой связи за факт о компании. */
  checks_passed?: number;
  checks_total?: number;
  /** Названия пройденных проверок — только для детального вида. */
  passed_checks?: string[];
};

export type RiskAssessment = {
  /** Чья это оценка — банка или платформы ЗСК Банка России. */
  source: string;
  value: string;
  /** false означает «оценить невозможно» — не низкий риск и не высокий. */
  known: boolean;
};

/**
 * Противоречие между разделами отчёта.
 *
 * Пути внутри данных сюда не приходят намеренно: ими триггер проверяется
 * на сервере, а на экране пользователь видит слова.
 */
export type ReportTrigger = {
  key: string;
  title: string;
  explanation: string;
  /** Значения, из которых сложилось, уже отформатированные сервером. */
  evidence: string[];
  /** Раздел отчёта, где это можно проверить. */
  section: string;
  weight: number;
  tags: string[];
};

export type CounterpartyReport = {
  inn: string;
  name: string;
  is_entrepreneur: boolean;
  status: string;
  registered: string | null;
  years: number | null;
  bank_risk: RiskAssessment;
  zsk_risk: RiskAssessment;
  /** UI выводит разделы в постоянном порядке из UX-спеки. */
  sections: ReportSectionData[];
  unknown_chapters: string[];
  signals: number;
  unknowns: number;
  /** Необязательно: сервер постарше о противоречиях не знает. */
  triggers?: ReportTrigger[];
};

// ─────────── Описания графиков: приходят с сервера вместе с отчётом ───────────
// Описание говорит, что показать. Чем рисовать — забота интерфейса.

export type ChartSeries = {
  name: string;
  unit: string;
  /** Соответствуют подписям оси один к одному. null — год без данных, а не ноль. */
  values: Array<number | null>;
};

export type ChartSpec = {
  key: string;
  title: string;
  /** 'lines' — ряд по годам, 'bars' — сравнение величин. */
  form: 'lines' | 'bars';
  labels: string[];
  series: ChartSeries[];
  /** Поля отчёта, из которых построено — пользователь может проверить цифру. */
  source: string;
};

// ─────────── Блоки сообщения ассистента ───────────
// Сообщение — упорядоченная последовательность блоков, а не текст с довесками
// по краям. Порядок не вычисляется: блок вызова открывается в момент события,
// поэтому «текст → вызов → текст» складывается сам.
//
// Прежняя схема держала три отдельных списка — отметки о вызовах, графики,
// ссылки — и рисовала каждый в своём фиксированном месте. Один вызов оказывался
// разорван между началом и концом сообщения, а порядок терялся безвозвратно.

/**
 * Исход вызова. Четыре состояния, а не два: поток рвётся между началом
 * и концом вызова, и без «прервано» такой вызов крутился бы вечно.
 *
 * «Не удался» и «прервано» различаются намеренно: в первом случае инструмент
 * ответил отказом, во втором неизвестно, выполнился ли он вообще.
 */
export type ToolState = 'running' | 'ok' | 'failed' | 'aborted';

export type ToolSource = { title: string; url: string; snippet?: string };

/** Вызов инструмента вместе со своим результатом. Результат принадлежит вызову,
 *  а не концу сообщения. */
export type ToolCall = {
  tool: string;
  /** Фраза для человека: «Строю график „Суммы исков по годам"». */
  title: string;
  state: ToolState;
  /** Ключ графика. Данные интерфейс берёт из загруженного отчёта — так числа
   *  в чате не могут разойтись с дашбордом. */
  chart?: string;
  sources?: ToolSource[];
  /** Данные, взятые по теме. Показываются целиком: модель не должна видеть
   *  того, чего не видит пользователь, иначе ответ станет нечем сверить. */
  lookup?: { topic: string; text: string };
};

/**
 * Итог сверки чисел ответа с отчётом.
 *
 * «Не выдумывает» — критерий приёмки кейса, и до сих пор он держался
 * на формулировках промпта. `total` ноль значит «проверять было нечего»,
 * а не «подтверждено»: ответ без чисел проверка не покрывает.
 */
export type AnswerCheck = {
  total: number;
  unverified: { number: string; context: string }[];
  /** Обращались ли к модели за второй ступенью. */
  checked: boolean;
};

export type MessageBlock =
  | { kind: 'text'; text: string }
  | { kind: 'tool'; call: ToolCall };


// ─────────── Новости из внешних источников ───────────
// Отдельный слой, а не часть отчёта: кейсодатель задал иерархию источников
// дословно — найденное снаружи всегда со ссылкой и всегда отдельно от фактов
// отчёта, смешивать их нельзя.

export type NewsLevel = 'тревожная' | 'нейтральная' | '';

export type NewsItem = {
  title: string;
  url: string;
  /** Одна фраза словами источника. Оценку модель не добавляет. */
  summary: string;
  level: NewsLevel;
};

export type CompanyNews = {
  items: NewsItem[];
  level: NewsLevel;
  /** Внешний источник не ответил. Это не то же самое, что «новостей нет». */
  failed: boolean;
  checked_at: number;
};
