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
  /** 'money' форматируется компонентом дизайн-системы, а не вручную. */
  kind: 'text' | 'count' | 'money';
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
};

export type RiskAssessment = {
  /** Чья это оценка — банка или платформы ЗСК Банка России. */
  source: string;
  value: string;
  /** false означает «оценить невозможно» — не низкий риск и не высокий. */
  known: boolean;
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
