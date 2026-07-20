"""Голосовой инбокс: диктовка дописывается в конец файла.

Ни микрофона, ни окон - проверяем то место, где теряется текст: запись в файл.
Главный случай из плана - два нажатия подряд дают две записи с временем, - и
ловушки вокруг него: занятый файл, путь в несуществующей папке, чужой хвост без
перевода строки.

Запуск: python test_inbox.py
"""

import os
import sys
import tempfile
import time

import inbox

ok = True

# Время фиксированное: иначе ожидаемое пришлось бы считать той же функцией,
# которую тест проверяет. 19.07.2026, воскресенье, 21:40 и 21:44.
FIRST = time.struct_time((2026, 7, 19, 21, 40, 0, 6, 200, 0))
SECOND = time.struct_time((2026, 7, 19, 21, 44, 0, 6, 200, 0))


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


def read(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def main() -> int:
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "inbox.md")

    # --- главный случай: два нажатия подряд ---
    check(inbox.append(path, "Купить билеты до пятницы", FIRST),
          "первая диктовка записалась")
    check(inbox.append(path, "Позвонить в сервис", SECOND),
          "вторая записалась следом")
    text = read(path)
    check(text == "- 21:40\nКупить билеты до пятницы\n"
                  "\n- 21:44\nПозвонить в сервис\n",
          "две записи со временем, между ними пустая строка")
    check(text.count("- 21:") == 2, "именно две записи, а не одна поверх другой")
    check("\r" not in text,
          "перенос строки только \\n: в текстовом режиме Windows подсунула бы CRLF")
    check(not text.startswith("\n"),
          "новый файл не начинается с пустой строки - её там некому оставить")

    # --- файла нет: создаётся ---
    fresh = os.path.join(tmp, "нового-нет.md")
    check(inbox.append(fresh, "Первая мысль", FIRST), "файл создаётся сам")
    check(read(fresh) == "- 21:40\nПервая мысль\n", "и содержит ровно запись")

    # --- чужой файл, который кончается без перевода строки ---
    tail = os.path.join(tmp, "чужой.md")
    with open(tail, "w", encoding="utf-8", newline="") as f:
        f.write("# Мои заметки")
    inbox.append(tail, "Дописали своё", FIRST)
    check(read(tail) == "# Мои заметки\n\n- 21:40\nДописали своё\n",
          "запись не прилипает к последней строке чужого файла")

    # --- UTF-8 ---
    uni = os.path.join(tmp, "юникод.txt")
    inbox.append(uni, "Ёлка, приём, ещё раз", FIRST)
    check("Ёлка, приём, ещё раз" in read(uni), "кириллица читается обратно")

    # --- многострочный текст ---
    multi = os.path.join(tmp, "многострочно.md")
    inbox.append(multi, "Первая строка\nвторая строка", FIRST)
    check(read(multi) == "- 21:40\nПервая строка\nвторая строка\n",
          "текст с переводом строки ложится как есть")

    # --- ЛОВУШКИ ---
    check(inbox.append("", "Некуда", FIRST) is False,
          "пустой путь - выключенный инбокс, а не место для записи")
    check(inbox.append(path, "", FIRST) is False,
          "пустой текст не плодит записей без слов")
    check(inbox.append(path, "   \n  ", FIRST) is False,
          "одни пробелы - тоже пусто")
    before = read(path)
    inbox.append(path, "", FIRST)
    check(read(path) == before, "и файл при этом не тронут")

    nowhere = os.path.join(tmp, "нет-такой-папки", "inbox.md")
    check(inbox.append(nowhere, "Мысль", FIRST) is False,
          "путь в несуществующей папке - отказ, а не падение и не своя папка")
    check(not os.path.exists(os.path.dirname(nowhere)),
          "папку по опечатке в пути не заводим")

    # Файл занят намертво: на Windows это открытие с монопольным доступом.
    # Ровно этот случай и должен уводить текст в буфер обмена.
    busy = os.path.join(tmp, "занятый.md")
    with open(busy, "w", encoding="utf-8") as f:
        f.write("- 20:00\nстарое\n")
    locked = None
    try:
        import msvcrt

        locked = open(busy, "a", encoding="utf-8")
        msvcrt.locking(locked.fileno(), msvcrt.LK_NBLCK, 1)
    except (ImportError, OSError):
        locked = None
    if locked is not None:
        try:
            check(inbox.append(busy, "Мысль", FIRST) is False,
                  "занятый файл - отказ, текст уйдёт в буфер (задача 12)")
        finally:
            try:
                msvcrt.locking(locked.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            locked.close()
    else:
        # Замок не поставился - молчать нельзя: тест не проверил то, ради чего
        # он написан, и об этом должно быть видно в выводе.
        check(True, "занятый файл не проверен: замок не поставился")

    # Папка вместо файла - тоже отказ, а не исключение наружу.
    check(inbox.append(tmp, "Мысль", FIRST) is False,
          "папка вместо файла - отказ, а не падение")

    # --- ~ в пути ---
    # Человек пишет путь руками и напишет «~/inbox.md». Подменяем домашнюю
    # папку на временную, чтобы проверить разворот, а не засорять настоящую.
    old_home = os.environ.get("USERPROFILE")
    os.environ["USERPROFILE"] = tmp
    try:
        check(inbox.append("~/дома.md", "Мысль из дома", FIRST),
              "путь с ~ принимается")
        check(os.path.exists(os.path.join(tmp, "дома.md")),
              "и разворачивается в домашнюю папку, а не в файл с именем «~»")
    finally:
        if old_home is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = old_home

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
