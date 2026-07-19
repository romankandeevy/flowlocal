"""Список преобразований: что попадёт в окно выбора.

Ollama здесь не нужна - проверяем разбор конфига и сам список, а не работу
модели. Модель проверяется живьём, автотестом её ответ не поймать (это ровно
то, о чём предупреждает llm_command: у правки по указанию нет признака
правильности).

Ловушки важнее проверок: конфиг человек правит руками, и одна кривая строка не
должна лишать его всего списка - список открывается по хоткею посреди работы.

Запуск: python test_transforms.py
"""

import sys

import transforms as TF

ok = True


def check(cond: bool, text: str) -> None:
    global ok
    ok = ok and bool(cond)
    print(("  ок   " if cond else "ПРОВАЛ ") + text)


def main() -> int:
    # --- готовый список ---
    ids = [p["id"] for p in TF.PRESETS]
    check(len(ids) == len(set(ids)), "у готовых преобразований нет одинаковых id")
    check(all(p.get("title") and p.get("instruction") for p in TF.PRESETS),
          "у каждого готового есть название и указание")
    check(all(len(p["title"]) <= 20 for p in TF.PRESETS),
          "названия влезают в окно выбора (не длиннее 20 знаков)")
    check(all(len(p.get("hint", "")) <= 42 for p in TF.PRESETS),
          "подсказки не переносятся на вторую строку")
    check(TF.PRESETS[0]["id"] == "prompt",
          "первым идёт «Задание для ИИ» - самое частое нажимается не глядя")
    # Цифрой нажимаются первые девять - так устроен список выбора. Десятый и
    # дальше берутся стрелками или мышью, и это не поломка: окно показывает у
    # них «·» вместо номера. Но первые девять должны быть самыми ходовыми,
    # иначе частое преобразование окажется без быстрой клавиши.
    check(len(TF.PRESETS) <= 12,
          f"готовых {len(TF.PRESETS)} - список не превращается в стену")
    check([p["id"] for p in TF.PRESETS[:3]] == ["prompt", "shorter", "fix"],
          "первые три - самые частые: они нажимаются не глядя")
    check("en" not in [p["id"] for p in TF.PRESETS[:9]] or True,
          "перевод не обязан быть в первой девятке - он редкий")

    # --- пустой конфиг ---
    check(len(TF.all_for({})) == len(TF.PRESETS),
          "пустой конфиг даёт ровно готовый список")

    # --- свои ---
    cfg = {"transforms": [{"id": "mine", "title": "По-деловому",
                           "instruction": "перепиши строго"}]}
    got = TF.all_for(cfg)
    check(len(got) == len(TF.PRESETS) + 1, "своё добавилось к готовым")
    check(got[-1]["custom"] is True, "своё помечено как своё")

    # --- ЛОВУШКИ: кривой конфиг не должен ронять список ---
    bad = {"transforms": [
        {"title": "без указания"},                      # нет instruction
        {"instruction": "без названия"},                # нет title
        {"title": "  ", "instruction": "пробелы"},      # пустое название
        {"title": "норм", "instruction": "   "},        # пустое указание
        "вообще не словарь",                            # не dict
        None,
        {"title": "живое", "instruction": "работай"},    # единственное годное
    ]}
    got = TF.all_for(bad)
    customs = [t for t in got if t.get("custom")]
    check(len(customs) == 1 and customs[0]["title"] == "живое",
          "из семи кривых записей выжила ровно одна годная")

    check(TF.all_for({"transforms": "строка вместо списка"}) == TF.all_for({}),
          "строка вместо списка не ломает список")
    check(TF.all_for({"transforms": None}) == TF.all_for({}),
          "None вместо списка не ломает список")

    # --- ЛОВУШКА: без id он всё равно должен быть уникальным ---
    got = TF.all_for({"transforms": [
        {"title": "первое", "instruction": "раз"},
        {"title": "второе", "instruction": "два"}]})
    cids = [t["id"] for t in got]
    check(len(cids) == len(set(cids)),
          "своим без id раздаются разные id, иначе выбор брал бы не то")

    # --- предел ---
    many = {"transforms": [{"title": f"т{i}", "instruction": "и"}
                           for i in range(50)]}
    check(len([t for t in TF.all_for(many) if t.get("custom")]) == TF.MAX_CUSTOM,
          f"своих не больше {TF.MAX_CUSTOM} - остальные не влезли бы в окно")

    # --- спрятать готовое ---
    cfg = {"transforms_hidden": ["en", "email"]}
    got = [t["id"] for t in TF.all_for(cfg)]
    check("en" not in got and "email" not in got, "спрятанные не показываются")
    check("prompt" in got, "остальные готовые на месте")

    # --- поиск ---
    check(TF.find({}, "shorter")["title"] == "Короче", "поиск по id находит")
    check(TF.find({}, "нет такого") is None, "неизвестный id даёт None, а не падение")
    check(TF.find({"transforms_hidden": ["en"]}, "en") is None,
          "спрятанное не найти - иначе хоткей применял бы то, чего нет в списке")

    # --- длина полей ---
    long = {"transforms": [{"title": "т" * 200, "hint": "п" * 200,
                            "instruction": "и"}]}
    t = [x for x in TF.all_for(long) if x.get("custom")][0]
    check(len(t["title"]) <= 40 and len(t["hint"]) <= 60,
          "слишком длинные название и подсказка обрезаются, а не ломают окно")

    print("\nИТОГ:", "всё сходится" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
