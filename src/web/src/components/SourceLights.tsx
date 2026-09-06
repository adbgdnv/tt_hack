import type { OwnVerdict } from '../types';

type Light = { known: boolean; value: string };

type Tone = 'green' | 'orange' | 'red' | 'grey';

function tone(light: Light): Tone {
  if (!light.known) return 'grey';
  if (light.value === 'Красный' || light.value === 'Высокий') return 'red';
  if (light.value === 'Жёлтый' || light.value === 'Средний') return 'orange';
  return 'green';
}

/** Своё состояние — в тот же цвет, что и чужие оценки. Отдельная палитра
 *  сделала бы из трёх карточек три разные шкалы. */
const СВОЙ_ТОН: Record<OwnVerdict['state'], Tone> = {
  clean: 'green',
  clarify: 'orange',
  attention: 'red',
  unknown: 'grey',
};

/**
 * Три оценки контрагента: скоринг банка, платформа ЗСК Банка России и наша.
 *
 * Первые две сервис не пересчитывает, только показывает. Третья — своя,
 * по открытым данным, и стоит последней намеренно: первыми читаются те,
 * что человек уже знает по банковскому интерфейсу, и наша достраивает
 * картину, а не спорит с порога.
 *
 * Цветом залит весь блок, а не значок рядом с ним: оценка — главное, что
 * пользователь считывает за первые секунды, и она должна читаться боковым
 * зрением. Точку-индикатор и мелкие пояснения убрали: цвет блока и без них
 * говорит то же самое, а подписи растаскивали внимание.
 *
 * Владелец оценки назван текстом, а не значком: «БАНК РОССИИ» рядом с ЗСК —
 * это и есть объяснение, почему сервис её не оспаривает. У своей карточки
 * той же строкой назван предмет измерения: без этого три светофора читаются
 * как одна шкала, а расхождение с зелёной банковской — как «банк ошибся».
 * Обе чужие считаются по банковским операциям и судов не видят; наша —
 * по тому, сходятся ли разделы отчёта между собой.
 *
 * Предмет назван узко намеренно. Замерено на 200 компаниях: у 51 из них
 * на экране есть разделы с сигналом, а расхождений между разделами нет.
 * Подпись «суды, взыскания, реестры, отчётность» обещала бы, что карточка
 * их покрывает, и серое «оценить нечем» рядом с красным разделом читалось бы
 * как «всё чисто». Считать сигнальные разделы наравне с расхождениями тоже
 * нельзя: замерено — 135 компаний из 200 получают «есть вопросы», и карточка
 * перестаёт различать.
 */
export function SourceLights({ bank, zsk, own }: {
  bank: Light;
  zsk: Light;
  own?: OwnVerdict;
}) {
  return (
    <div className="source-lights">
      <div className={`source-lights__row${own ? ' source-lights__row--three' : ''}`}>
        <Rating owner="Альфа-Банк" kind="Скоринг" light={bank} />
        <Rating owner="Банк России" kind="Платформа ЗСК" light={zsk} />
        {own && <Own verdict={own} />}
      </div>
    </div>
  );
}

function Rating({ owner, kind, light }: { owner: string; kind: string; light: Light }) {
  return (
    <div className={`rating rating--${tone(light)}`}>
      <span className="rating__owner">{owner}</span>
      <span className="rating__kind">{kind}</span>
      <strong className="rating__value">{light.known ? light.value : 'Оценить невозможно'}</strong>
    </div>
  );
}

function Own({ verdict }: { verdict: OwnVerdict }) {
  return (
    <div className={`rating rating--${СВОЙ_ТОН[verdict.state]}`}>
      <span className="rating__owner">Проверка контрагента</span>
      <span className="rating__kind">Расхождения между разделами</span>
      <strong className="rating__value">{verdict.wording}</strong>
      {/* Чего не хватило — здесь же, а не отдельной строкой ниже: «оценить
          нечем» без ответа «чего именно» это половина ответа. */}
      {verdict.state === 'unknown' && verdict.gaps.length > 0 && (
        <span className="rating__note">нет данных: {verdict.gaps.join(', ').toLowerCase()}</span>
      )}
    </div>
  );
}
