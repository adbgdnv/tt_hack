import { Indicator } from '@alfalab/core-components-indicator';
import { Status } from '@alfalab/core-components-status';

type Light = { known: boolean; value: string };

function color(light: Light): 'green' | 'orange' | 'red' | 'grey' {
  if (!light.known) return 'grey';
  if (light.value === 'Красный' || light.value === 'Высокий') return 'red';
  if (light.value === 'Жёлтый' || light.value === 'Средний') return 'orange';
  return 'green';
}

const DOT_COLOR: Record<'green' | 'orange' | 'red' | 'grey', string> = {
  green: '#0d9336',
  orange: '#e07f0e',
  red: '#ec2d20',
  grey: '#9a9da4',
};

/**
 * Обе независимые оценки контрагента — банковский скоринг и платформа ЗСК Банка
 * России — в одном спокойном слое, отдельно от собственного вывода ниже. Сервис
 * их не пересчитывает, только показывает.
 */
export function SourceLights({ bank, zsk }: { bank: Light; zsk: Light }) {
  return (
    <div className="source-lights">
      <span className="eyebrow">Независимые оценки · сервис их не пересчитывает</span>
      <div className="source-lights__row">
        <div className="source-lights__item">
          <div className="source-lights__value">
            <Indicator size={8} backgroundColor={DOT_COLOR[color(bank)]} />
            <Status size={20} view="soft" color={color(bank)}>
              {bank.known ? bank.value : 'Оценить невозможно'}
            </Status>
          </div>
          <div className="source-lights__caption">
            <strong>Скоринг банка</strong>
            <span>методология скоринга не раскрывается</span>
          </div>
        </div>
        <div className="source-lights__item">
          <div className="source-lights__value">
            <Indicator size={8} backgroundColor={DOT_COLOR[color(zsk)]} />
            <Status size={20} view="soft" color={color(zsk)}>
              {zsk.known ? zsk.value : 'Оценить невозможно'}
            </Status>
          </div>
          <div className="source-lights__caption">
            <strong>Платформа ЗСК (Банк России)</strong>
            <span>жёлтый и красный на платформе показываются серым</span>
          </div>
        </div>
      </div>
    </div>
  );
}
