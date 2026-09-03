"""Заголовки негативных факторов.

Объяснения берём из данных — поле `name` заполнено у всех 217 факторов. Свои пишем
только заголовки: текст фактора медианно 248 символов и в карточку не помещается.

Тест на настоящей выгрузке пропускается там, где её нет; проверка полноты словаря
работает только имея набор, потому что смысл её именно в сверке со всеми кодами.
"""

import pytest

from core.factors import HEADINGS, heading, weight
from core.repo import load

pytestmark_data = pytest.mark.skipif(True, reason="переопределяется ниже")


def test_заголовок_не_повторяет_код():
    """Иначе пользователь увидит massOkved — ровно то, что запрещено."""
    for code, text in HEADINGS.items():
        assert text != code
        assert not text.isascii(), f"{code}: заголовок должен быть на русском, а не {text!r}"


def test_неизвестный_код_не_роняет_и_не_показывает_себя():
    """Появится новый код — интерфейс не должен показать его как есть."""
    got = heading("совершенноНовыйКод")
    assert "совершенноНовыйКод" not in got
    assert got.strip()


def test_значимость_задана_для_всех_известных_кодов():
    for code in HEADINGS:
        assert weight(code) >= 1


def test_значимость_у_неизвестного_кода_минимальна():
    assert weight("новыйКод") == min(weight(c) for c in HEADINGS)


try:
    _RECORDS = load().counterparties
except RuntimeError:
    _RECORDS = ()


@pytest.mark.skipif(not _RECORDS, reason="набор не собран — нечего сверять")
def test_все_коды_из_выгрузки_имеют_заголовок():
    """Главная проверка: словарь покрывает то, что реально приходит.
    Прежний словарь в интерфейсе покрывал 4 кода из 15."""
    коды = {
        f["code"]
        for r in _RECORDS
        for f in ((r.get("reputationalRisks") or {}).get("negative") or [])
    }
    непокрытые = sorted(коды - set(HEADINGS))
    assert непокрытые == [], f"без заголовка остались: {непокрытые}"
