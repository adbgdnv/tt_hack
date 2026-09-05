import type { ReactNode } from 'react';
import { Suspense, lazy, useEffect, useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { IconButtonDesktop } from '@alfalab/core-components-icon-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { Skeleton } from '@alfalab/core-components-skeleton';
import { Status } from '@alfalab/core-components-status';
import { ToastPlateDesktop } from '@alfalab/core-components-toast-plate/desktop';
import { TooltipDesktop } from '@alfalab/core-components-tooltip/desktop';
import { Typography } from '@alfalab/core-components-typography';
import { DocumentPdfMIcon } from '@alfalab/icons-glyph/DocumentPdfMIcon';
import { ShareMIcon } from '@alfalab/icons-glyph/ShareMIcon';
import { compareCounterparties, getCounterparty, getNews, getReport, sectionsFromCompany, searchCounterparties, datasetDate } from './api';
import type { CompanyNews, CompareResult, Counterparty, CounterpartyReport, HistoryItem, ReportSectionData } from './types';
import { deriveVerdict } from './verdict';
import { Brand } from './components/Brand';
// Отложенно: чат нужен только на экране компании, а тянет за собой разбор
// разметки — 51 КБ в сжатии. На первом экране это чистый простой.
// Ожидание срабатывает один раз при открытии компании, а не на каждое слово
// ответа: разбиение по самой разметке дало бы мигание прямо во время печати.
const ChatPanel = lazy(() =>
  import('./components/ChatPanel').then((module) => ({ default: module.ChatPanel })),
);
import { BlockModal } from './components/BlockModal';
import { ComparePool } from './components/ComparePool';
import { CompareVerdicts } from './components/CompareVerdicts';
import { SectionNav } from './components/SectionNav';
import { anchorId } from './components/ReportSection';
import { CompletionBar } from './components/CompletionBar';
import { NewsBlock } from './components/NewsBlock';
import { ReportSection } from './components/ReportSection';
import { SourceLights } from './components/SourceLights';
import { TriggersBlock } from './components/TriggersBlock';
import { VerdictBanner } from './components/VerdictBanner';

const HISTORY_KEY = 'counterparty-check-history-v1';
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

function AppHeader({ compact, onHome, mode, onMode, children }: {
  compact?: boolean;
  onHome?: () => void;
  /** Режим продукта. Без него подпись «Проверка контрагента» — просто текст;
   *  с ним это выбор между проверкой одного и сравнением нескольких. */
  mode?: 'report' | 'compare';
  onMode?: (next: 'report' | 'compare') => void;
  children?: ReactNode;
}) {
  return (
    <header className={'app-header' + (compact ? ' app-header--compact' : '')}>
      <Brand onHome={onHome} />
      {mode && onMode ? (
        <div className="app-header__modes" role="tablist" aria-label="Режим">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'report'}
            className={`mode${mode === 'report' ? ' mode--on' : ''}`}
            onClick={() => onMode('report')}
          >
            Проверка контрагента
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'compare'}
            className={`mode${mode === 'compare' ? ' mode--on' : ''}`}
            onClick={() => onMode('compare')}
          >
            Сравнение контрагентов
          </button>
        </div>
      ) : (
        <span className="app-header__product">Проверка контрагента</span>
      )}
      {children}
    </header>
  );
}

function ComparePage({ pool, result, failed, onAdd, onRemove, onOpenReport }: {
  pool: string[];
  result: CompareResult | null;
  failed: boolean;
  onAdd: (inn: string) => void;
  onRemove: (inn: string) => void;
  onOpenReport: (inn: string, section?: string) => void;
}) {
  return (
    <main className="page compare-page">
      <ComparePool
        pool={pool}
        verdicts={result?.verdicts ?? []}
        notFound={result?.not_found ?? []}
        onAdd={onAdd}
        onRemove={onRemove}
      />

      {failed ? (
        <p className="compare__empty">
          Не удалось собрать сравнение. Это сбой сервиса, а не утверждение
          о компаниях.
        </p>
      ) : pool.length === 0 ? (
        <p className="compare__empty">
          Добавьте контрагентов по ИНН — сравнение покажет, к кому из них меньше
          вопросов, и назовёт причины.
        </p>
      ) : result === null ? (
        <p className="compare__empty">Собираем сравнение…</p>
      ) : (
        <CompareVerdicts
          verdicts={result.verdicts}
          summary={result.summary}
          onOpenReport={onOpenReport}
        />
      )}
    </main>
  );
}

