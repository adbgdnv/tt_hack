import { useEffect, useMemo, useRef, useState } from 'react';
import { IconButtonDesktop } from '@alfalab/core-components-icon-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { SendMIcon } from '@alfalab/icons-glyph/SendMIcon';

import { streamChat } from '../api';
import type { CounterpartyReport } from '../types';
import { ReportChart } from './ReportChart';

/** Вызов инструмента в ленте: пользователь видит, чем занят агент. */
type Step = { id: string; title: string; done: boolean; ok: boolean };
type Source = { title: string; url: string };

type Message =
  | { id: string; role: 'user'; text: string }
  | {
      id: string;
      role: 'agent';
      text: string;
      sections: string[];
      steps: Step[];
      charts: string[];
      sources: Source[];
      streaming: boolean;
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

function AnswerFeedback({ value, onChange }: {
  value?: FeedbackValue;
  onChange: (next: FeedbackValue) => void;
}) {
  return (
    <div className="answer-feedback">
      <span>Ответ помог?</span>
      <button type="button" aria-label="Ответ помог" aria-pressed={value?.value === 'up'} onClick={() => onChange({ value: 'up' })}>👍</button>
      <button type="button" aria-label="Ответ не помог" aria-pressed={value?.value === 'down'} onClick={() => onChange({ value: 'down' })}>👎</button>
      {value?.value === 'down' && (
        <div className="answer-feedback__reasons" aria-label="Причина отрицательной оценки">
          {FEEDBACK_REASONS.map((reason) => (
            <button
              key={reason}
              type="button"
              aria-pressed={value.reason === reason}
              onClick={() => onChange({ value: 'down', reason })}
            >
              {reason}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChatPanel({ report, onToast }: {
  report: CounterpartyReport | null;
  onToast: (message: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [askedQuestions, setAskedQuestions] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<Record<string, FeedbackValue>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  // Брошенный поток на сервере продолжал бы тратить квоту, общую на всех.
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = useMemo(() => `s-${Math.random().toString(36).slice(2)}`, []);
  const questions = useMemo(
    () => suggestionPool(report).filter((question) => !askedQuestions.includes(question)).slice(0, 3),
    [askedQuestions, report],
  );

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
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

  const ask = async (question: string) => {
    const clean = question.trim();
    if (!clean || busy || !report) return;
    setInput('');
    // Заданный вопрос убираем из подсказок и подставляем следующий из пула.
    setAskedQuestions((current) => (current.includes(clean) ? current : [...current, clean]));
    const replyId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', text: clean },
      {
        id: replyId,
        role: 'agent',
        text: '',
        sections: [],
        steps: [],
        charts: [],
        sources: [],
        streaming: true,
      },
    ]);
    setBusy(true);

    // Правку ответа держим в одном месте: событий много, а меняют они
    // всегда одно и то же сообщение.
    const patch = (change: (m: Extract<Message, { role: 'agent' }>) => Partial<Message>) =>
      setMessages((current) =>
        current.map((m) => (m.id === replyId && m.role === 'agent' ? { ...m, ...change(m) } : m)),
      );

    const controller = new AbortController();
    abortRef.current = controller;
    let failed = '';
    try {
      for await (const event of streamChat(report.inn, clean, sessionId, controller.signal)) {
        if (event.name === 'token') {
          patch((m) => ({ text: m.text + event.data.text }));
        } else if (event.name === 'tool_start') {
          patch((m) => ({
            steps: [...m.steps, { id: event.data.tool, title: event.data.title, done: false, ok: true }],
          }));
        } else if (event.name === 'tool_end') {
          patch((m) => ({
            steps: m.steps.map((s, i) =>
              i === m.steps.length - 1 ? { ...s, done: true, ok: event.data.ok } : s,
            ),
          }));
        } else if (event.name === 'chart') {
          patch((m) => ({ charts: [...m.charts, event.data.chart] }));
        } else if (event.name === 'sources') {
          patch((m) => ({ sources: event.data.items }));
        } else if (event.name === 'error') {
          failed = event.data.detail;
        } else if (event.name === 'done') {
          patch((m) => ({ sections: event.data.sections, streaming: false }));
        }
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        failed = error instanceof Error ? error.message : 'Сервис разбора сейчас недоступен';
      }
    } finally {
      abortRef.current = null;
      patch(() => ({ streaming: false }));
      setBusy(false);
    }

    if (failed) {
      // Уже показанный текст не убираем: он настоящий. Сбой добавляется рядом.
      setMessages((current) => [
        ...current.filter((m) => m.id !== replyId || (m.role === 'agent' && m.text.length > 0)),
        { id: crypto.randomUUID(), role: 'failure', text: failed },
      ]);
      onToast('Разбор недоступен — отчёт остаётся полным');
    }
  };

  return (
    <aside className="chat-panel" aria-label="Чат об отчёте контрагента">
      <header className="chat-header">
        <div>
          <span className="ai-mark">AI</span>
          <div><h2>Чат по отчёту</h2><small>Задайте вопрос своими словами</small></div>
        </div>
        <span className="chat-memory">Память в этой сессии</span>
      </header>

      <div className="chat-scroll" ref={scrollRef}>
        <div className="agent-message agent-message--summary">
          <span className="message-author">Ассистент</span>
          <p>Отвечаю только по этому отчёту. Чего в нём нет — так и скажу.</p>
          <span className="summary-note">Оценки риска не пересчитываю, объясняю.</span>
        </div>

        {messages.map((message) =>
          message.role === 'user' ? (
            <div className="user-message" key={message.id}>{message.text}</div>
          ) : message.role === 'failure' ? (
            <div className="agent-message agent-message--failure" key={message.id} role="status">
              <strong>Не удалось получить разбор</strong>
              <p>{message.text} Это сбой сервиса, а не утверждение о компании — отчёт слева остаётся полным.</p>
            </div>
          ) : (
            <div className="agent-message" key={message.id}>
              <span className="message-author">Ассистент</span>

              {message.steps.map((step, index) => (
                <details className="agent-step" key={`${step.id}-${index}`}>
                  <summary>
                    {step.done ? (step.ok ? '✓' : '✕') : '⋯'} {step.title}
                  </summary>
                  <span>
                    {step.ok
                      ? 'Данные для ответа взяты отсюда.'
                      : 'Шаг не удался — то, что ниже, на него не опирается.'}
                  </span>
                </details>
              ))}

              <p className="agent-message__text">
                {message.text}
                {message.streaming && <span className="agent-caret" aria-hidden="true" />}
              </p>

              {/* График рисуется из уже загруженного отчёта по ключу: так числа
                  в чате физически не могут разойтись с дашбордом. */}
              {message.charts.map((key) => {
                const spec = report?.sections
                  .flatMap((section) => section.charts)
                  .find((chart) => chart.key === key);
                return spec ? (
                  <div className="agent-message__chart" key={key}>
                    <ReportChart spec={spec} />
                  </div>
                ) : null;
              })}

              {message.sources.length > 0 && (
                <div className="agent-message__sources">
                  <span>Внешние источники — отчётом не подтверждены:</span>
                  <ul>
                    {message.sources.map((source) => (
                      <li key={source.url}>
                        <a href={source.url} target="_blank" rel="noopener noreferrer">
                          {source.title || source.url}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {message.sections.length > 0 && (
                <div className="agent-message__grounding">
                  {message.sections.map((key) => {
                    const section = report?.sections.find((item) => item.key === key);
                    return section ? <span className="static-label" key={key}>{section.title}</span> : null;
                  })}
                </div>
              )}
              <AnswerFeedback
                value={feedback[message.id]}
                onChange={(next) => setFeedback((current) => ({ ...current, [message.id]: next }))}
              />
            </div>
          ),
        )}

        {/* Индикатор нужен только до первого слова: дальше видно сам ответ. */}
        {busy && !messages.some((m) => m.role === 'agent' && m.streaming && m.text) && (
          <div className="agent-message progress-card" aria-live="polite">
            <span className="message-author">Ассистент</span>
            <p>Читаю отчёт…</p>
          </div>
        )}
      </div>

      <div className="chat-suggestions" aria-label="Предложенные вопросы">
        {questions.map((question) => (
          <button key={question} type="button" disabled={busy} onClick={() => void ask(question)}>
            {question}
          </button>
        ))}
      </div>

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
    </aside>
  );
}
