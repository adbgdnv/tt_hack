import { useEffect, useMemo, useRef, useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { TagDesktop as Tag } from '@alfalab/core-components-tag/desktop';

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

/**
 * Заготовленные вопросы собираются по состояниям разделов: спрашивать про суды
 * у компании без судебных дел бессмысленно.
 */
function suggestions(report: CounterpartyReport | null): string[] {
  if (!report) return ['Что настораживает в этой компании?'];
  const signalled = report.sections.filter((s) => s.state === 'signal');
  const questions = signalled.slice(0, 2).map((s) => `Что не так с разделом «${s.title}»?`);
  if (report.signals === 0) questions.push('Что удалось проверить, а что нет?');
  if (report.unknowns > 0) questions.push('Чего не хватает в отчёте?');
  questions.push('Что стоит уточнить перед сделкой?');
  return questions.slice(0, 3);
}

export function ChatPanel({ report, onToast }: {
  report: CounterpartyReport | null;
  onToast: (message: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Брошенный поток на сервере продолжал бы тратить квоту, общую на всех.
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = useMemo(() => `s-${Math.random().toString(36).slice(2)}`, []);
  const questions = useMemo(() => suggestions(report), [report]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);

  // Смена контрагента сбрасывает переписку: ответы о предыдущей компании
  // в новом контексте вводят в заблуждение.
  useEffect(() => {
    abortRef.current?.abort();
    setMessages([]);
    setInput('');
  }, [report?.inn]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const ask = async (question: string) => {
    const clean = question.trim();
    if (!clean || busy || !report) return;
    setInput('');
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
    <aside className="chat-panel" aria-label="Диалог о контрагенте">
      <header className="chat-header">
        <div>
          <span className="ai-mark">AI</span>
          <h2>Разбор отчёта</h2>
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
                    const section = report?.sections.find((s) => s.key === key);
                    return section ? <Tag key={key} size={32} view="muted">{section.title}</Tag> : null;
                  })}
                </div>
              )}
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

      <div className="chat-suggestions">
        {questions.map((question) => (
          <button key={question} type="button" disabled={busy} onClick={() => ask(question)}>
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
          placeholder="Спросите об этой компании"
          onChange={(_, { value }) => setInput(value)}
        />
        <ButtonDesktop size={48} view="accent" type="submit" loading={busy} disabled={!report}>
          Спросить
        </ButtonDesktop>
      </form>
    </aside>
  );
}
