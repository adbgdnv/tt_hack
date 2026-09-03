import { useEffect, useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { Skeleton } from '@alfalab/core-components-skeleton';
import { Tag } from '@alfalab/core-components-tag';
import { ToastPlateDesktop } from '@alfalab/core-components-toast-plate/desktop';
import { TooltipDesktop } from '@alfalab/core-components-tooltip/desktop';
import { getCounterparty, searchCounterparties } from './api';
import { humanFactorLabels } from './fixtures';
import type { BlockKey, Counterparty, HistoryItem, ReportBlock } from './types';
import { BlockModal } from './components/BlockModal';
import { ChatPanel } from './components/ChatPanel';
import { FinancialChart } from './components/FinancialChart';

const HISTORY_KEY = 'counterparty-check-history-v1';
const blockOrder: BlockKey[] = ['registration', 'finances', 'courts', 'enforcement', 'registries', 'activity'];

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
  green: 'Без заметных негативных фактов',
  yellow: 'Требует внимания',
  red: 'Есть значимые факты',
  unknown: 'Данных недостаточно',
};

function AppHeader({ compact, onHome }: { compact?: boolean; onHome?: () => void }) {
  return (
    <header className={'app-header' + (compact ? ' app-header--compact' : '')}>
      <button className="brand" type="button" onClick={onHome} aria-label="На главную">
        <span className="brand__mark">A</span>
        <span className="brand__name">АЛЬФА-БАНК</span>
      </button>
      <div className="app-header__product">
        Проверка контрагента
        <Tag size={32} view="muted">Прототип</Tag>
      </div>
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

function HomeScreen({ query, setQuery, suggestions, searching, notFound, history, homeChat, setHomeChat, onSearch, onSelect }: {
  query: string;
  setQuery: (value: string) => void;
  suggestions: Counterparty[];
  searching: boolean;
  notFound: boolean;
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
          <Tag size={32} view="muted">Для малого бизнеса</Tag>
          <h1>Проверьте контрагента<br />до важного решения</h1>
          <p>Соберём факты из отчёта, покажем, на что обратить внимание, и объясним простым языком.</p>
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
          </form>
          <div className="v2-note">Поиск в ЕГРЮЛ и уведомление об обновлении данных — V2</div>
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
              <div className="mini-proof"><strong>54</strong><span>активных производства</span><Tag size={32} view="muted">ФССП · дата</Tag></div>
            </div>
          </section>
        ) : (
          <section className="history">
            <div className="section-heading">
              <div><span className="eyebrow">История</span><h2>Недавние проверки</h2></div>
              <span>{history.length} {history.length === 1 ? 'компания' : 'компании'}</span>
            </div>
            <div className="history-grid">
              {history.map((item) => (
                <button className="history-card" key={item.inn} type="button" onClick={() => onSelect(item.inn)}>
                  <span className="bank-dot bank-dot--green" />
                  <h3>{item.name}</h3>
                  <p>ИНН {item.inn}</p>
                  <div><span>Банковский риск: {item.bankRisk.toLowerCase()}</span><time>{item.dataDate}</time></div>
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
    </>
  );
}

function Dashboard({ company, onHome, onOpenBlock, chatContext, onToast, onAddCompare, compareCount, compared }: {
  company: Counterparty;
  onHome: () => void;
  onOpenBlock: (key: BlockKey, proof?: boolean) => void;
  chatContext: BlockKey | null;
  onToast: (message: string) => void;
  onAddCompare: () => void;
  compareCount: number;
  compared: boolean;
}) {
  return (
    <>
      <AppHeader compact onHome={onHome} />
      <main className="page dashboard-page">
        <button className="back-link" type="button" onClick={onHome}>← Новый поиск</button>
        <section className="company-header">
          <div className="company-header__identity">
            <div className="company-status-row">
              <Tag size={32} view="muted">{company.status}</Tag>
              <span>ИНН {company.inn}</span>
            </div>
            <h1>{company.name}</h1>
            <p>Данные отчёта на {company.dataDate}</p>
          </div>
          <div className="bank-signal">
            <div className="bank-signal__head"><span>Банковская оценка</span><span className="source-of-truth">Источник истины</span></div>
            <div className="bank-signal__value"><span className={'bank-dot bank-dot--' + (company.bankLight === 'Красный' ? 'red' : company.bankLight === 'Жёлтый' ? 'yellow' : 'green')} />{company.bankRisk} риск</div>
            <div className="bank-signal__meta"><span>ЗСК: {company.bankLight}</span><time>Расчёт {company.dataDate}</time></div>
          </div>
          <div className="report-actions">
            <ButtonDesktop size={40} view="secondary" onClick={() => onToast('PDF-снимок отчёта сохранён')}>↓ PDF</ButtonDesktop>
            <ButtonDesktop size={40} view="secondary" onClick={() => onToast('Постоянная ссылка скопирована')}>↗ Ссылка</ButtonDesktop>
            <ButtonDesktop size={40} view="outlined" disabled={compared || compareCount >= 2} onClick={onAddCompare}>
              {compared ? '✓ В сравнении' : '+ Сравнить'}
            </ButtonDesktop>
          </div>
        </section>

        {company.negativeFactors.length > 0 && (
          <section className="factor-strip">
            <span>Факторы во входных данных</span>
            <div>{company.negativeFactors.map((factor) => <Tag key={factor} size={32} view="muted">{humanFactorLabels[factor] ?? factor}</Tag>)}</div>
          </section>
        )}

        <div className="dashboard-layout">
          <section>
            <div className="blocks-heading">
              <div><span className="eyebrow">Данные отчёта</span><h2>На что обратить внимание</h2></div>
              <TooltipDesktop content="Каждый индикатор — ориентир на основе данных своего блока, не банковская оценка">
                <span className="indicator-legend"><span className="signal signal--yellow" /> Как читать индикаторы</span>
              </TooltipDesktop>
            </div>
            <div className="blocks-grid">
              {blockOrder.map((key) => <RiskBlockCard key={key} block={company.blocks[key]} onOpen={() => onOpenBlock(key)} />)}
            </div>
            {company.financials && (
              <section className="finance-card">
                <div className="finance-card__heading">
                  <div><span className="eyebrow">Финансы</span><h2>Динамика показателей</h2></div>
                  <ButtonDesktop size={40} view="secondary" onClick={() => onOpenBlock('finances')}>Подробнее</ButtonDesktop>
                </div>
                <FinancialChart data={company.financials} />
                {company.inn === '7716512345' && <p className="finance-gap"><strong>Пробел:</strong> бухгалтерская отчётность за 2025 год не представлена.</p>}
              </section>
            )}
          </section>
          <ChatPanel company={company} contextBlock={chatContext} onOpenProof={(key) => onOpenBlock(key, true)} onToast={onToast} />
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
  const [company, setCompany] = useState<Counterparty | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>(readHistory);
  const [homeChat, setHomeChat] = useState(false);
  const [modalBlock, setModalBlock] = useState<BlockKey | null>(null);
  const [chatContext, setChatContext] = useState<BlockKey | null>(null);
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
      setChatContext(null);
      const item: HistoryItem = { name: found.name, inn: found.inn, bankRisk: found.bankRisk, dataDate: found.dataDate };
      const nextHistory = [item, ...history.filter((entry) => entry.inn !== found.inn)].slice(0, 6);
      setHistory(nextHistory);
      writeHistory(nextHistory);
    } catch {
      setView('home');
      setNotFound(true);
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

  const openBlock = (key: BlockKey, proof = false) => {
    setChatContext(key);
    setHighlighted(proof);
    setModalBlock(key);
  };

  const goHome = () => {
    setView('home');
    setCompany(null);
    setModalBlock(null);
    setChatContext(null);
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
          history={history}
          homeChat={homeChat}
          setHomeChat={setHomeChat}
          onSearch={submitSearch}
          onSelect={(inn) => void openCompany(inn)}
        />
      ) : company ? (
        <Dashboard
          company={company}
          onHome={goHome}
          onOpenBlock={openBlock}
          chatContext={chatContext}
          onToast={setToast}
          onAddCompare={addCompare}
          compareCount={compare.length}
          compared={compare.some((item) => item.inn === company.inn)}
        />
      ) : <><AppHeader compact onHome={goHome} /><DashboardSkeleton /></>}

      {company && (
        <BlockModal
          company={company}
          blockKey={modalBlock}
          highlighted={highlighted}
          onClose={() => { setModalBlock(null); setHighlighted(false); }}
          onOpenBlock={(key) => { setHighlighted(false); openBlock(key); }}
        />
      )}

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