function DashboardSkeleton() {
  return (
    <main className="page dashboard-page" aria-label="Загрузка отчёта">
      <div className="skeleton-title"><Skeleton visible animate><div>Загружаем название компании</div></Skeleton></div>
      <div className="dashboard-layout">
        <section className="report-sections">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} visible animate borderRadius={16}>
              <div className="section-skeleton">Загрузка данных раздела</div>
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

function HomeScreen({ query, setQuery, suggestions, searching, notFound, loadFailed, history, onSearch, onSelect }: {
  query: string;
  setQuery: (value: string) => void;
  suggestions: Counterparty[];
  searching: boolean;
  notFound: boolean;
  loadFailed: boolean;
  history: HistoryItem[];
  onSearch: () => void;
  onSelect: (inn: string) => void;
}) {
  return (
    <>
      <AppHeader />
      <main className="home page">
        <section className="hero">
          <span className="static-label static-label--hero">Для вашего бизнеса</span>
          <Typography.Title tag="h1" className="hero__title" view="xlarge" font="styrene" weight="bold">
            Проверьте контрагента<br />до начала работы
          </Typography.Title>
          <p>
            Помогаем быстро и эффективно оценить надёжность контрагента: защитите бизнес от штрафов,
            доначислений налогов и недобросовестных партнёров.
          </p>
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
                    <span><strong>{item.name}</strong>{item.director && <small>{item.director}</small>}</span>
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

        <section className="history">
          <div className="section-heading">
            <div>
              <Typography.Title tag="h2" view="xsmall" font="styrene" weight="bold">
                Недавние проверки
              </Typography.Title>
            </div>
          </div>
          {history.length > 0 ? (
            <div className="history-grid">
              {history.map((item) => (
                <button className="history-card" key={item.inn} type="button" onClick={() => onSelect(item.inn)}>
                  <Status size={20} view="soft" color={riskColor(item.bankRisk)}>{historyRiskLabel(item.bankRisk)}</Status>
                  <Typography.Title tag="h3" view="xsmall" font="styrene" weight="bold">{item.name}</Typography.Title>
                  <p>ИНН {item.inn}</p>
                  <div><time>{item.dataDate}</time></div>
                </button>
              ))}
            </div>
          ) : (
            <p className="history-empty">Здесь появятся ваши последние проверки.</p>
          )}
        </section>
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

function headerFacts(sections: ReportSectionData[]) {
  const labels = /^(Юридический адрес|Адрес|Телефон|Контакт|Контакты|Сайт|Веб-сайт|E-mail|Электронная почта)$/i;
  const facts = sections.find((section) => section.key === 'registration')?.facts ?? [];
  return facts.filter((fact) => labels.test(fact.label)).map((fact) => ({ label: fact.label, value: String(fact.value) }));
}

function Dashboard({ company, report, news, openedSection, highlighted, onHome, onCompare, onOpenBlock, onCloseBlock, onToast }: {
  company: Counterparty;
  report: CounterpartyReport | null;
  news: CompanyNews | null | undefined;
  openedSection: string | null;
  highlighted: boolean;
  onHome: () => void;
  onCompare: () => void;
  onOpenBlock: (key: string, proof?: boolean) => void;
  onCloseBlock: () => void;
  onToast: (message: string) => void;
}) {
  // Отчёт с сервера — источник, если он есть. Иначе те же 6 полей, что видит
  // модель в сокращённом ответе API, приведённые к тому же контракту — одна
  // отрисовка вместо двух несогласованных.
  const sections = orderedSections(report?.sections ?? sectionsFromCompany(company));
  const bankKnown = report ? report.bank_risk.known : company.bankRisk !== 'Нет данных';
  const bankValue = report?.bank_risk.value ?? company.bankRisk;
  const zskKnown = report ? report.zsk_risk.known : company.bankLight !== 'Нет данных';
  const zskValue = report?.zsk_risk.value ?? company.bankLight;
  const verdict = deriveVerdict(sections);
  // Раскрыта ли полоса разбора. Живёт здесь, а не в чате: от неё зависит
  // раскладка всей страницы — навигация по разделам уходит вниз вместе
  // с отчётом, когда разговор занимает экран.
  const [asking, setAsking] = useState(false);
  // Экран новой компании открывается её отчётом, а не чужой перепиской.
  useEffect(() => setAsking(false), [company.inn]);

  // Переход к разделу из навигации: подробный вид закрывается — иначе целевой
  // карточки на странице просто нет, — и страница прокручивается к ней.
  // Прокрутка в следующем кадре: карточка появляется только после отрисовки
  // закрытого подробного вида.
  const goToSection = (key: string) => {
    onCloseBlock();
    requestAnimationFrame(() => {
      document.getElementById(anchorId(key))?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    });
  };

  // Дата, на которую собраны данные. Спрашиваем у сервиса, а не подставляем
  // заглушку: раньше в карточке стояло «Данные отчёта на дата не указана».
  const [dataDate, setDataDate] = useState<string | null>(null);
  useEffect(() => {
    let живо = true;
    void datasetDate().then((д) => живо && setDataDate(д));
    return () => {
      живо = false;
    };
  }, []);

  return (
    <>
      <AppHeader compact onHome={onHome} mode="report" onMode={(next) => next === 'compare' && onCompare()}>
        {/* Имя и ИНН в шапке, а не отдельным блоком на пол-экрана: полоса
            разбора занимает верх страницы, и «про какую компанию мы говорим»
            должно оставаться видимым, когда отчёт уехал вниз. */}
        <div className="company-chip">
          <span className="company-chip__name">{company.name}</span>
          <span>ИНН {company.inn}</span>
          {dataDate && <span>· данные на {dataDate}</span>}
        </div>
        <div className="app-header__actions">
          <TooltipDesktop content="Сохранить в PDF" position="bottom">
            <IconButtonDesktop
              size={40}
              view="secondary"
              icon={DocumentPdfMIcon}
              aria-label="Сохранить в PDF"
              onClick={() => window.print()}
            />
          </TooltipDesktop>
          <TooltipDesktop content="Скопировать ссылку на отчёт" position="bottom">
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
          <ButtonDesktop size={40} view="text" onClick={onHome}>
            Новый поиск
          </ButtonDesktop>
        </div>
      </AppHeader>

      {/* Базовый экран: блоки слева, разбор колонкой справа. Разбор
          раскрывается поверх страницы на всю ширину — отчёт при этом остаётся
          на месте под ним, а не уезжает: к нему возвращаются проверять
          утверждения, и он не должен менять положение. */}
      <main className="page dashboard-page">
        <div className="dashboard-layout">
        <section className="dashboard-main">
          {openedSection ? (
            <BlockModal
              sections={sections}
              blockKey={openedSection}
              highlighted={highlighted}
              onClose={onCloseBlock}
              onOpenBlock={onOpenBlock}
            />
          ) : (
            <>
              <SourceLights
                bank={{ known: bankKnown, value: bankValue }}
                zsk={{ known: zskKnown, value: zskValue }}
              />
              <VerdictBanner verdict={verdict} onOpenSection={onOpenBlock} />

              {/* Противоречия сразу под вердиктом: это то, ради чего
                  пользователь пришёл, и читать до них восемь карточек
                  он не должен. */}
              {report && (
                <TriggersBlock triggers={report.triggers ?? []} onOpenSection={onOpenBlock} />
              )}

              <div className="blocks-heading">
                <Typography.Title tag="h2" view="xsmall" font="styrene" weight="bold">
                  Разделы проверки
                </Typography.Title>
                <TooltipDesktop content="Порядок разделов постоянный. Недостаток данных не означает отсутствие рисков">
                  <span className="indicator-legend">Как читать разделы</span>
                </TooltipDesktop>
              </div>

              <div className="report-sections">
                {sections.map((section) => (
                  <ReportSection
                    key={section.key}
                    section={section}
                    onOpen={() => onOpenBlock(section.key)}
                  />
                ))}
              </div>

              <NewsBlock news={news} />
              <CompletionBar onAnswer={() => onToast('Спасибо за отзыв')} />
            </>
          )}
        </section>

        <aside className="dashboard-side">
          <SectionNav sections={sections} onGo={goToSection} />
          <Suspense fallback={<div className="chat-band chat-band--loading">Загрузка разбора…</div>}>
            <ChatPanel
              report={report}
              expanded={asking}
              onExpanded={setAsking}
              onToast={onToast}
            />
          </Suspense>
        </aside>
        </div>
      </main>
    </>
  );
}

export default function App() {
  const [view, setView] = useState<'home' | 'dashboard' | 'compare'>('home');
  // Пул сравнения живёт рядом с отчётом, а не вместо него: переключение
  // режимов не должно терять ни открытую компанию, ни собранный пул.
  const [pool, setPool] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [compareFailed, setCompareFailed] = useState(false);
  const [query, setQueryState] = useState('');
  const [suggestions, setSuggestions] = useState<Counterparty[]>([]);
  const [searching, setSearching] = useState(false);
  const [notFound, setNotFound] = useState(false);
  // Сбой связи — не утверждение о компании. Смешивать их нельзя:
  // «сервис недоступен» и «такой компании нет» это разные ответы.
  const [loadFailed, setLoadFailed] = useState(false);
  const [company, setCompany] = useState<Counterparty | null>(null);
  // Собранный отчёт с сервера. null означает «сервер недоступен» —
  // тогда разделы строятся из тех же данных, что уже есть у company.
  const [report, setReport] = useState<CounterpartyReport | null>(null);
  // Три значения, а не два: null — ещё ищем, undefined — внешний поиск
  // не настроен и блока быть не должно, объект — искали и вот что вышло.
  const [news, setNews] = useState<CompanyNews | null | undefined>(null);
  const [history, setHistory] = useState<HistoryItem[]>(readHistory);
  const [modalBlock, setModalBlock] = useState<string | null>(null);

  // Открытие адреса с ИНН ведёт к тому же отчёту — иначе постоянная ссылка бессмысленна.
  useEffect(() => {
    const inn = new URLSearchParams(window.location.search).get('inn');
    if (inn) void openCompany(inn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [highlighted, setHighlighted] = useState(false);
  const [toast, setToast] = useState('');

  // Пул пересобирается на сервере при каждом изменении: порядок и вывод —
  // часть ответа, а не клиентская сортировка.
  useEffect(() => {
    if (pool.length === 0) {
      setCompareResult(null);
      setCompareFailed(false);
      return undefined;
    }
    let живо = true;
    setCompareFailed(false);
    void compareCounterparties(pool)
      .then((итог) => живо && setCompareResult(итог))
      .catch(() => живо && setCompareFailed(true));
    return () => {
      живо = false;
    };
  }, [pool]);

  const addToPool = (inn: string) =>
    setPool((текущий) => (текущий.includes(inn) ? текущий : [...текущий, inn]));
  const removeFromPool = (inn: string) =>
    setPool((текущий) => текущий.filter((и) => и !== inn));

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
      // Новости — тем более отдельно: чужой поиск с чтением страниц занимает
      // около десяти секунд, и экран не должен их ждать.
      setNews(null);
      getNews(inn)
        .then(setNews)
        .catch(() => setNews({ items: [], level: '', failed: true, checked_at: 0 }));
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
          onSearch={submitSearch}
          onSelect={(inn) => void openCompany(inn)}
        />
      ) : view === 'compare' ? (
        <>
          <AppHeader
            compact
            onHome={goHome}
            mode="compare"
            onMode={(next) => setView(next === 'compare' ? 'compare' : company ? 'dashboard' : 'home')}
          >
            <div className="app-header__actions">
              <ButtonDesktop size={40} view="text" onClick={goHome}>Новый поиск</ButtonDesktop>
            </div>
          </AppHeader>
          <ComparePage
            pool={pool}
            result={compareResult}
            failed={compareFailed}
            onAdd={addToPool}
            onRemove={removeFromPool}
            onOpenReport={(inn, section) => {
              void openCompany(inn).then(() => {
                if (section) openBlock(section);
              });
            }}
          />
        </>
      ) : company ? (
        <Dashboard
          company={company}
          report={report}
          news={news}
          openedSection={modalBlock}
          highlighted={highlighted}
          onHome={goHome}
          onCompare={() => {
            // Открытая компания попадает в пул первой: сравнивать её с кем-то
            // и есть причина, по которой сюда переключаются.
            addToPool(company.inn);
            setView('compare');
          }}
          onOpenBlock={openBlock}
          onCloseBlock={() => { setModalBlock(null); setHighlighted(false); window.scrollTo({ top: 0 }); }}
          onToast={setToast}
        />
      ) : <><AppHeader compact onHome={goHome} /><DashboardSkeleton /></>}

      {toast && (
        <div className="toast-wrap" role="status">
          <ToastPlateDesktop title={toast} badge="positive-checkmark" closerProps={{ hasCloser: true }} onClose={() => setToast('')} />
        </div>
      )}
    </div>
  );
}
