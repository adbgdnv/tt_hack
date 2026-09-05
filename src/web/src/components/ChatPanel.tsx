import { useEffect, useMemo, useRef, useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { IconButtonDesktop } from '@alfalab/core-components-icon-button/desktop';
import { TagDesktop } from '@alfalab/core-components-tag/desktop';
import { Typography } from '@alfalab/core-components-typography';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { ArrowsInwardMIcon } from '@alfalab/icons-glyph/ArrowsInwardMIcon';
import { ArrowsOutwardMIcon } from '@alfalab/icons-glyph/ArrowsOutwardMIcon';
import { SendMIcon } from '@alfalab/icons-glyph/SendMIcon';
import { TooltipDesktop } from '@alfalab/core-components-tooltip/desktop';

import { streamChat } from '../api';
import type { AnswerCheck, CounterpartyReport, MessageBlock } from '../types';
import { ChatMarkdown } from './ChatMarkdown';
import { ToolBlock } from './ToolBlock';

type Message =
  | { id: string; role: 'user'; text: string }
  | {
      id: string;
      role: 'agent';
      /** Упорядоченная последовательность блоков: текст и вызовы вперемешку,
       *  ровно в том порядке, в каком они происходили. Прежде здесь были три
       *  отдельных списка, и один вызов оказывался разорван между началом
       *  и концом сообщения. */
      blocks: MessageBlock[];
      sections: string[];
      streaming: boolean;
      /** Итог сверки чисел с отчётом. Приходит после текста ответа. */
      check?: AnswerCheck;
    }
  /** Сбой сервиса — отдельная роль, а не ответ: путать их нельзя. */
  | { id: string; role: 'failure'; text: string };

type FeedbackValue = { value: 'up' | 'down'; reason?: string };

const FEEDBACK_REASONS = [
  'Не отвечает на вопрос',
  'Непонятно',
  'Недостаточно данных',
  'Обнаружена ошибка',
  'Слишком много текста',
  'Другое',
];

/** Пул шире видимых трёх вопросов: использованный вопрос сразу заменяется следующим. */
function suggestionPool(report: CounterpartyReport | null): string[] {
  if (!report) return ['Что можно проверить в отчёте?'];
  const signalled = report.sections.filter((section) => section.state === 'signal');
  const missing = report.sections.filter((section) => section.state === 'empty');
  const questions = [
    ...signalled.map((section) => `Какие факты важны в разделе «${section.title}»?`),
    ...missing.map((section) => `Каких данных не хватает в разделе «${section.title}»?`),
  ];
  if (report.signals === 0) questions.push('Что удалось проверить, а что нет?');
  questions.push(
    'Что стоит уточнить перед сделкой?',
    'Какие документы запросить у контрагента?',
    'Какие факты стоит перепроверить в первую очередь?',
    'Что в отчёте не влияет на банковскую оценку?',
  );
  return [...new Set(questions)];
}

/**
 * Чем подтверждён ответ.
 *
 * «Не выдумывает» — критерий приёмки кейса, и до этой строки он держался
 * на формулировках промпта: пользователю нечем было отличить число из отчёта
 * от придуманного. Неподтверждённое показывается, а не вычёркивается: нужны
 * и утверждение, и сомнение в нём.
 *
 * Ответ без чисел не показывает ничего: «проверять было нечего» — не то же
 * самое, что «подтверждено», и выдавать одно за другое нельзя.
 */
function AnswerCheckLine({ check }: { check: AnswerCheck }) {
  if (check.total === 0) return null;
  const confirmed = check.total - check.unverified.length;
  return (
    <div className={`answer-check${check.unverified.length ? ' answer-check--doubt' : ''}`}>
      <span>
        Числа сверены с отчётом: {confirmed} из {check.total}
      </span>
      {check.unverified.length > 0 && (
        <ul>
          {check.unverified.map((claim) => (
            <li key={`${claim.number}-${claim.context}`}>
              <b>{claim.number}</b> — в отчёте не нашлось: {claim.context}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AnswerFeedback({ value, onChange }: {
  value?: FeedbackValue;
  onChange: (next: FeedbackValue) => void;
}) {
  return (
    <div className="answer-feedback">
      <span>Ответ помог?</span>
      <TagDesktop
        size={32}
        checked={value?.value === 'up'}
        aria-label="Ответ помог"
        onClick={() => onChange({ value: 'up' })}
      >
        👍
      </TagDesktop>
      <TagDesktop
        size={32}
        checked={value?.value === 'down'}
        aria-label="Ответ не помог"
        onClick={() => onChange({ value: 'down' })}
      >
        👎
      </TagDesktop>
      {value?.value === 'down' && (
        <div className="answer-feedback__reasons" aria-label="Причина отрицательной оценки">
          {FEEDBACK_REASONS.map((reason) => (
            <TagDesktop
              key={reason}
              size={32}
              checked={value.reason === reason}
              onClick={() => onChange({ value: 'down', reason })}
            >
              {reason}
            </TagDesktop>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChatPanel({ report, expanded, onExpanded, onToast }: {
  report: CounterpartyReport | null;
  /** Раскрыта ли полоса. Живёт в `App`: от неё зависит раскладка всей
   *  страницы — навигация по разделам уходит вниз вместе с отчётом. */
  expanded: boolean;
  onExpanded: (open: boolean) => void;
  onToast: (message: string) => void;
}) {
  const setExpanded = onExpanded;
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [askedQuestions, setAskedQuestions] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<Record<string, FeedbackValue>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  // Брошенный поток на сервере продолжал бы тратить квоту, общую на всех.
  const abortRef = useRef<AbortController | null>(null);
  /** Раскрытый вызов — один на всю ленту: развёрнутая страница и развёрнутый
   *  поиск разом выталкивают текст ответа с экрана. */
  const [openTool, setOpenTool] = useState<string | null>(null);

  /** Внизу ли пользователь. Обновляется прокруткой, а не подсчётом при отрисовке. */
  const stickToBottom = useRef(true);
  const sessionId = useMemo(() => `s-${Math.random().toString(36).slice(2)}`, []);
  const questions = useMemo(
    () => suggestionPool(report).filter((question) => !askedQuestions.includes(question)).slice(0, 3),
    [askedQuestions, report],
  );

  // Держим ленту внизу, только пока пользователь и так внизу. Иначе отлистать
  // вверх во время ответа невозможно: каждое пришедшее слово утаскивало бы
  // обратно. Плавную прокрутку во время печати не включаем — на каждом слове
  // она превращается в дрожание.
  useEffect(() => {
    const element = scrollRef.current;
    // Разговора ещё нет — прижимать нечего. Раньше лента открывалась
    // прокрученной в конец первого сообщения, и вердикт, ради которого
    // экран и открывается, оказывался выше края.
    if (!element || !stickToBottom.current || messages.length === 0) return;
    element.scrollTop = element.scrollHeight;
  }, [messages, busy]);

  // Смена контрагента сбрасывает переписку: ответы о предыдущей компании
  // в новом контексте вводят в заблуждение.
  useEffect(() => {
    abortRef.current?.abort();
    setMessages([]);
    setInput('');
    setAskedQuestions([]);
    setFeedback({});
  }, [report?.inn]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // Esc сворачивает — привычка, а не выдумка. Во время ответа не сворачивает:
  // текст, приходящий в невидимую полосу, для читателя потерян.
  useEffect(() => {
    if (!expanded) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) setExpanded(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded, busy]);


  const ask = async (question: string) => {
    const clean = question.trim();
    if (!clean || busy || !report) return;
    setInput('');
    const replyId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', text: clean },
      { id: replyId, role: 'agent', blocks: [], sections: [], streaming: true },
    ]);
    setBusy(true);

    // Блоки копятся здесь, а в состояние уезжают раз в кадр. Порядок при этом
    // не страдает: накопитель меняется сразу, отрисовка догоняет. Без этого
    // разметка разбиралась бы заново на каждое пришедшее слово.
    const blocks: MessageBlock[] = [];
    let frame: number | null = null;
    const flush = () => {
      frame = null;
      setMessages((current) =>
        current.map((m) =>
          m.id === replyId && m.role === 'agent' ? { ...m, blocks: [...blocks] } : m,
        ),
      );
    };
    const schedule = () => {
      if (frame === null) frame = requestAnimationFrame(flush);
    };

    const appendText = (text: string) => {
      const last = blocks[blocks.length - 1];
      if (last && last.kind === 'text') last.text += text;
      else blocks.push({ kind: 'text', text });
      schedule();
    };
    /** Последний открытый вызов — ему принадлежит пришедший результат. */
    const lastCall = () => {
      for (let i = blocks.length - 1; i >= 0; i -= 1) {
        const block = blocks[i];
        if (block.kind === 'tool') return block.call;
      }
      return null;
    };

    const controller = new AbortController();
    abortRef.current = controller;
    let failed = '';
    try {
      for await (const event of streamChat(report.inn, clean, sessionId, controller.signal)) {
        if (event.name === 'token') {
          appendText(event.data.text);
        } else if (event.name === 'tool_start') {
          // Вызов открывается НА ТЕКУЩЕМ МЕСТЕ — отсюда и берётся порядок
          // «текст → вызов → текст». Вычислять его потом неоткуда.
          blocks.push({
            kind: 'tool',
            call: { tool: event.data.tool, title: event.data.title, state: 'running' },
          });
          schedule();
        } else if (event.name === 'chart') {
          const call = lastCall();
          if (call) call.chart = event.data.chart;
          schedule();
        } else if (event.name === 'sources') {
          const call = lastCall();
          if (call) call.sources = event.data.items;
          schedule();
        } else if (event.name === 'lookup') {
          const call = lastCall();
          if (call) {
            call.lookup = event.data;
            // Тема дописывается в заголовок только здесь: в начале вызова
            // аргументы приходят кусками и обычно ещё не разобраны, поэтому
            // три запроса подряд выглядели тремя одинаковыми строками
            // «Запросил данные».
            call.title = `Запросил данные: ${event.data.topic}`;
          }
          schedule();
        } else if (event.name === 'check') {
          const проверка = event.data;
          setMessages((current) =>
            current.map((m) =>
              m.id === replyId && m.role === 'agent' ? { ...m, check: проверка } : m,
            ),
          );
        } else if (event.name === 'tool_end') {
          const call = lastCall();
          if (call) call.state = event.data.ok ? 'ok' : 'failed';
          schedule();
        } else if (event.name === 'error') {
          failed = event.data.detail;
        } else if (event.name === 'done') {
          setMessages((current) =>
            current.map((m) =>
              m.id === replyId && m.role === 'agent' ? { ...m, sections: event.data.sections } : m,
            ),
          );
        }
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        failed = error instanceof Error ? error.message : 'Сервис разбора сейчас недоступен';
      }
    } finally {
      abortRef.current = null;
      if (frame !== null) cancelAnimationFrame(frame);
      // Вызовы, до которых не дошло завершение, — прерваны, а не выполняются.
      // Иначе оборванный ответ оставляет их крутящимися навсегда.
      for (const block of blocks) {
        if (block.kind === 'tool' && block.call.state === 'running') block.call.state = 'aborted';
      }
      const finalBlocks = [...blocks];
      setMessages((current) =>
        current.map((m) =>
          m.id === replyId && m.role === 'agent'
            ? { ...m, blocks: finalBlocks, streaming: false }
            : m,
        ),
      );
      setBusy(false);
    }

    if (failed) {
      // Уже показанный текст не убираем: он настоящий. Сбой добавляется рядом.
      const saidSomething = blocks.some((b) => b.kind === 'text' && b.text.trim());
      setMessages((current) => [
        ...current.filter((m) => m.id !== replyId || saidSomething),
        { id: crypto.randomUUID(), role: 'failure', text: failed },
      ]);
      onToast('Разбор недоступен — отчёт остаётся полным');
    }
  };

  return (
    <>
      {/* Подложка гасит отчёт, но оставляет его видимым и на месте: к нему
          возвращаются проверять утверждения, и он не должен ни исчезать,
          ни менять положение под наложением. */}
      {expanded && (
        <div
          className="chat-scrim"
          aria-hidden="true"
          onClick={() => !busy && setExpanded(false)}
        />
      )}
    <section
      className={`chat-band${expanded ? ' chat-band--open' : ''}`}
      aria-label="Разбор отчёта контрагента"
    >
      <header className="chat-band__head">
        <span className="ai-mark">AI</span>
        <div className="chat-band__title">
          <Typography.Title tag="h2" view="xsmall" font="styrene" weight="bold">
            Разбор отчёта
          </Typography.Title>
          <small>Спросите что угодно об этой компании</small>
        </div>
        {/* Переключатель в углу, а не кнопка «Свернуть» при раскрытом.
            Раскрытие есть и по фокусу в поле, но фокус — намерение спросить,
            а не намерение читать: перечитать длинный ответ хочется и без
            нового вопроса, и для этого нужна явная кнопка.

            Свернуть во время ответа нельзя: текст, приходящий в невидимую
            панель, для читателя потерян. */}
        <TooltipDesktop
          content={expanded ? 'Свернуть' : 'Развернуть на весь экран'}
          position="left"
        >
          <IconButtonDesktop
            size={32}
            view="secondary"
            icon={expanded ? ArrowsInwardMIcon : ArrowsOutwardMIcon}
            disabled={expanded && busy}
            aria-label={expanded ? 'Свернуть разбор' : 'Развернуть разбор на весь экран'}
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          />
        </TooltipDesktop>
      </header>

      <div
        className="chat-scroll"
        ref={scrollRef}
        onScroll={(event) => {
          const element = event.currentTarget;
          const fromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
          stickToBottom.current = fromBottom < 80;
        }}
      >
        <div className="agent-message agent-message--summary">
          <span className="message-author">Ассистент</span>
          <p>Отвечаю только по этому отчёту. Чего в нём нет — так и скажу.</p>
        </div>

        {messages.map((message) =>
          message.role === 'user' ? (
            // Строка-обёртка, а не выравнивание самого пузыря: колонка ленты
            // задаёт каждому блоку свою ширину, и `align-self` на пузыре
            // ничего не двигал — он занимал всю строку и текст оставался слева.
            <div className="chat-row chat-row--user" key={message.id}>
              <div className="user-message">{message.text}</div>
            </div>
          ) : message.role === 'failure' ? (
            <div className="agent-message agent-message--failure" key={message.id} role="status">
              <strong>Не удалось получить разбор</strong>
              <p>{message.text} Это сбой сервиса, а не утверждение о компании — отчёт слева остаётся полным.</p>
            </div>
          ) : message.streaming && message.blocks.length === 0 ? null : (
            <div className="agent-message" key={message.id}>
              <span className="message-author">Ассистент</span>

              {/* Блоки идут ровно в том порядке, в каком происходили. Результат
                  вызова лежит внутри своего вызова, а не в конце сообщения. */}
              {message.blocks.map((block, index) =>
                block.kind === 'text' ? (
                  <ChatMarkdown key={`t${index}`} text={block.text} />
                ) : (
                  <ToolBlock
                    key={`c${index}`}
                    call={block.call}
                    chart={
                      block.call.chart
                        ? report?.sections
                            .flatMap((section) => section.charts)
                            .find((chart) => chart.key === block.call.chart)
                        : undefined
                    }
                    expanded={openTool === `${message.id}:${index}`}
                    onToggle={() =>
                      setOpenTool((current) =>
                        current === `${message.id}:${index}` ? null : `${message.id}:${index}`,
                      )
                    }
                  />
                ),
              )}

              {/* Курсор живёт вне разбора разметки: внутри он попал бы
                  в разбираемую строку и ломал бы её. */}
              {message.streaming && <span className="agent-caret" aria-hidden="true" />}

              {/* Разделы, названные в ответе, — сдержанной подписью, а не
                  карточкой. Опознаются они совпадением слов в тексте, то есть
                  догадкой (4 ответа из 8 на замере), и карточка выдавала бы
                  догадку за проверенное основание. */}
              {message.sections.length > 0 && (
                <div className="agent-message__grounding">
                  {message.sections.map((key) => {
                    const section = report?.sections.find((item) => item.key === key);
                    return section ? (
                      <span className="static-label" key={key}>{section.title}</span>
                    ) : null;
                  })}
                </div>
              )}
              {message.check && <AnswerCheckLine check={message.check} />}
              {!message.streaming && (
                <AnswerFeedback
                  value={feedback[message.id]}
                  onChange={(next) => setFeedback((current) => ({ ...current, [message.id]: next }))}
                />
              )}
            </div>
          ),
        )}

        {/* Индикатор нужен только до первого слова: дальше видно сам ответ. */}
        {busy &&
          !messages.some(
            (m) => m.role === 'agent' && m.streaming && m.blocks.length > 0,
          ) && (
          <div className="agent-message progress-card" aria-live="polite">
            <span className="message-author">Ассистент</span>
            <p>Читаю отчёт…</p>
          </div>
        )}
      </div>

      {/* Подсказки нужны ровно до первого вопроса: они отвечают «с чего
          начать». Дальше человек уже начал, а они отнимают у ленты треть
          высоты ровно там, где идёт ответ.

          Условной отрисовкой, а не `hidden`: у блока есть `display` из класса,
          а правило автора сильнее браузерного `[hidden] { display: none }` —
          атрибут стоял, подсказки показывались. */}
      {messages.length === 0 && (
      <div className="chat-suggestions" aria-label="Предложенные вопросы">
        <span>С чего начать</span>
        {questions.map((question) => (
          <ButtonDesktop
            key={question}
            className="chat-suggestions__item"
            size={40}
            view="secondary"
            block
            disabled={busy}
            onClick={() => void ask(question)}
          >
            {question}
          </ButtonDesktop>
        ))}
      </div>
      )}

      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(input);
        }}
      >
        <InputDesktop
          size={48}
          block
          value={input}
          disabled={busy || !report}
          placeholder={report ? 'Напишите вопрос по отчёту' : 'Чат доступен с отчётом сервера'}
          aria-label="Вопрос по отчёту"
          onChange={(_, { value }) => setInput(value)}
          // Раздвижение по постановке курсора, а не по кнопке: намерение
          // спросить выражается тем, что человек ставит курсор в поле.
          onFocus={() => {
            setExpanded(true);
            // Браузер подкручивает страницу к полю, и шапка уезжает за край.
            // Возвращаем верх: раскрытая полоса занимает экран целиком
            // и должна начинаться под шапкой, а не над ней.
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
        />
        <IconButtonDesktop
          size={48}
          view="primary"
          type="submit"
          icon={SendMIcon}
          loading={busy}
          disabled={!report || !input.trim()}
          aria-label="Отправить вопрос"
          title="Отправить вопрос"
        />
      </form>
    </section>
    </>
  );
}
