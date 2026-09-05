import { useState } from 'react';
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { Indicator } from '@alfalab/core-components-indicator';
import { InputDesktop } from '@alfalab/core-components-input/desktop';

import { STATE_COLOR } from '../state';
import type { CompareLevel, CompareVerdict } from '../types';

/** Цвет пула берётся из той же таблицы, что и точки разделов: три состояния
 *  одни и те же по всему продукту, и заводить им второй набор цветов значит
 *  однажды их разойтись. */
const ЦВЕТ: Record<CompareLevel, string> = {
  clean: STATE_COLOR.filled,
  clarify: STATE_COLOR.signal,
  attention: STATE_COLOR.signal,
};

const ОТТЕНОК: Record<CompareLevel, string> = {
  clean: '#0d9336',
  clarify: '#ea8313',
  attention: '#ec2d20',
};

/**
 * Пул контрагентов: кого сравниваем.
 *
 * Компании добавляются по ИНН — не по названию: в наборе есть однофамильцы,
 * и «ТЕХПРОМ» без уточнения выбирал бы за пользователя. Название показывается
 * после того, как компания найдена.
 */
export function ComparePool({
  pool,
  verdicts,
  notFound,
  onAdd,
  onRemove,
}: {
  /** Состав пула — источник истины. Рисовать чипы из ответа сервера значит
   *  показывать пустой пул при сбое связи, из которого нечего убрать. */
  pool: string[];
  verdicts: CompareVerdict[];
  notFound: string[];
  onAdd: (inn: string) => void;
  onRemove: (inn: string) => void;
}) {
  const поИнн = new Map(verdicts.map((в) => [в.inn, в]));
  const пропавшие = new Set(notFound);
  const [ввод, setВвод] = useState('');

  const добавить = () => {
    const цифры = ввод.replace(/\D/g, '');
    if (!цифры) return;
    onAdd(цифры);
    setВвод('');
  };

  return (
    <section className="pool" aria-label="Пул контрагентов">
      <span className="lbl">Пул · {pool.length}</span>

      <div className="pool__items">
        {pool.map((inn) => {
          const вердикт = поИнн.get(inn);
          // ИНН, которого нет в наборе, остаётся на виду: молча выбросить
          // компанию из пула значит соврать о составе сравнения.
          const нет = пропавшие.has(inn);
          const подпись = вердикт ? вердикт.name : нет ? `ИНН ${inn} — не найден` : `ИНН ${inn}`;
          return (
            <span className={`pool__chip${нет ? ' pool__chip--missing' : ''}`} key={inn}>
              {вердикт && (
                <Indicator size={8} backgroundColor={ОТТЕНОК[вердикт.level] ?? ЦВЕТ[вердикт.level]} />
              )}
              <span className="pool__name">{подпись}</span>
              <button
                type="button"
                className="pool__remove"
                aria-label={`Убрать ${подпись} из пула`}
                onClick={() => onRemove(inn)}
              >
                ×
              </button>
            </span>
          );
        })}
      </div>

      <form
        className="pool__add"
        onSubmit={(event) => {
          event.preventDefault();
          добавить();
        }}
      >
        <InputDesktop
          size={40}
          value={ввод}
          placeholder="ИНН контрагента"
          aria-label="Добавить контрагента по ИНН"
          onChange={(_, { value }) => setВвод(value)}
        />
        <ButtonDesktop size={40} view="secondary" type="submit" disabled={!ввод.trim()}>
          Добавить
        </ButtonDesktop>
      </form>
    </section>
  );
}
