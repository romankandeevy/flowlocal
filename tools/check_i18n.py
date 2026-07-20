"""Какие строки интерфейса остались без английского перевода.

    python tools/check_i18n.py           # список непереведённых
    python tools/check_i18n.py --stub    # заготовка для вставки в i18n.py

Зачем инструмент, а не внимательность. Ключ перевода - сама русская строка
(см. i18n.py), поэтому забытый перевод ничего не ломает: строка просто
остаётся русской. Это хорошее свойство - пустая кнопка хуже кнопки на чужом
языке, - но у него есть цена: заметить пропажу можно только глазами, открыв
английский интерфейс и пройдя все страницы. Так и вышло, что половина словаря
лежала мёртвым грузом, а «оформление» и «устройство» оставались русскими.

Ищем `L.t("...")` в qml/ и сверяем со словарём. Составные подписи собираются
из кусков - `L.t("часть один ") + L.t("часть два")`, - и каждый кусок здесь
отдельная строка: так они и лежат в словаре.

Не находит: строки, собранные в Python и отданные в QML готовыми (подписи
списков вроде B.themeOptions). Их немного, они перечислены в i18n.py своим
разделом, и подставляются через L.t уже в Segmented/Select.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402

# L.t("строка") и L.t('строка'). Многострочные вызовы не ищем: их в проекте
# нет, а regexp на них разрастается до нечитаемого.
CALL = re.compile(r"""L\.t\(\s*(["'])(.+?)\1\s*\)""", re.S)


def strings() -> dict[str, list[str]]:
    """Строка -> в каких файлах встретилась."""
    found: dict[str, list[str]] = {}
    qml = os.path.join(ROOT, "qml")
    # Обход рекурсивный: с 19.07.2026 qml/ поделена на controls/ и windows/, а
    # плоский listdir в такой папке нашёл бы ноль файлов и честно отрапортовал
    # «непереведённых нет». Инструмент, который молчит тем громче, чем больше
    # он пропустил, хуже отсутствующего.
    for root, _dirs, names in os.walk(qml):
        for name in sorted(names):
            if not name.endswith(".qml"):
                continue
            with open(os.path.join(root, name), encoding="utf-8") as f:
                for _q, text in CALL.findall(f.read()):
                    # Переменные в вызове (L.t(modelData.title)) сюда не
                    # попадают - их не сматчит кавычка. Это правильно: что там
                    # за строка, известно только в работе.
                    found.setdefault(text, []).append(name)
    return found


def main() -> int:
    found = strings()
    missing = {s: files for s, files in found.items() if s not in i18n.EN}
    print(f"строк в qml/: {len(found)}, в словаре: {len(i18n.EN)}")
    if not missing:
        print("непереведённых нет")
        return 0

    print(f"без перевода: {len(missing)}\n")
    if "--stub" in sys.argv:
        # Заготовка для вставки: остаётся дописать правую часть.
        for s in missing:
            print(f'    {s!r}: "",')
        return 1
    for s, files in sorted(missing.items(), key=lambda p: p[1][0]):
        where = ", ".join(sorted(set(files)))
        print(f"  [{where}] {s[:70]}")
    print("\nзаготовка для i18n.py: python tools/check_i18n.py --stub")
    return 1


if __name__ == "__main__":
    sys.exit(main())
