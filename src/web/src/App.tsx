import { Suspense, lazy, useEffect, useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { IconButtonDesktop } from '@alfalab/core-components-icon-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { Skeleton } from '@alfalab/core-components-skeleton';
import { Status } from '@alfalab/core-components-status';
import { ToastPlateDesktop } from '@alfalab/core-components-toast-plate/desktop';
import { TooltipDesktop } from '@alfalab/core-components-tooltip/desktop';
import { DocumentPdfMIcon } from '@alfalab/icons-glyph/DocumentPdfMIcon';
import { ShareMIcon } from '@alfalab/icons-glyph/ShareMIcon';
import { getCounterparty, getReport, searchCounterparties } from './api';
import type { BlockKey, Counterparty, CounterpartyReport, HistoryItem, ReportBlock, ReportSectionData } from './types';
import { BlockModal } from './components/BlockModal';
import { Brand } from './components/Brand';
// Отложенно: чат нужен только на экране компании, а тянет за собой разбор
// разметки — 51 КБ в сжатии. На первом экране это чистый простой.
// Ожидание срабатывает один раз при открытии компании, а не на каждое слово
// ответа: разбиение по самой разметке дало бы мигание прямо во время печати.
const ChatPanel = lazy(() =>
  import('./components/ChatPanel').then((module) => ({ default: module.ChatPanel })),
);
import { ReportSection } from './components/ReportSection';

const HISTORY_KEY = 'counterparty-check-history-v1';
const blockOrder: BlockKey[] = ['registration', 'finances', 'courts', 'enforcement', 'registries', 'activity'];
const reportSectionOrder = ['registration', 'finances', 'courts', 'enforcement', 'registries', 'activity', 'management', 'related'];

function readHistory(): HistoryItem[] {
  try {
    const stored = window.localStorage.getItem(HISTORY_KEY);
    return stored ? (JSON.parse(stored) as HistoryItem[]) : [];
  } catch {
    return [];
  }
}

function writeHistory(history: HistoryItem[]) {
  try {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {
    // История необязательна: приватный режим не должен ломать основной flow.
  }
}

const signalLabels = {
  green: 'Нейтральная значимость · значимых сигналов нет',
  yellow: 'Средняя значимость · негативное направление',
  red: 'Высокая значимость · негативное направление',
  unknown: 'Недостаточно данных',
};

function AppHeader({ compact, onHome }: { compact?: boolean; onHome?: () => void }) {
  return (
    <header className={'app-header' + (compact ? ' app-header--compact' : '')}>
      <Brand onHome={onHome} />
      <span className="app-header__product">Проверка контрагента</span>
      <span className="app-header__prototype">Прототип</span>
    </header>
  );
}

function DashboardSkeleton() {
  return (
    <main className="page dashboard-page" aria-label="Загрузка отчёта">
      <div className="skeleton-title"><Skeleton visible animate><div>Загружаем название компании</div></Skeleton></div>
      <div className="dashboard-layout">
        <section className="blocks-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} visible animate borderRadius={16}>
              <div className="block-skeleton">Загрузка данных блока отчёта</div>
            </Skeleton>
          ))}
        </section>
        <Skeleton visible animate borderRadius={16}>
          <div className="chat-skeleton">Загрузка панели разбора</div>
        </Skeleton>
      </div>
    </main>
  );
}

function RiskBlockCard({ block, onOpen }: { block: ReportBlock; onOpen: () => void }) {
  return (
    <button className="block-card" type="button" onClick={onOpen}>
      <div className="block-card__top">
        <div className="block-card__title">
          <span className={'signal signal--' + block.signal} aria-hidden="true" />
          <h3>{block.title}</h3>
        </div>
        <TooltipDesktop content="Ориентир на основе данных блока, не банковская оценка" position="top">
          <span className="info-dot" aria-label="Что означает индикатор блока" onClick={(event) => event.stopPropagation()}>i</span>
        </TooltipDesktop>
      </div>
      <span className="block-card__signal">{signalLabels[block.signal]}</span>
      <ul>
        {block.preview.slice(0, 2).map((fact) => <li key={fact}>{fact}</li>)}
      </ul>
      <span className="block-card__action">Разобрать <span aria-hidden="true">→</span></span>
    </button>
  );
}

