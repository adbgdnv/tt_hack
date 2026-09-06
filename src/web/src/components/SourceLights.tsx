import type { ReactNode } from 'react';
import { CheckmarkHexagonMIcon } from '@alfalab/icons-glyph/CheckmarkHexagonMIcon';

import { AlfaWordmark, BankOfRussiaLogo } from './Logos';
import type { Verdict, VerdictState } from '../verdict';

type Light = { known: boolean; value: string };

type Tone = 'green' | 'orange' | 'red' | 'grey';

export function tone(light: Light): Tone {
  if (!light.known) return 'grey';
  if (light.value === 'Красный' || light.value === 'Высокий') return 'red';
  if (light.value === 'Жёлтый' || light.value === 'Средний') return 'orange';
  return 'green';
}

/** Своё состояние — в тот же цвет, что и чужие оценки. Отдельная палитра
 *  сделала бы из трёх плашек три разные шкалы. */
const СВОЙ_ТОН: Record<VerdictState, Tone> = {
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
 * ЗСК оценивает риск операций, сервис смотрит открытые данные: суды, взыскания,
 * реестры, отчётность. Одинаковые слова на трёх плашках («низкий риск» × 3) читались бы как
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



/**
 * Три оценки контрагента в один ряд: наша, скоринг банка и платформа ЗСК Банка
 * России. Чужие две сервис не пересчитывает, только показывает.
 *
 * Своя стоит первой: читатель должен видеть, что вывод даёт та страница,
 * на которой он находится, — иначе третья плашка выглядит как ещё одно чужое
 * мнение неизвестного происхождения.
 *
 * Владелец каждой оценки назван своим знаком — наша в том числе, и потому её
 * знак устроен как у Банка России: значок плюс название, той же высоты и того
 * же веса. Заголовком с подчёркиванием она читалась раньше собственной оценки
 * и выпадала из ряда: в ряду все «кто» должны звучать одинаково тихо, чтобы
 * слышны были «что».
 *
 * Предмет измерения ушёл в подсказку, а не стоит подписью на плашке. На макете
 * плашка одна строка, и подпись под знаком банка означала бы, что мы объясняем
 * и чужую методику тоже, — а её нам не раскрывают.
 *
 * Свой вывод приходит готовым из `deriveVerdict` — тем же вызовом, что и баннер
 * «Обратить внимание» ниже. Второго правила у плашки нет намеренно: пока их было
 * два — на сервере по расхождениям между разделами, на экране по сигнальным
 * разделам, — они расходились у 116 компаний из 200. У восемнадцати баннер
 * говорил «обратить внимание», а плашка над ним — «вопросов нет». Худший случай:
 * СРО «СОМ», 1,26 млрд ₽ исков как ответчику и зелёная плашка.
 */
export function SourceLights({ bank, zsk, verdict }: {
  bank: Light;
  zsk: Light;
  /** Вывод сервиса — тот же, что показывает баннер ниже. */
  verdict: Verdict;
}) {
  // «Оценить нечем» без ответа «чего именно не хватило» — половина ответа.
  const ownGaps = verdict.state === 'unknown' && verdict.gaps.length > 0
    ? `нет данных: ${verdict.gaps.join(', ').toLowerCase()}`
    : null;

  return (
    <div className="source-lights">
      <Rating
        owner={(
          <span className="rating__brand">
            <CheckmarkHexagonMIcon className="rating__brand-mark" />
            <span className="rating__brand-name">Проверка контрагента</span>
          </span>
        )}
        title="Оценка сервиса по открытым данным: суды, взыскания, реестры, отчётность"
        tone={СВОЙ_ТОН[verdict.state]}
        words={verdict.word}
        note={ownGaps}
      />
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
