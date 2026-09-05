import { Indicator } from '@alfalab/core-components-indicator';
import { TooltipDesktop } from '@alfalab/core-components-tooltip/desktop';

import { STATE_COLOR, STATE_LABEL } from '../state';
import type { ReportSectionData } from '../types';

/**
 * Навигация по разделам — восемь точек справа от полосы разбора.
 *
 * Ведёт к разделу, а не открывает его: подробности показывает сама карточка
 * по нажатию. Разные действия у одного раздела — не путаница, а два разных
 * намерения: «покажи, где это» и «покажи подробнее».
 *
 * Отчёт делает две работы. Первая, «что вообще проверено и где горит», карточек
 * не требует: восьми точек достаточно, и они помещаются в узкую колонку рядом
 * с разговором. Вторая, «покажи подробности», остаётся за карточками ниже.
 *
 * Порядок разделов постоянный: пользователь запоминает, где что, и переставлять
 * их по значимости значило бы отнимать эту память ради одного взгляда.
 *
 * Цвет — не единственный носитель: состояние названо словами в подсказке
 * и в `aria-label`, иначе список нечитаем без различения цветов.
 */
export function SectionNav({
  sections,
  onGo,
}: {
  sections: ReportSectionData[];
  /** Перейти к разделу в отчёте. Именно перейти, а не открыть: список
   *  из восьми пунктов обещает перемещение между ними, и подмена отчёта
   *  подробным видом это обещание не выполняет — после каждого пункта
   *  пришлось бы возвращаться назад. */
  onGo: (key: string) => void;
}) {
  if (sections.length === 0) return null;

  const сигналов = sections.filter((section) => section.state === 'signal').length;
  const пустых = sections.filter(
    (section) => section.state === 'empty' || section.state === 'not_applicable',
  ).length;

  return (
    <nav className="section-nav" aria-label="Разделы отчёта">
      <span className="section-nav__head">Разделы</span>

      <div className="section-nav__items">
        {sections.map((section) => (
          <TooltipDesktop
            key={section.key}
            content={STATE_LABEL[section.state]}
            position="left"
          >
            <button
              type="button"
              className="section-nav__item"
              onClick={() => onGo(section.key)}
              aria-label={`Перейти к разделу «${section.title}»: ${STATE_LABEL[section.state]}`}
            >
              <Indicator size={8} backgroundColor={STATE_COLOR[section.state]} />
              <span>{section.title}</span>
            </button>
          </TooltipDesktop>
        ))}
      </div>

      {/* Отвечает на вопрос, который восемь точек оставляют открытым: сколько
          из них молчат не потому, что чисто, а потому, что данных нет. */}
      <span className="section-nav__summary">
        {сигналов > 0 ? `${сигналов} с сигналом` : 'Сигналов нет'}
        {пустых > 0 && ` · ${пустых} без данных`}
      </span>
    </nav>
  );
}
