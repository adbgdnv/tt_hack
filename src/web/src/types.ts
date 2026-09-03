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
