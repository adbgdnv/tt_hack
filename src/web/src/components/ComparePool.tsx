import { useEffect, useState } from 'react';
import { Indicator } from '@alfalab/core-components-indicator';
import { InputDesktop } from '@alfalab/core-components-input/desktop';

import { searchCounterparties } from '../api';
import { STATE_COLOR } from '../state';
import type { CompareLevel, CompareVerdict, Counterparty } from '../types';

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
 * Поиск тот же, что на главной: по ИНН, названию или ФИО руководителя,
 * с подсказками. Раньше здесь принимался только ИНН — пользователь, знающий
 * компанию по имени, вынужден был идти искать её на другом экране и возвращаться.
 *
 * Выбор идёт из подсказок, а не по введённой строке: в наборе есть
 * однофамильцы — три разных ТЕХПРОМА с разными ИНН, — и добавлять «первого
 * похожего» значило бы выбирать за пользователя.
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
  const [подсказки, setПодсказки] = useState<Counterparty[]>([]);
  const [ищем, setИщем] = useState(false);

  // Поиск с задержкой: без неё запрос уходит на каждую букву. Задержка та же,
  // что на главной, — экраны не должны вести себя по-разному.
  useEffect(() => {
    const строка = ввод.trim();
    if (строка.length < 3) {
      setПодсказки([]);
      setИщем(false);
      return undefined;
    }
    let живо = true;
    setИщем(true);
    const таймер = window.setTimeout(() => {
      void searchCounterparties(строка)
        .then((найдено) => живо && setПодсказки(найдено))
        .catch(() => живо && setПодсказки([]))
        .finally(() => живо && setИщем(false));
    }, 250);
    return () => {
      живо = false;
      window.clearTimeout(таймер);
    };
  }, [ввод]);

  const выбрать = (inn: string) => {
    onAdd(inn);
    setВвод('');
    setПодсказки([]);
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
          // Введён готовый ИНН — добавляем его; иначе ждём выбора из подсказок.
          const цифры = ввод.replace(/\D/g, '');
          if (цифры.length >= 10) выбрать(цифры);
        }}
      >
        <InputDesktop
          size={40}
          block
          clear="auto"
          value={ввод}
          placeholder="ИНН, название или ФИО руководителя"
          aria-label="Добавить контрагента в пул"
          onChange={(_, { value }) => setВвод(value)}
        />

        {подсказки.length > 0 && !ищем && (
          <div className="pool__hints suggestions" role="listbox" aria-label="Подсказки поиска">
            {подсказки.map((компания) => (
              <button
                key={компания.inn}
                type="button"
                role="option"
                onClick={() => выбрать(компания.inn)}
              >
                <span>
                  <strong>{компания.name}</strong>
                  {компания.director && <small>{компания.director}</small>}
                </span>
                <em>ИНН {компания.inn}</em>
              </button>
            ))}
          </div>
        )}

        {ищем && <div className="pool__hints inline-loader"><span />Ищем…</div>}
      </form>
    </section>
  );
}
