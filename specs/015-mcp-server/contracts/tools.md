# Контракт инструментов MCP

Восемь инструментов и один ресурс. Каждый — вызов в ядро; логики здесь нет.

Общее правило ответов: **ненайденное — это ответ, а не ошибка.** Инструмент
возвращает `{"error": "not_found", "detail": ...}`, а не бросает исключение:
исключение доходит до клиента как поломка сервера и обрывает разговор.

## `search_counterparty(query, limit=10) -> list[dict]`

Поиск по ИНН, части названия или ФИО руководителя. Пустой список означает
«в базе нет».

## `get_counterparty_report(inn) -> dict`

Отчёт целиком, поля из выгрузки. Пустое поле — «данных нет», а не «проблем нет».

## `assess_risk(inn) -> dict`

```
{
  "inn", "name", "status", "is_entrepreneur",
  "bank_risk":  {"value", "known", "source"},
  "zsk_risk":   {"value", "known", "source"},
  "contradictions": [{"title", "detail", "section", "evidence": [...]}],
  "sections": [{"key", "title", "state", "checks_passed", "checks_total"}],
  "gaps": ["раздел", ...],
  "signals": int, "unknowns": int
}
```

Числового балла нет и не будет: кейсодатель этого не просил и просил
обратного. `state` раздела — то же трёхсостояние, что на экране.

## `compare_counterparties(inns) -> dict`

```
{
  "summary": {"headline", "detail"},
  "verdicts": [{"inn", "name", "level", "recommendation",
                "reasons": [...], "gaps": [...],
                "checks_passed", "checks_total"}],
  "not_found": ["инн", ...]
}
```

Порядок — от того, к кому меньше вопросов. Тот же, что на экране сравнения:
считает его один и тот же код. Список длиннее предела — отказ с числом.

## `get_financials(inn) -> dict`

```
{"inn", "name", "text", "reports_filed": bool, "is_entrepreneur": bool}
```

`text` — отчётность по годам и коэффициенты словами словаря полей.
`reports_filed: false` при `is_entrepreneur: true` значит «у ИП такого
не бывает», а не «не сдали».

## `look_up(inn, topic) -> dict`

```
{"inn", "topic", "text"}            тема опознана
{"inn", "topic", "topics": "..."}   тема не опознана — перечень доступных
```

Восемь тем: финансы, суды, взыскания, надёжность, управление, деятельность,
реквизиты, налоги.

## `verify_claims(text, inns) -> dict`

```
{
  "total": int,
  "confirmed": int,
  "unverified": [{"number": "строка как в тексте", "context": "..."}]
}
```

Сверяет числа текста с отчётами **всех** названных ИНН. `total: 0` значит
«чисел не было», а не «всё подтверждено».

## `find_contradictions(inn) -> dict`

```
{"inn", "name", "contradictions": [{"title", "detail", "section", "evidence"}]}
```

То, что не видно ни в одном разделе по отдельности: зелёные светофоры при
тяжёлых открытых данных, управляющий вместо директора, долги покупателей
больше выручки, устаревшая отчётность. Пустой список — «противоречий
не нашлось», и это тоже ответ.

## Ресурс `counterparty://{inn}`

Отчёт как адресуемые данные — клиент подкладывает их в контекст сам,
без вызова инструмента.
