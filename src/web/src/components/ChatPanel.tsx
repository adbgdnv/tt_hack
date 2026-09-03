import { useEffect, useMemo, useRef, useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { TagDesktop as Tag } from '@alfalab/core-components-tag/desktop';

import { askAboutCounterparty } from '../api';
import type { CounterpartyReport } from '../types';

type Message =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'agent'; text: string; sections: string[] }
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
  const sessionId = useMemo(() => `s-${Math.random().toString(36).slice(2)}`, []);
  const questions = useMemo(() => suggestions(report), [report]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);

  // Смена контрагента сбрасывает переписку: ответы о предыдущей компании
  // в новом контексте вводят в заблуждение.
  useEffect(() => {
    setMessages([]);
    setInput('');
  }, [report?.inn]);

  const ask = async (question: string) => {
    const clean = question.trim();
    if (!clean || busy || !report) return;
    setInput('');
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', text: clean }]);
    setBusy(true);
    try {
      const reply = await askAboutCounterparty(report.inn, clean, sessionId);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'agent', text: reply.answer, sections: reply.sections },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'failure',
          text: error instanceof Error ? error.message : 'Сервис разбора сейчас недоступен',
        },
      ]);
      onToast('Разбор недоступен — отчёт остаётся полным');
    } finally {
      setBusy(false);
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
              <p className="agent-message__text">{message.text}</p>
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

        {busy && (
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