function HomeScreen({ query, setQuery, suggestions, searching, notFound, loadFailed, history, homeChat, setHomeChat, onSearch, onSelect }: {
  query: string;
  setQuery: (value: string) => void;
  suggestions: Counterparty[];
  searching: boolean;
  notFound: boolean;
  loadFailed: boolean;
  history: HistoryItem[];
  homeChat: boolean;
  setHomeChat: (value: boolean) => void;
  onSearch: () => void;
  onSelect: (inn: string) => void;
}) {
  return (
    <>
      <AppHeader />
      <main className="home page">
        <section className="hero">
          <span className="static-label static-label--hero">Для вашего бизнеса</span>
          <h1>Проверьте контрагента<br />до начала работы</h1>
          <p>Получите факты и цифры из отчёта, узнайте, на что обратить внимание, и разберите сложные сведения простым языком.</p>
          <form className="search" onSubmit={(event) => { event.preventDefault(); onSearch(); }}>
            <div className="search__control">
              <InputDesktop
                size={56}
                block
                clear="auto"
                label="ИНН, название или ФИО руководителя"
                labelView="inner"
                value={query}
                onChange={(_, payload) => setQuery(payload.value)}
                inputMode="search"
                aria-label="Поиск по ИНН, названию или ФИО руководителя"
              />
              <ButtonDesktop type="submit" view="accent" size={56} loading={searching}>Проверить</ButtonDesktop>
            </div>
            {suggestions.length > 0 && !searching && (
              <div className="suggestions" role="listbox" aria-label="Подсказки поиска">
                {suggestions.map((item) => (
                  <button key={item.inn} type="button" role="option" onClick={() => onSelect(item.inn)}>
                    <span><strong>{item.name}</strong><small>{item.director}</small></span>
                    <em>ИНН {item.inn}</em>
                  </button>
                ))}
              </div>
            )}
            {searching && <div className="inline-loader"><span />Ищем компанию во входных данных…</div>}
            {notFound && (
              <div className="inline-error" role="status">
                <strong>Компании по этому ИНН не существует</strong>
                <span>Проверьте цифры или введите другой ИНН. Поиск остаётся доступен.</span>
              </div>
            )}
            {loadFailed && (
              <div className="inline-error" role="status">
                <strong>Не удалось получить данные</strong>
                <span>Это сбой сервиса, а не утверждение о компании — про неё мы сейчас ничего сказать не можем. Попробуйте ещё раз.</span>
              </div>
            )}
          </form>
        </section>

        {history.length === 0 ? (
          <section className="onboarding">
            <div className="onboarding__copy">
              <span className="eyebrow">Как это работает</span>
              <h2>От ИНН до понятных следующих шагов</h2>
              <div className="steps">
                <div><b>1</b><span><strong>Находим отчёт</strong><small>Только во входных данных</small></span></div>
                <div><b>2</b><span><strong>Показываем факты</strong><small>Без нового общего скоринга</small></span></div>
                <div><b>3</b><span><strong>Помогаем проверить</strong><small>С пруфами и источниками</small></span></div>
              </div>
              <ButtonDesktop size={48} view="secondary" onClick={() => setHomeChat(!homeChat)}>
                {homeChat ? 'Скрыть подсказку' : 'Открыть чат'}
              </ButtonDesktop>
            </div>
            <div className="onboarding__visual">
              <span className="ai-mark ai-mark--large">AI</span>
              <h3>Не знаете, с чего начать?</h3>
              <p>{homeChat ? 'Введите ИНН или название. На дашборде я предложу три вопроса по самым заметным фактам и отвечу только по отчёту.' : 'Ассистент подскажет вопросы после выбора компании.'}</p>
              <div className="mini-proof"><strong>54</strong><span>активных производства</span><span className="static-label">ФССП · дата</span></div>
            </div>
          </section>
        ) : (
          <section className="history">
            <div className="section-heading">
              <div><span className="eyebrow">История</span><h2>Недавние проверки</h2></div>
            </div>
            <div className="history-grid">
              {history.map((item) => (
                <button className="history-card" key={item.inn} type="button" onClick={() => onSelect(item.inn)}>
                  <Status size={20} view="soft" color={riskColor(item.bankRisk)}>{historyRiskLabel(item.bankRisk)}</Status>
                  <h3>{item.name}</h3>
                  <p>ИНН {item.inn}</p>
                  <div><time>{item.dataDate}</time></div>
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
    </>
  );
}

/** Цвет индикатора. Отсутствие оценки — серый, а не зелёный:
 *  «оценить невозможно» и «всё хорошо» — разные утверждения. */
function riskColor(value: string): 'green' | 'orange' | 'red' | 'grey' {
  if (value === 'Красный' || value === 'Высокий') return 'red';
  if (value === 'Жёлтый' || value === 'Средний') return 'orange';
  if (value === 'Зелёный' || value === 'Низкий') return 'green';
  return 'grey';
}

function historyRiskLabel(value: Counterparty['bankRisk']): string {
  return value === 'Нет данных' ? value : `${value} риск`;
}

function orderedSections(sections: ReportSectionData[]): ReportSectionData[] {
  const rank = new Map(reportSectionOrder.map((key, index) => [key, index]));
  return [...sections].sort((left, right) =>
    (rank.get(left.key) ?? reportSectionOrder.length) - (rank.get(right.key) ?? reportSectionOrder.length));
}

function headerFacts(company: Counterparty, report: CounterpartyReport | null) {
  const labels = /^(Юридический адрес|Адрес|Телефон|Контакт|Контакты|Сайт|Веб-сайт|E-mail|Электронная почта)$/i;
  const reportFacts = report?.sections.find((section) => section.key === 'registration')?.facts ?? [];
  const fromReport = reportFacts.filter((fact) => labels.test(fact.label));
  if (fromReport.length > 0) return fromReport.map((fact) => ({ label: fact.label, value: String(fact.value) }));
  return company.blocks.registration.details.filter((fact) => labels.test(fact.label));
}

function Dashboard({ company, report, openedSection, highlighted, onHome, onOpenBlock, onCloseBlock, onToast }: {
  company: Counterparty;
  report: CounterpartyReport | null;
  openedSection: string | null;
  highlighted: boolean;
  onHome: () => void;
  onOpenBlock: (key: string, proof?: boolean) => void;
  onCloseBlock: () => void;
  onToast: (message: string) => void;
}) {
  const contactFacts = headerFacts(company, report);
  const bankKnown = report ? report.bank_risk.known : company.bankRisk !== 'Нет данных';
  const bankValue = report?.bank_risk.value ?? company.bankRisk;
  const zskKnown = report ? report.zsk_risk.known : company.bankLight !== 'Нет данных';
  const zskValue = report?.zsk_risk.value ?? company.bankLight;
  const sections = orderedSections(report?.sections ?? []);

  return (
    <>
      <AppHeader compact onHome={onHome} />
      <main className="page dashboard-page">
        <div className="dashboard-layout">
          <section className="dashboard-main">
            <button className="back-link" type="button" onClick={onHome}>← Новый поиск</button>
            <section className="company-header">
              <div className="company-header__identity">
                <div className="company-status-row">
                  <span className="static-label">{company.status}</span>
                  <span>ИНН {company.inn}</span>
                </div>
                <h1>{company.name}</h1>
                <p>Данные отчёта на {company.dataDate}</p>
                {contactFacts.length > 0 && (
                  <dl className="company-header__contacts">
                    {contactFacts.map((fact) => (
                      <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>
                    ))}
                  </dl>
                )}
              </div>
              <div className="bank-signal">
                <div className="bank-signal__primary">
                  <span>Оценка банка:</span>
                  <Status size={24} view="soft" color={bankKnown ? riskColor(bankValue) : 'grey'}>
                    {bankKnown ? bankValue : 'Оценить невозможно'}
                  </Status>
                </div>
                <span className="bank-signal__method">
                  {report?.bank_risk.source ?? 'Скоринг банка'} · методология скоринга не раскрывается
                </span>
                <div className="bank-signal__secondary">
                  <span>Платформа ЗСК (Банк России):</span>
                  <Status size={20} view="soft" color={zskKnown ? riskColor(zskValue) : 'grey'}>
                    {zskKnown ? zskValue : 'Оценить невозможно'}
                  </Status>
                </div>
                <p>Это независимые источники. Сервис показывает их оценки без пересчёта.</p>
              </div>
              <div className="report-actions">
                {/* Печать средствами браузера: он же даёт и сохранение в файл.
                    Генерация PDF на сервере — отдельная зависимость ради кнопки. */}
                <TooltipDesktop content="Сохранить в PDF" position="top">
                  <IconButtonDesktop size={40} view="secondary" icon={DocumentPdfMIcon} aria-label="Сохранить в PDF" onClick={() => window.print()} />
                </TooltipDesktop>
                <TooltipDesktop content="Скопировать ссылку на отчёт" position="top">
                  <IconButtonDesktop
                    size={40}
                    view="secondary"
                    icon={ShareMIcon}
                    aria-label="Скопировать ссылку на отчёт"
                    onClick={() => {
                      const url = `${window.location.origin}${window.location.pathname}?inn=${company.inn}`;
                      navigator.clipboard
                        .writeText(url)
                        .then(() => onToast('Ссылка на отчёт скопирована'))
                        .catch(() => onToast('Не удалось скопировать — скопируйте адрес из строки браузера'));
                    }}
                  />
                </TooltipDesktop>
              </div>
            </section>

            <div className="dashboard-content">
              {openedSection ? (
                <BlockModal
                  company={company}
                  report={report}
                  blockKey={openedSection}
                  highlighted={highlighted}
                  onClose={onCloseBlock}
                  onOpenBlock={onOpenBlock}
                />
              ) : (
                <>
                  <div className="blocks-heading">
                    <div>
                      <span className="eyebrow">Данные отчёта</span>
                      <h2>Разделы проверки</h2>
                    </div>
                    <TooltipDesktop content="Порядок разделов постоянный. Недостаток данных не означает отсутствие рисков">
                      <span className="indicator-legend">Как читать разделы</span>
                    </TooltipDesktop>
                  </div>

                  {report && report.signals === 0 && (
                    <p className="report-clean">
                      По доступным данным значимых сигналов не обнаружено.
                      {report.unknowns > 0 && ` Недостаточно данных по разделам: ${report.unknowns}.`}
                    </p>
                  )}

                  <div className="report-sections">
                    {report
                      ? sections.map((section) => (
                        <ReportSection key={section.key} section={section} onOpen={() => onOpenBlock(section.key)} />
                      ))
                      : blockOrder.map((key) => <RiskBlockCard key={key} block={company.blocks[key]} onOpen={() => onOpenBlock(key)} />)}
                  </div>
                </>
              )}
            </div>
          </section>
          <Suspense fallback={<aside className="chat-panel" aria-hidden="true" />}>
            <ChatPanel report={report} onToast={onToast} />
          </Suspense>
        </div>
      </main>
    </>
  );
}

export default function App() {
  const [view, setView] = useState<'home' | 'dashboard'>('home');
  const [query, setQueryState] = useState('');
  const [suggestions, setSuggestions] = useState<Counterparty[]>([]);
  const [searching, setSearching] = useState(false);
  const [notFound, setNotFound] = useState(false);
  // Сбой связи — не утверждение о компании. Смешивать их нельзя:
  // «сервис недоступен» и «такой компании нет» это разные ответы.
  const [loadFailed, setLoadFailed] = useState(false);
  const [company, setCompany] = useState<Counterparty | null>(null);
  // Собранный отчёт с сервера. null означает «сервер недоступен» —
  // тогда показываются заготовленные примеры как запасной путь.
  const [report, setReport] = useState<CounterpartyReport | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>(readHistory);
  const [homeChat, setHomeChat] = useState(false);
  const [modalBlock, setModalBlock] = useState<string | null>(null);

  // Открытие адреса с ИНН ведёт к тому же отчёту — иначе постоянная ссылка бессмысленна.
  useEffect(() => {
    const inn = new URLSearchParams(window.location.search).get('inn');
    if (inn) void openCompany(inn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [highlighted, setHighlighted] = useState(false);
  const [toast, setToast] = useState('');
  const [compare, setCompare] = useState<HistoryItem[]>([]);

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const result = await searchCounterparties(query);
        if (active) setSuggestions(result);
      } catch {
        if (active) setSuggestions([]);
      }
    }, 160);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(''), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const setQuery = (value: string) => {
    setQueryState(value);
    setNotFound(false);
  };

  const openCompany = async (inn: string) => {
    setQueryState(inn);
    setSuggestions([]);
    setNotFound(false);
    setLoadFailed(false);
    setReport(null);
    setSearching(true);
    setView('dashboard');
    setCompany(null);
    try {
      const found = await getCounterparty(inn);
      if (!found) {
        setView('home');
        setNotFound(true);
        return;
      }
      setCompany(found);
      setModalBlock(null);
      // Отчёт получает собственный адрес: без него кнопка «Ссылка» копировала бы
      // адрес поиска, то есть врала.
      window.history.replaceState(null, '', `?inn=${encodeURIComponent(inn)}`);
      // Отчёт грузится отдельно: его отсутствие не должно ронять экран целиком.
      getReport(inn).then((r) => setReport(r ?? null)).catch(() => setReport(null));
      const item: HistoryItem = { name: found.name, inn: found.inn, bankRisk: found.bankRisk, dataDate: found.dataDate };
      const nextHistory = [item, ...history.filter((entry) => entry.inn !== found.inn)].slice(0, 6);
      setHistory(nextHistory);
      writeHistory(nextHistory);
    } catch {
      setView('home');
      setLoadFailed(true);
    } finally {
      setSearching(false);
    }
  };

  const submitSearch = async () => {
    const known = suggestions.find((item) => item.inn === query.trim()) ?? suggestions[0];
    if (known) {
      await openCompany(known.inn);
      return;
    }
    const digits = query.replace(/\D/g, '');
    if (digits.length === 10 || digits.length === 12) {
      await openCompany(digits);
      return;
    }
    setSearching(true);
    try {
      const matches = await searchCounterparties(query);
      if (matches[0]) await openCompany(matches[0].inn);
      else setNotFound(true);
    } catch {
      setNotFound(true);
    } finally {
      setSearching(false);
    }
  };

  const openBlock = (key: string, proof = false) => {
    setHighlighted(proof);
    setModalBlock(key);
    window.scrollTo({ top: 0 });
  };

  const goHome = () => {
    setView('home');
    setCompany(null);
    setModalBlock(null);
    setQueryState('');
  };

  const addCompare = () => {
    if (!company || compare.some((item) => item.inn === company.inn) || compare.length >= 2) return;
    setCompare((current) => [...current, { name: company.name, inn: company.inn, bankRisk: company.bankRisk, dataDate: company.dataDate }]);
    setToast('Компания добавлена в сравнение');
  };

  return (
    <div className="app-shell">
      {view === 'home' ? (
        <HomeScreen
          query={query}
          setQuery={setQuery}
          suggestions={suggestions}
          searching={searching}
          notFound={notFound}
          loadFailed={loadFailed}
          history={history}
          homeChat={homeChat}
          setHomeChat={setHomeChat}
          onSearch={submitSearch}
          onSelect={(inn) => void openCompany(inn)}
        />
      ) : company ? (
        <Dashboard
          company={company}
          report={report}
          openedSection={modalBlock}
          highlighted={highlighted}
          onHome={goHome}
          onOpenBlock={openBlock}
          onCloseBlock={() => { setModalBlock(null); setHighlighted(false); window.scrollTo({ top: 0 }); }}
          onToast={setToast}
        />
      ) : <><AppHeader compact onHome={goHome} /><DashboardSkeleton /></>}

      {compare.length > 0 && (
        <div className="compare-bar">
          <span>В сравнении: <strong>{compare.length}</strong> из 2</span>
          <span>{compare.map((item) => item.name).join(' · ')}</span>
          <ButtonDesktop size={40} view="secondary" onClick={() => setToast('Экран сравнения — TBU')}>Сравнить</ButtonDesktop>
          <button type="button" aria-label="Очистить сравнение" onClick={() => setCompare([])}>×</button>
        </div>
      )}

      {toast && (
        <div className="toast-wrap" role="status">
          <ToastPlateDesktop title={toast} badge="positive-checkmark" closerProps={{ hasCloser: true }} onClose={() => setToast('')} />
        </div>
      )}
    </div>
  );
}
