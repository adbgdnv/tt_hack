---
name: alfa-core-components
description: Use when writing React UI with @alfalab/core-components (the core-ds design system) — choosing package imports, wiring up a theme, or debugging missing styles, empty CSS variables, and rejected prop values such as size="m".
---

# @alfalab/core-components

Дизайн-система Альфа-Банка: 132 React-компонента, MIT, React 16.9–19.
[Сторибук с песочницей](https://core-ds.github.io/core-components/) · [core-ds/core-components](https://github.com/core-ds/core-components)

## Установка и импорт

Каждый компонент — отдельный пакет со своей версией. Ставь точечно; метапакет тянет 122 зависимости.

```bash
npm i @alfalab/core-components-button   # точечно — предпочтительно
npm i @alfalab/core-components          # вся библиотека (v50.x)
```

Форма импорта зависит от способа установки — перепутать легко:

```tsx
import { Button } from '@alfalab/core-components-button';   // после точечной установки
import { Button } from '@alfalab/core-components/button';   // после установки метапакета
```

## Тема подключается отдельно

```ts
import '@alfalab/core-components-themes/corp.css';
```

Доступные темы: `click` `corp` `dark` `intranet` `mobile` `site`.

**В v49 путь был другим** — `@alfalab/core-components/themes/corp.css`. Если после апгрейда до 50 отвалилась темизация, причина почти всегда здесь: css в старом пакете был невалидным, темы вынесли в отдельный `@alfalab/core-components-themes`.

Ограничения из официальной документации:

- **одна тема на страницу**;
- **одна палитра на страницу**, по умолчанию bluetint. Если в проекте и bluetint, и indigo — разводи их по отдельным css-бандлам, иначе цвета перезапишут друг друга в общем бандле;
- `dark` красит страницу целиком, перекрасить отдельный блок нельзя. Если нужен именно блок — это не тёмная тема, а `inverted`-версия компонента (`colors='inverted'`).

## Размеры числовые, а не буквенные

Самая частая ошибка в сгенерированном коде: `size="m"` из старых версий библиотеки.

| Компонент | Допустимые `size` |
|---|---|
| `Button` | `32 \| 40 \| 48 \| 56 \| 64 \| 72` |
| Форм-контролы (`Input`, `Select`, `FormControl`, …) | `40 \| 48 \| 56 \| 64 \| 72` |

```tsx
<Button view='accent' size={48} block loading>Проверить</Button>  // ✅
<Button view='accent' size='m'>Проверить</Button>                 // ❌ не соберётся
```

`Button.view`: `accent | primary | secondary | outlined | transparent | text`.

## Точки входа: responsive / desktop / mobile

Корневой импорт отдаёт **responsive**-версию: в бандл попадает и десктопный, и мобильный код, переключение идёт по breakpoint в рантайме.

```tsx
import { Button } from '@alfalab/core-components-button';                  // responsive
import { ButtonDesktop } from '@alfalab/core-components-button/desktop';
import { ButtonMobile } from '@alfalab/core-components-button/mobile';
```

Продукт только десктопный — импортируй `/desktop`, это заметно режет бандл.

В пакете лежат ещё сборки `modern` (современный JS), `cssm` (css-modules) и `moderncssm`. Трогай их только если этого требует сборщик.

## SSR и точка перехода

```bash
npm i @alfalab/core-config
```

```tsx
const coreConfig = useMemo(() => ({ breakpoint: 1024, client: 'desktop' }), []);
```

`breakpoint` — граница между мобильной и десктопной версиями. `client` фиксирует версию для серверного рендера, чтобы responsive-компоненты не дорисовывались на клиенте. Доступно с 48 версии; задаётся один раз глобально вместо переопределения каждого компонента.

## Что пригодится под отчёт по контрагенту

`table` `chart` `status` `tag` `filter-tag` `amount` `badge` `plate` `collapse` `skeleton` `attach` `tooltip` `typography`

## Частые ошибки

| Симптом | Причина |
|---|---|
| Компоненты без цветов, CSS-переменные пустые | не импортирована тема |
| Темизация отвалилась после апгрейда до v50 | старый путь `@alfalab/core-components/themes/…` |
| `Type '"m"' is not assignable to type '40 \| 48 \| …'` | буквенный `size` из старых версий |
| Цвета перебивают друг друга | две палитры в одном css-бандле |
| Модуль не найден | импорт `@alfalab/core-components/button` при точечной установке (или наоборот) |
| Разъезд разметки при гидратации в SSR | не задан `client` в CoreConfig |

Пакеты помечены `sideEffects: ["**/*.css"]`. Не отключай `sideEffects` в сборщике целиком — tree-shaking вытрясет стили.
