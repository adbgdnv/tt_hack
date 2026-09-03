import { useEffect, useMemo, useRef, useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { Tag } from '@alfalab/core-components-tag';
import { blockQuestions, scenarioAnswer } from '../fixtures';
import type { AgentAnswer, BlockKey, ChatMessage, Counterparty, Proof } from '../types';

type Props = {
  company: Counterparty;
  contextBlock: BlockKey | null;
  onOpenProof: (block: BlockKey) => void;
  onToast: (message: string) => void;
};

const stages = ['Ищем компанию', 'Собираем факты', 'Готовим объяснение'];

function AnswerCard({ answer, onOpenProof, streamingText }: { answer?: AgentAnswer; onOpenProof: (block: BlockKey) => void; streamingText?: string }) {
  if (!answer) return <div className="stream-text">{streamingText}<span className="stream-caret" /></div>;
  const parts = [
    ['Факт', answer.fact],
    ['Интерпретация', answer.interpretation],
    ['Чего не хватает', answer.gap],
    ['Что проверить', answer.next],
  ];
  return (
    <div className="answer-contract">
      {parts.map(([label, text]) => (
        <div key={label} className="answer-part">
          <span>{label}</span>
          <p>{text}</p>
        </div>
      ))}
      {answer.proofs.length > 0 && (
        <div className="proofs" aria-label="Подтверждающие факты">
          {answer.proofs.map((proof) => <ProofWidget key={`${proof.block}-${proof.value}`} proof={proof} onOpen={() => onOpenProof(proof.block)} />)}
        </div>
      )}
    </div>
  );
}

function ProofWidget({ proof, onOpen }: { proof: Proof; onOpen: () => void }) {
  return (
    <div className="proof">
      <button className="proof__button" type="button" onClick={onOpen} aria-label={`${proof.value}, ${proof.label}. Открыть источник`}>
        <strong>{proof.value}</strong>
        <span>{proof.label}</span>
      </button>
      <Tag size={32} view="muted">{proof.source}</Tag>
    </div>
  );
}

export function ChatPanel({ company, contextBlock, onOpenProof, onToast }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [stage, setStage] = useState(-1);
  const [streamingText, setStreamingText] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const isBusy = stage >= 0 || Boolean(streamingText);
  const suggestions = useMemo(() => contextBlock ? blockQuestions[contextBlock] : company.questions, [company.questions, contextBlock]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, stage, streamingText]);

  useEffect(() => {
    setMessages([]);
    setInput('');
    setStage(-1);
    setStreamingText('');
  }, [company.inn]);

  const ask = async (question: string) => {
    const clean = question.trim();
    if (!clean || isBusy) return;
    setInput('');
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', text: clean }]);
    for (let index = 0; index < stages.length; index += 1) {
      setStage(index);
      await new Promise((resolve) => window.setTimeout(resolve, 420));
    }
    setStage(-1);
    const answer = scenarioAnswer(company, clean, contextBlock ?? undefined);
    const lead = 'Готово. Разбираю только факты из входного отчёта.';
    for (let index = 1; index <= lead.length; index += 2) {
      setStreamingText(lead.slice(0, index));
      await new Promise((resolve) => window.setTimeout(resolve, 18));
    }
    setStreamingText('');
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'agent', text: lead, answer }]);
  };

  return (
    <aside className="chat-panel" aria-label="Диалог с ИИ">
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
          <p>{company.summary}</p>
          <span className="summary-note">Банковский светофор не пересчитывается.</span>
        </div>
        {messages.map((message) => message.role === 'user' ? (
          <div className="user-message" key={message.id}>{message.text}</div>
        ) : (
          <div className="agent-message" key={message.id}>
            <span className="message-author">Ассистент</span>
            <AnswerCard answer={message.answer} onOpenProof={onOpenProof} />
          </div>
        ))}
        {stage >= 0 && (
          <div className="agent-message progress-card" aria-live="polite">
            {stages.map((label, index) => (
              <div className={index <= stage ? 'progress-step progress-step--active' : 'progress-step'} key={label}>
                <span>{index < stage ? '✓' : index === stage ? '●' : '○'}</span>{label}
              </div>
            ))}
          </div>
        )}
        {streamingText && <div className="agent-message"><AnswerCard streamingText={streamingText} onOpenProof={onOpenProof} /></div>}
      </div>
      <div className="chat-composer">
        <div className="chat-suggestions" aria-label="Предложенные вопросы">
          <span>{contextBlock ? `Вопросы · ${company.blocks[contextBlock].title}` : 'Можно спросить'}</span>
          <div>
            {suggestions.map((question) => (
              <button key={question} type="button" onClick={() => void ask(question)} disabled={isBusy}>{question}</button>
            ))}
          </div>
        </div>
        <form className="chat-composer__row" onSubmit={(event) => { event.preventDefault(); void ask(input); }}>
          <InputDesktop
            value={input}
            onChange={(event) => setInput(event.target.value)}
            size={48}
            block
            clear="auto"
            label="Вопрос по отчёту"
            aria-label="Введите вопрос по отчёту"
          />
          <ButtonDesktop size={48} view="accent" type="submit" disabled={!input.trim() || isBusy} aria-label="Отправить вопрос">→</ButtonDesktop>
        </form>
        <div className="chat-save">
          <button type="button" onClick={() => onToast('Постоянная ссылка на чат скопирована')}>🔗 Ссылка</button>
          <button type="button" onClick={() => onToast('Лог чата сохранён как .txt')}>📄 .txt</button>
        </div>
        <p className="chat-disclaimer">Ассистент рекомендует, но не принимает решение за вас.</p>
      </div>
    </aside>
  );
}
