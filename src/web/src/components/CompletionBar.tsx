import { useState } from 'react';

type Answer = 'yes' | 'partial' | 'no';

/**
 * North Star из product.md: «Получили ли вы достаточно информации для следующего
 * шага?». Ответ остаётся локальным в этой сессии — как и 👍/👎 под ответом
 * ассистента, отправлять его пока некуда: аналитика на бэкенде не заведена, а
 * притворяться, что она есть, значит выдавать интерфейс за то, чем он не является.
 */
export function CompletionBar({ onAnswer }: { onAnswer: (value: Answer) => void }) {
  const [answered, setAnswered] = useState<Answer | null>(null);

  const pick = (value: Answer) => {
    setAnswered(value);
    onAnswer(value);
  };

  return (
    <div className="completion-bar" role="status">
      <span>{answered ? 'Спасибо — это поможет доработать сервис' : 'Хватило информации для следующего шага?'}</span>
      {!answered && (
        <div className="completion-bar__options">
          <button type="button" onClick={() => pick('yes')}>Да</button>
          <button type="button" onClick={() => pick('partial')}>Частично</button>
          <button type="button" onClick={() => pick('no')}>Нет</button>
        </div>
      )}
    </div>
  );
}
