import { useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { InputDesktop } from '@alfalab/core-components-input/desktop';
import { TagDesktop } from '@alfalab/core-components-tag/desktop';

import type { Deal, DealScheme, DealSide } from '../types';
import { DEAL_SCHEMES, DEAL_SIDES, dealKnown } from '../types';

/**
 * Под какую сделку смотрим отчёт.
 *
 * Пользователь приходит с задачей, а не с интересом к разделам: при авансе
 * решает способность поставить, при отсрочке — способность рассчитаться.
 * Спросить это дешевле, чем ждать, пока человек догадается сам сформулировать
 * условия в вопросе.
 *
 * Формой, а не только вопросом агента: четыре уточнения в чате — это допрос
 * перед первым ответом. Здесь они отвечаются в одно касание и остаются
 * на экране, а недостающее агент спрашивает по ходу разговора.
 *
 * Ничего не обязательно. Пустая форма — законное состояние: выдумывать условия
 * за пользователя нельзя, а без них агент работает как раньше.
 */
export function DealBar({ deal, onChange, disabled }: {
  deal: Deal;
  /** Изменённые поля, а не условия целиком: два клика подряд успевают
   *  случиться до перерисовки, и второй, собранный из прежнего `deal`,
   *  затирал бы первый. */
  onChange: (patch: Deal) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const known = dealKnown(deal);

  // Свёрнутая строка — не украшение: сохранённые условия влияют на каждый
  // следующий ответ, и человек должен видеть, с чем именно ему отвечают.
  // Особенно потому, что часть из них разобрана из его же реплики.
  if (known && !open) {
    return (
      <div className="deal-bar deal-bar--saved">
        <span className="deal-bar__label">Сделка</span>
        <span className="deal-bar__summary">{describe(deal)}</span>
        <button type="button" className="deal-bar__edit" onClick={() => setOpen(true)}>
          Изменить
        </button>
      </div>
    );
  }

  if (!open) {
    return (
      <div className="deal-bar">
        <span className="deal-bar__label">Сделка не описана</span>
        <button type="button" className="deal-bar__edit" onClick={() => setOpen(true)}>
          Рассказать о сделке
        </button>
      </div>
    );
  }

  /** Повторное нажатие снимает выбор: ошибиться в один клик легко, а стереть
   *  выбранное иначе нечем. */
  const toggle = <T extends string>(current: T | null | undefined, next: T) =>
    current === next ? null : next;

  return (
    <div className="deal-bar deal-bar--open">
      <div className="deal-bar__head">
        <span className="deal-bar__label">Под какую сделку смотрим</span>
        <button type="button" className="deal-bar__edit" onClick={() => setOpen(false)}>
          {known ? 'Свернуть' : 'Пропустить'}
        </button>
      </div>

      <div className="deal-bar__row">
        <span>Проверяем</span>
        {DEAL_SIDES.map(({ key, label }) => (
          <TagDesktop
            key={key}
            size={32}
            disabled={disabled}
            checked={deal.side === key}
            onClick={() => onChange({ side: toggle<DealSide>(deal.side, key) })}
          >
            {label}
          </TagDesktop>
        ))}
      </div>

      <div className="deal-bar__row">
        <span>Расчёты</span>
        {DEAL_SCHEMES.map(({ key, label }) => (
          <TagDesktop
            key={key}
            size={32}
            disabled={disabled}
            checked={deal.scheme === key}
            onClick={() => onChange({ scheme: toggle<DealScheme>(deal.scheme, key) })}
          >
            {label}
          </TagDesktop>
        ))}
      </div>

      <div className="deal-bar__row deal-bar__row--fields">
        <InputDesktop
          size={40}
          label="Сумма, ₽"
          labelView="outer"
          disabled={disabled}
          value={deal.sum ? String(deal.sum) : ''}
          inputMode="numeric"
          onChange={(_, { value }) => onChange({ sum: digits(value) })}
        />
        <InputDesktop
          size={40}
          label="Срок, дней"
          labelView="outer"
          disabled={disabled}
          value={deal.days ? String(deal.days) : ''}
          inputMode="numeric"
          onChange={(_, { value }) => onChange({ days: digits(value) })}
        />
      </div>

      <p className="deal-bar__note">
        Ничего не обязательно — чего не хватит, спрошу по ходу. Это ваши слова,
        а не данные отчёта: проверить их нам нечем.
      </p>

      {known && (
        <ButtonDesktop size={40} view="secondary" onClick={() => setOpen(false)}>
          Готово
        </ButtonDesktop>
      )}
    </div>
  );
}

/** Только цифры: поле про сумму и срок, и «60 дней» в нём — уже не число. */
function digits(value: string): number | null {
  const clean = value.replace(/\D/g, '');
  return clean ? Number(clean) : null;
}

/** Строка сохранённых условий: «Поставщик · аванс · 3 000 000 ₽ · 45 дней». */
export function describe(deal: Deal): string {
  const side = DEAL_SIDES.find((item) => item.key === deal.side);
  const scheme = DEAL_SCHEMES.find((item) => item.key === deal.scheme);
  return [
    side && (side.key === 'supplier' ? 'Поставщик' : 'Покупатель'),
    scheme?.label.toLowerCase(),
    deal.sum ? `${deal.sum.toLocaleString('ru-RU')} ₽` : null,
    deal.days ? `${deal.days} дней` : null,
    deal.goal,
  ]
    .filter(Boolean)
    .join(' · ');
}
