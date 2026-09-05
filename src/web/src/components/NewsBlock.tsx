import { Link } from '@alfalab/core-components-link';
import { Skeleton } from '@alfalab/core-components-skeleton';
import { Status } from '@alfalab/core-components-status';
import { Typography } from '@alfalab/core-components-typography';

import type { CompanyNews } from '../types';

/**
 * Новости о компании из внешних источников.
 *
 * Отдельным блоком под разделами, а не картой в их сетке: разделы собраны
 * из отчёта кейсодателя, а это найдено снаружи. Кейсодатель задал иерархию
 * дословно — внешнее либо не конфликтует с отчётом, либо им подтверждается,
 * и смешивать одно с другим нельзя. Отсюда и ссылка у каждой находки:
 * единственное, чем внешнее сведение можно проверить.
 *
 * Четыре состояния, а не два. «Ищем», «не нашлось», «не дозвонились»
 * и «вот что нашли» — разные сообщения, и подменять третье вторым значит
 * выдавать сбой связи за факт о компании.
 */

const LEVEL_LABEL: Record<string, string> = {
  'тревожная': 'Есть на что обратить внимание',
  'нейтральная': 'Тревожного не нашлось',
};

export function NewsBlock({ news }: { news: CompanyNews | null | undefined }) {
  // Поиск не настроен — блока нет вовсе. Пустой блок читался бы как
  // «про компанию не пишут», хотя мы просто не смотрели.
  if (news === undefined) return null;

  return (
    <section className="news" aria-label="Новости из внешних источников">
      <header className="news__head">
        <div>
          <Typography.Title tag="h2" view="xsmall" font="styrene" weight="bold">
            Что пишут снаружи
          </Typography.Title>
          <p className="news__note">
            Найдено в открытых источниках и отчётом не подтверждено. Проверяйте по ссылке.
          </p>
        </div>
        {news && !news.failed && news.level && (
          <Status size={20} view="soft" color={news.level === 'тревожная' ? 'red' : 'green'}>
            {LEVEL_LABEL[news.level]}
          </Status>
        )}
      </header>

      {!news && (
        <div className="news__items" aria-live="polite">
          <Skeleton visible className="news__skeleton" />
          <Skeleton visible className="news__skeleton" />
        </div>
      )}

      {news?.failed && (
        <p className="news__empty">
          Внешний поиск сейчас не отвечает. Это сбой связи, а не утверждение о компании —
          отчёт выше остаётся полным.
        </p>
      )}

      {news && !news.failed && news.items.length === 0 && (
        <p className="news__empty">В открытых источниках про эту компанию ничего не нашлось.</p>
      )}

      {news && !news.failed && news.items.length > 0 && (
        <ul className="news__items">
          {news.items.map((item) => (
            <li key={item.url} className={`news-item news-item--${item.level === 'тревожная' ? 'alarming' : 'neutral'}`}>
              <p className="news-item__summary">{item.summary || item.title}</p>
              <Link
                href={item.url}
                view="default"
                target="_blank"
                rel="noopener noreferrer nofollow"
              >
                {sourceName(item.url)}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Домен вместо полного адреса: он и есть имя источника, а адрес занимает строку. */
function sourceName(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}
