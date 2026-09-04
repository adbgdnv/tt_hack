type Light = { known: boolean; value: string };

type Tone = 'green' | 'orange' | 'red' | 'grey';

function tone(light: Light): Tone {
  if (!light.known) return 'grey';
  if (light.value === 'Красный' || light.value === 'Высокий') return 'red';
  if (light.value === 'Жёлтый' || light.value === 'Средний') return 'orange';
  return 'green';
}

/**
 * Две независимые оценки контрагента — скоринг банка и платформа ЗСК Банка
 * России. Сервис их не пересчитывает, только показывает.
 *
 * Цветом залит весь блок, а не значок рядом с ним: оценка — главное, что
 * пользователь считывает за первые секунды, и она должна читаться боковым
 * зрением. Точку-индикатор и мелкие пояснения убрали: цвет блока и без них
 * говорит то же самое, а подписи растаскивали внимание.
 *
 * Владелец оценки назван текстом, а не значком: «БАНК РОССИИ» рядом с ЗСК —
 * это и есть объяснение, почему сервис её не оспаривает.
 */
export function SourceLights({ bank, zsk }: { bank: Light; zsk: Light }) {
  return (
    <div className="source-lights">
      <div className="source-lights__row">
        <Rating owner="Альфа-Банк" kind="Скоринг" light={bank} />
        <Rating owner="Банк России" kind="Платформа ЗСК" light={zsk} />
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
