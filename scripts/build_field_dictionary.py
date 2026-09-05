"""Словарь полей: официальная спецификация кейсодателя → `src/core/fields.json`.

Собирается заранее и коммитится, а не читается в рантайме. Причина простая:
`data/` — симлинк на каталог вне репозитория, в образ он не попадает, и на
сервере спецификации нет. Тем же приёмом собран набор контрагентов, только
набор не коммитится — в нём ФИО учредителей, а здесь только имена полей.

Описания берутся дословно из `data/GetFullReportResponse.md`: своя редактура
исказила бы смысл, а отвечаем мы за то, что сказал источник. Там, где поля
в спецификации нет, описание пишем сами и помечаем это.

Запуск: python3 scripts/build_field_dictionary.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[1]
СПЕЦИФИКАЦИЯ = КОРЕНЬ / "data" / "GetFullReportResponse.md"
НАБОР = КОРЕНЬ / "dataset" / "counterparties.json"
ВЫХОД = КОРЕНЬ / "src" / "core" / "fields.json"

# Раздел спецификации → раздел отчёта. Спецификация уже разложена по темам,
# и её разложение совпадает с нашими разделами почти один в один.
РАЗДЕЛ = {
    "Общая информация": "registration",
    "Учредители, руководство, структура": "management",
    "Юридические риски": "courts",
    "Финансовые показатели": "finances",
    "Репутационные риски": "registries",
    "Госзакупки": "activity",
}

# На какой вопрос отвечает поле. Теги нужны, чтобы позже подбирать контекст
# по смыслу, а не по пути; сейчас ими же упорядочиваются триггеры.
ТЕГИ: dict[str, tuple[str, ...]] = {
    "finReports": ("финансы",),
    "coefficient": ("финансы",),
    "arbitrationCases": ("суды",),
    "arbitrationByStatus": ("суды",),
    "executionProceedings": ("суды", "взыскания"),
    "reputationalRisks": ("надёжность",),
    "status": ("надёжность",),
    "baseInfo": ("реквизиты",),
    "foundersInfo": ("управление",),
    "relatedCompanies": ("управление",),
    "kindsOfActivityInfo": ("деятельность",),
    "taxSystem": ("деятельность", "налоги"),
    "licenses": ("деятельность",),
    "procurements": ("деятельность",),
    "inspections": ("надёжность",),
    "phones": ("реквизиты",),
    "branchesInfo": ("реквизиты",),
}

# Поля, которых в спецификации нет. Описания наши, и это помечено в `origin`.
#
# Десять из одиннадцати — счётчики арбитража: в спецификации они записаны
# через многоточие (`...dfAmount`), то есть описание там есть, но по точному
# пути не находится. Восстанавливаем его по смыслу префикса: p/d — истец
# или ответчик, f/p/a — завершено, рассматривается, обжалуется.
СВОИ: dict[str, str] = {
    "arbitrationByStatus.plaintiffArbitration.plaintiffArbitrationFinished.pfCount":
        "Завершённых дел, где компания истец",
    "arbitrationByStatus.plaintiffArbitration.plaintiffArbitrationFinished.pfAmount":
        "Сумма требований по завершённым делам, где компания истец",
    "arbitrationByStatus.plaintiffArbitration.plaintiffArbitrationPending.ppCount":
        "Рассматриваемых дел, где компания истец",
    "arbitrationByStatus.plaintiffArbitration.plaintiffArbitrationPending.ppAmount":
        "Сумма требований по рассматриваемым делам, где компания истец",
    "arbitrationByStatus.plaintiffArbitration.plaintiffArbitrationAppealed.paCount":
        "Обжалуемых дел, где компания истец",
    "arbitrationByStatus.plaintiffArbitration.plaintiffArbitrationAppealed.paAmount":
        "Сумма требований по обжалуемым делам, где компания истец",
    "arbitrationByStatus.defandantArbitration.defandantArbitrationFinished.dfCount":
        "Завершённых дел, где компания ответчик",
    "arbitrationByStatus.defandantArbitration.defandantArbitrationFinished.dfAmount":
        "Сумма требований по завершённым делам, где компания ответчик",
    "arbitrationByStatus.defandantArbitration.defandantArbitrationPending.dpCount":
        "Рассматриваемых дел, где компания ответчик",
    "arbitrationByStatus.defandantArbitration.defandantArbitrationPending.dpAmount":
        "Сумма требований по рассматриваемым делам, где компания ответчик",
    "arbitrationByStatus.defandantArbitration.defandantArbitrationAppealed.daCount":
        "Обжалуемых дел, где компания ответчик",
    "arbitrationByStatus.defandantArbitration.defandantArbitrationAppealed.daAmount":
        "Сумма требований по обжалуемым делам, где компания ответчик",
    "foundersInfo.cofounders[].active":
        "Признак, является ли учредитель активным",
}

# Расхождения спецификации с данными. Молча разрешать их в пользу одной
# из сторон нельзя: у следующего читателя не будет способа об этом узнать.
РАСХОЖДЕНИЯ: dict[str, str] = {
    "foundersInfo.cofounders[].active":
        "В спецификации поле называется `isActive`, в данных — `active`",
    "status.reasonName":
        "Спецификация описывает поле как «Причина закрытия организации», "
        "но в данных оно заполнено у действующих компаний и содержит в том числе "
        "«признано несостоятельным (банкротом)». Верим данным",
}

# Короткая подпись для экрана там, где описание спецификации длинное
# или служебное. Всё остальное берёт описание как есть.
ПОДПИСИ: dict[str, str] = {
    "finReports[].common.proceeds": "Выручка",
    "finReports[].common.profit": "Прибыль",
    "finReports[].common.year": "Год отчётности",
    "finReports[].assets.totalAssets": "Активы",
    "finReports[].assets.currentAssets.stocks": "Запасы",
    "finReports[].assets.currentAssets.receivables": "Дебиторская задолженность",
    "finReports[].assets.currentAssets.bankroll": "Денежные средства",
    "finReports[].assets.uncurrentAssets.total": "Внеоборотные активы",
    "finReports[].liabilities.capitals": "Собственный капитал",
    "finReports[].liabilities.totalLiabilities": "Пассивы",
    "finReports[].liabilities.shortTermLiabilities.accountsPayable": "Кредиторская задолженность",
    "finReports[].liabilities.shortTermLiabilities.borrowedFunds": "Заёмные средства",
    "executionProceedings[].active": "Признак действующего производства",
    "executionProceedings[].date": "Дата возбуждения производства",
    "arbitrationCases[].plaintiffAmount": "Сумма исков, поданных компанией",
    "arbitrationCases[].defendantAmount": "Сумма исков, предъявленных компании",
}


def из_спецификации() -> dict[str, tuple[str, str]]:
    """Путь → (описание, раздел спецификации). Таблицы вида `| `поле` | смысл |`."""
    текст = СПЕЦИФИКАЦИЯ.read_text(encoding="utf-8")
    поля: dict[str, tuple[str, str]] = {}
    раздел = ""
    for строка in текст.splitlines():
        if строка.startswith("## "):
            раздел = строка.strip("# *").strip()
        совпало = re.match(r"\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|", строка)
        if совпало:
            поля[совпало.group(1)] = (совпало.group(2).strip(), раздел)
    return поля


def пути_набора() -> dict[str, int]:
    """Листовые пути данных и у скольких компаний каждый заполнен.

    Пустое значение не считается заполненным: поле, которое есть у всех
    и везде пустое, — это не покрытие, а видимость покрытия.
    """
    записи = json.loads(НАБОР.read_text(encoding="utf-8"))["counterparties"]
    счёт: dict[str, int] = {}
    for запись in записи:
        видел: set[str] = set()

        def обойти(узел: object, путь: str = "") -> None:
            if isinstance(узел, dict):
                for ключ, значение in узел.items():
                    обойти(значение, f"{путь}.{ключ}" if путь else ключ)
            elif isinstance(узел, list):
                # схема одинакова у всех элементов — хватит первого
                for элемент in узел[:1]:
                    обойти(элемент, f"{путь}[]")
            elif узел not in (None, "", []):
                видел.add(путь)

        обойти(запись)
        for путь in видел:
            счёт[путь] = счёт.get(путь, 0) + 1
    return счёт


def теги(путь: str, раздел_спеки: str) -> list[str]:
    корень = путь.split(".")[0].removesuffix("[]")
    свои = ТЕГИ.get(корень, ())
    return sorted({*свои, *( (раздел_спеки,) if раздел_спеки else () )})


def собрать() -> dict:
    спека = из_спецификации()
    заполненность = пути_набора()
    всего = len(json.loads(НАБОР.read_text(encoding="utf-8"))["counterparties"])

    статьи = {}
    for путь in sorted(set(заполненность) | set(СВОИ)):
        описание, раздел_спеки = спека.get(путь, ("", ""))
        origin = "spec"
        if not описание:
            описание = СВОИ.get(путь, "")
            origin = "own"
        if not описание:
            # поле есть в данных, описания нет нигде — так и пишем,
            # выдумывать смысл за источник нельзя
            описание = ""
            origin = "unknown"
        статьи[путь] = {
            "label": ПОДПИСИ.get(путь) or описание or путь,
            "description": описание,
            "origin": origin,
            "section": РАЗДЕЛ.get(раздел_спеки, ""),
            "tags": теги(путь, раздел_спеки),
            "filled": заполненность.get(путь, 0),
        }
        if путь in РАСХОЖДЕНИЯ:
            статьи[путь]["conflict"] = РАСХОЖДЕНИЯ[путь]

    return {
        "meta": {
            "источник": "data/GetFullReportResponse.md",
            "компаний_в_наборе": всего,
            "полей": len(статьи),
            "из_спецификации": sum(1 for с in статьи.values() if с["origin"] == "spec"),
            "своих": sum(1 for с in статьи.values() if с["origin"] == "own"),
            "без_описания": sum(1 for с in статьи.values() if с["origin"] == "unknown"),
        },
        "fields": статьи,
    }


def main() -> int:
    if not СПЕЦИФИКАЦИЯ.exists():
        print(f"Нет спецификации: {СПЕЦИФИКАЦИЯ}", file=sys.stderr)
        return 1
    if not НАБОР.exists():
        print(f"Нет набора: {НАБОР}\nСобрать: python3 scripts/build_dataset.py", file=sys.stderr)
        return 1

    словарь = собрать()
    ВЫХОД.write_text(
        json.dumps(словарь, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    м = словарь["meta"]
    print(
        f"{ВЫХОД.relative_to(КОРЕНЬ)}: {м['полей']} полей "
        f"({м['из_спецификации']} из спецификации, {м['своих']} своих, "
        f"{м['без_описания']} без описания)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
