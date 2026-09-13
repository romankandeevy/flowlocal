"""Заметки: хранение, поиск, уборка.

Окна здесь нет - проверяем то, где теряются данные: запись, чтение, удаление,
поиск и обезвреживание пути. Заметка - самое личное, что программа хранит,
и потерять её нельзя.

Запуск: python test_notes.py
"""

import os
import sys
import tempfile
import time

import notes

ok = True


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


def main() -> int:
    notes.DIR = tempfile.mkdtemp()

    # --- заголовок ---
    check(notes.title_of("Первая строка\nвторая") == "Первая строка",
          "заголовок - первая строка, а не весь текст")
    check(notes.title_of("") == "Без названия",
          "пустая заметка не зияет в списке безымянной строкой")
    check(notes.title_of("   \n  ") == "Без названия",
          "одни пробелы - тоже «Без названия»")
    long = notes.title_of("с" * 200)
    check(len(long) <= notes.TITLE_MAX,
          f"длинный заголовок обрезан ({len(long)} знаков), иначе список - стена")
    check(notes.title_of("много   пробелов   подряд") == "много пробелов подряд",
          "пробелы в заголовке схлопываются")

    # --- запись и чтение ---
    a = notes.save(notes.new_id(), "Разбор Wispr\nПосмотрел меню")
    check(bool(a), "заметка записалась")
    d = notes.load(a)
    check(d is not None and d["text"].startswith("Разбор Wispr"),
          "и прочиталась обратно дословно")
    check(d["title"] == "Разбор Wispr", "заголовок считается при чтении")

    time.sleep(1.1)          # идентификатор - метка времени с точностью до секунды
    b = notes.save(notes.new_id(), "Список покупок: хлеб, молоко")
    check(a != b, "у двух заметок разные идентификаторы")

    # --- список ---
    items = notes.listing()
    check(len(items) == 2, "в списке обе")
    check(items[0]["id"] == b,
          "свежая первой: список отсортирован по возрасту, а не по алфавиту")
    check("слов" in items[0]["note"] or "слова" in items[0]["note"],
          f"в строке списка счёт слов: {items[0]['note']!r}")

    # --- правка не плодит копий ---
    notes.save(a, "Разбор Wispr\nДописал про трансформы")
    check(len(notes.listing()) == 2, "правка обновляет заметку, а не создаёт вторую")
    check(notes.load(a)["text"].endswith("трансформы"), "правка сохранилась")
    check(notes.load(a)["created"] == a,
          "дата создания при правке не меняется - иначе заметка прыгала бы "
          "в конец списка каждый раз, как её тронули")

    # --- поиск ---
    check(len(notes.listing("хлеб")) == 1, "поиск находит по содержимому")
    check(len(notes.listing("ХЛЕБ")) == 1, "поиск не зависит от регистра")
    check(len(notes.listing("нетакогослова")) == 0, "ничего не нашлось - пустой список")
    check(len(notes.listing("")) == 2, "пустой запрос показывает всё")

    # --- ЛОВУШКИ ---
    check(notes.load("нет-такой") is None,
          "чтение несуществующей заметки даёт None, а не падение")
    notes.delete("нет-такой")
    check(True, "удаление несуществующей не падает")

    # Путь наружу. Идентификаторы приходят из наших же файлов, но проверить
    # дешевле, чем однажды записать заметку поверх config.json.
    p = notes._path("../../config")
    check(os.path.dirname(os.path.abspath(p)) == os.path.abspath(notes.DIR),
          "идентификатор с «../» не выводит за папку заметок")
    p2 = notes._path("a/b\\c")
    check("/" not in os.path.basename(p2) and "\\" not in os.path.basename(p2),
          "разделители пути из идентификатора вычищаются")

    # --- удаление ---
    notes.delete(a)
    check(len(notes.listing()) == 1, "удалённая заметка ушла из списка")
    check(notes.load(a) is None, "и не читается")

    # --- пустая заметка живёт ---
    c = notes.save(notes.new_id(), "")
    check(notes.load(c) is not None,
          "пустая заметка сохраняется: человек нажал «Новая» и ещё не начал")

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
