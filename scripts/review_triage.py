#!/usr/bin/env python3
"""Собрать карточки разбора из очереди комментариев vibe-debug.

Скрипт делает только механическую часть: тянет из записи экран, объект, автора,
дословный текст, вложения и ссылку на комментарий. Классификацию, разбор и
промпт исполнителю дописывает агент, строку «Решение» — человек.

Существующие карточки не трогает: при повторном запуске дописывает только
комментарии, которых в файле ещё нет.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_schema import load_schema, split_legacy, validate  # noqa: E402

PREVIEW = "https://tt-hack-review.72.56.16.44.sslip.io"
OPEN_STATUSES = ("new", "approved", "in_progress")
CARD_ID = re.compile(r"^### (DBG-[0-9A-F]{10})", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--status",
        action="append",
        default=None,
        help=f"какие статусы брать, по умолчанию {', '.join(OPEN_STATUSES)}",
    )
    parser.add_argument("--route", default="", help="ограничить одним маршрутом")
    return parser.parse_args()


def short(text: str, limit: int = 64) -> str:
    flat = " ".join(text.split())
    flat = re.sub(r"\[скриншот#[0-9A-F]{10}\]", "", flat).strip()
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


def describe_target(comment: dict[str, Any]) -> str:
    target = comment.get("target") or {}
    element = target.get("element") or "?"
    selector = comment.get("selector") or target.get("selector") or ":root"
    label = target.get("label") or target.get("heading") or ""
    name = f" — «{label}»" if label else ""
    return f"`{element}` `{selector}`{name}"


def describe_page(comment: dict[str, Any]) -> str:
    page = comment.get("page") or {}
    route = comment.get("route") or page.get("route") or "?"
    title = page.get("title") or ""
    return f"`{route}`" + (f" — {title}" if title else "")


def describe_author(comment: dict[str, Any]) -> str:
    author = comment.get("author") or "?"
    created = (comment.get("createdAt") or "").replace("T", " ").rstrip("Z")
    viewport = comment.get("viewport") or {}
    size = f"{viewport.get('width', '?')}×{viewport.get('height', '?')}"
    mode = comment.get("mode") or "—"
    return f"{author} · {created} UTC · {size} · режим {mode}"


def describe_attachments(comment: dict[str, Any]) -> str:
    attachments = comment.get("attachments") or []
    if not attachments:
        return "—"
    return ", ".join(
        f"`{item['id']}` ({item.get('width', '?')}×{item.get('height', '?')})"
        for item in attachments
    )


def quote(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
    return "\n".join(f"> {line}" for line in lines) or "> —"


def card(comment: dict[str, Any]) -> str:
    comment_id = comment["id"]
    route = comment.get("route") or "/"
    link = f"{PREVIEW}{route}?vibe-comment={comment_id}"
    return f"""### {comment_id} · {short(comment.get("text", ""))}

| | |
|---|---|
| Экран | {describe_page(comment)} |
| Объект | {describe_target(comment)} |
| Автор | {describe_author(comment)} |
| Вложения | {describe_attachments(comment)} |
| Статус | `{comment.get("status", "new")}` |
| Открыть | {link} |

**Дословно:**

{quote(comment.get("text", ""))}

**Класс:** _content / ux / scope / question / bug / fyi_

**Что понято:** _агент: что именно просят, в терминах экрана и файлов_

**Что не понято:** _агент: чего не хватает, чтобы правка была однозначной_

**Затрагивает:** _агент: файлы и сквозные компоненты_

**Решение:** _человек: принять / отклонить / вопрос заказчику — до этой строки исполнитель не работает_

**Промпт исполнителю:**

```text
агент: заполняется после решения
```

**Проверка:** _чем подтверждаем, что закрыто_

---
"""


def main() -> int:
    args = parse_args()
    statuses = tuple(args.status) if args.status else OPEN_STATUSES

    comments = json.loads(args.comments.read_text(encoding="utf-8"))
    schema = load_schema()
    for comment in comments:
        hard, _ = split_legacy(validate(comment, schema))
        if hard:
            print(f"{comment.get('id')}: {hard[0]}", file=sys.stderr)
            return 1

    selected = [
        comment
        for comment in comments
        if comment.get("status") in statuses
        and (not args.route or comment.get("route") == args.route)
    ]
    selected.sort(key=lambda item: (item.get("route", ""), item.get("createdAt", "")))

    existing = args.out.read_text(encoding="utf-8") if args.out.is_file() else ""
    known = set(CARD_ID.findall(existing))
    fresh = [comment for comment in selected if comment["id"] not in known]

    if not fresh:
        print(f"новых карточек нет, в {args.out} уже {len(known)}")
        return 0

    body = "".join(card(comment) for comment in fresh)
    if existing:
        args.out.write_text(existing.rstrip() + "\n\n" + body, encoding="utf-8")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")

    print(f"добавлено карточек: {len(fresh)}, всего в файле: {len(known) + len(fresh)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
