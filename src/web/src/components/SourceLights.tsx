import type { ReactNode } from 'react';

import { AlfaWordmark, BankOfRussiaLogo } from './Logos';
import type { OwnVerdict } from '../types';
import type { Verdict } from '../verdict';

type Light = { known: boolean; value: string };

type Tone = 'green' | 'orange' | 'red' | 'grey';

function tone(light: Light): Tone {
  if (!light.known) return 'grey';
  if (light.value === 'Красный' || light.value === 'Высокий') return 'red';
  if (light.value === 'Жёлтый' || light.value === 'Средний') return 'orange';
  return 'green';
}

/** Своё состояние — в тот же цвет, что и чужие оценки. Отдельная палитра
 *  сделала бы из трёх плашек три разные шкалы. */
const СВОЙ_ТОН: Record<OwnVerdict['state'], Tone> = {
  clean: 'green',
  clarify: 'orange',
  attention: 'red',
  unknown: 'grey',
};

/** Оценка словами, а не значением из данных.
 *
 * «Низкий» и «Зелёный» — это шкалы, а не вывод: чтобы прочитать их, надо знать,
 * низкий чего и зелёный по какому основанию.
 *
 * Три оценки стоят рядом и потому обязаны называть, что именно каждая измеряет.
 * Банк считает надёжность контрагента по своей — нераскрываемой — методике,
 * ЗСК оценивает риск операций, сервис смотрит, сходятся ли разделы отчёта между
 * собой. Одинаковые слова на трёх плашках («низкий риск» × 3) читались бы как
 * согласие трёх независимых источников, а весь смысл этого ряда в том, что они
 * расходятся: у МАКСМАРКЕТА два зелёных при 2,6 млрд ₽ исков.
 */
const BANK_WORDS: Record<Tone, string> = {
  green: 'низкий риск по скорингу',
  orange: 'средний риск по скорингу',
  red: 'высокий риск по скорингу',
  grey: 'скоринга нет',
};

const ZSK_WORDS: Record<Tone, string> = {
  green: 'низкий риск операций',
  orange: 'средний риск операций',
  red: 'высокий риск операций',
  grey: 'оценки нет',
};

/** Запасные слова своей оценки — ровно те же, что у сервера (`compare.СЛОВАМИ`).
 *  Своих формулировок здесь быть не должно: одна компания называлась бы в отчёте
 *  и в сравнении по-разному, а различить, две это оценки или одна, читателю
 *  было бы нечем. Нужны, только когда отчёт собран без сервера. */
const OWN_FALLBACK: Record<Verdict['level'], string> = {
  clean: 'вопросов нет',
  clarify: 'есть вопросы',
  attention: 'осторожнее',
};

/**
 * Три оценки контрагента в один ряд: наша, скоринг банка и платформа ЗСК Банка
 * России. Чужие две сервис не пересчитывает, только показывает.
 *
 * Своя стоит первой и подписана названием сервиса, а не логотипом: читатель
 * должен видеть, что вывод даёт та страница, на которой он находится, — иначе
 * третья плашка выглядит как ещё одно чужое мнение неизвестного происхождения.
 *
 * Владелец каждой оценки назван своим знаком: знак читается раньше текста,
 * а «чья это оценка» — первое, что нужно знать, чтобы понять, почему сервис
 * чужую не оспаривает.
 *
 * Предмет измерения ушёл в подсказку, а не стоит подписью на плашке. На макете
 * плашка одна строка, и подпись под знаком банка означала бы, что мы объясняем
 * и чужую методику тоже, — а её нам не раскрывают.
 */
export function SourceLights({ bank, zsk, own, verdict }: {
  bank: Light;
  zsk: Light;
  /** Оценка сервера. Слова и четвёртое состояние — его, не наши. */
  own?: OwnVerdict;
  /** Тот же вывод, посчитанный на клиенте: нужен, когда отчёта сервера нет. */
  verdict: Verdict;
}) {
  const ownTone = own ? СВОЙ_ТОН[own.state] : СВОЙ_ТОН[verdict.level];
  const ownWords = own ? own.wording : OWN_FALLBACK[verdict.level];
  // «Оценить нечем» без ответа «чего именно не хватило» — половина ответа.
  const ownGaps = own?.state === 'unknown' && own.gaps.length > 0
    ? `нет данных: ${own.gaps.join(', ').toLowerCase()}`
    : null;

  return (
    <div className="source-lights">
      <Rating
        owner={<span className="rating__own">Проверка контрагента</span>}
        title="Оценка сервиса: сходятся ли разделы отчёта между собой"
        tone={ownTone}
        words={ownWords}
        note={ownGaps}
      />
      <div className="source-lights__external">
        <Rating
          owner={<AlfaWordmark className="rating__logo rating__logo--alfa" />}
          title="Скоринг Альфа-Банка"
          tone={tone(bank)}
          words={BANK_WORDS[tone(bank)]}
          raw={bank.known ? bank.value : null}
        />
        <Rating
          owner={<BankOfRussiaLogo className="rating__logo rating__logo--cbr" />}
          title="Платформа «Знай своего клиента» Банка России"
          tone={tone(zsk)}
          words={ZSK_WORDS[tone(zsk)]}
          raw={zsk.known ? zsk.value : null}
        />
      </div>
    </div>
  );
}

function Rating({ owner, title, tone: t, words, raw, note }: {
  owner: ReactNode;
  title: string;
  tone: Tone;
  words: string;
  /** Значение как оно пришло в данных. В подсказке, а не на плашке: на плашке
   *  оно повторяло бы вывод другими словами и требовало знать шкалу. */
  raw?: string | null;
  note?: string | null;
}) {
  return (
    <div className="rating">
      {owner}
      <strong
        className={`rating__value rating__value--${t}`}
        title={raw ? `${title}: ${raw}` : title}
      >
        {words}
      </strong>
      {note && <span className="rating__note">{note}</span>}
    </div>
  );
}
