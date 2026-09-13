"""Обновления: спросить GitHub, есть ли версия свежее, и поставить её.

Почему свой чекер, а не готовый:

  - PyUpdater архивирован автором - брать нельзя;
  - tufup жив, но это TUF со своим хранилищем ключей и метаданными. Для
    приложения, которое ставится одним .exe из GitHub Releases, это стрельба
    из пушки: доверие у нас и так от GitHub с его TLS, а не от своей PKI.

Здесь ровно то, что нужно: GET /releases/latest, сравнить версии, скачать
setup.exe, запустить его и уйти с дороги. Пятьдесят строк вместо зависимости.

Чего здесь НЕТ намеренно - автоматической установки без спроса. Обновление
перезапускает приложение, а человек в этот момент может диктовать. Спрашиваем.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from version import GITHUB_REPO, __version__

_TIMEOUT = 6.0
_UA = {"User-Agent": f"FlowLocal/{__version__}"}


def _parse(v: str) -> tuple:
    """«v1.2.3» -> (1, 2, 3). Не semver целиком: нам хватает четырёх чисел.

    Всё, что не число, отбрасываем: тег «v0.2.0-beta» сравнится как 0.2.0.
    Для своих релизов этого достаточно, а разбирать пререлизы по спецификации
    ради одного пользователя - лишнее.

    **Четыре, а не три.** Четвёртое число - правка уже выпущенной версии
    (правило в CLAUDE.md: 0.3.1 поправили - выпускаем 0.3.1.1). Пока брали
    три, «0.3.1.1» и «0.3.1» разбирались в один и тот же (0, 3, 1), то есть
    обновлятор считал их одинаковыми и правку никому не предлагал. Молча:
    обновлений нет и ошибок нет - самый неприятный вид поломки.

    Разной длины кортежи сравниваются правильно сами: (0, 3, 1) < (0, 3, 1, 1),
    потому что короткий кортеж-префикс меньше длинного.

    **Берём только головную часть, до первого не-числа.** Раньше выгребались
    все числа подряд, и с переходом на четыре это сразу вышло боком: у
    «v0.2.0-beta.1» единица из имени пререлиза становилась четвёртым числом,
    то есть бета оказывалась НОВЕЕ своего же релиза. Поймано тестом, а не
    рассуждением.
    """
    m = re.match(r"v?(\d+(?:\.\d+)*)", (v or "").strip())
    if not m:
        return (0,)
    return tuple(int(n) for n in m.group(1).split(".")[:4])


def check() -> dict | None:
    """Свежая версия на GitHub или None.

    None - и когда обновлений нет, и когда спросить не вышло. Разницы для
    вызвавшего нет: в обоих случаях делать нечего. Молчим намеренно - сеть
    может не работать, репозиторий может быть приватным, GitHub может лежать,
    и ни один из этих случаев не повод беспокоить человека.
    """
    if not GITHUB_REPO:
        return None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers=_UA)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - нет сети, нет релизов, нет GitHub
        return None

    tag = str(data.get("tag_name") or "")
    if _parse(tag) <= _parse(__version__):
        return None

    # Ищем установщик. Папку-сборку не берём: её надо распаковывать руками,
    # а установщик знает, куда класть, и умеет обновить поверх.
    setup = next((a for a in data.get("assets", [])
                  if str(a.get("name", "")).lower().endswith("setup.exe")), None)
    if not setup:
        return None
    return {
        "version": tag.lstrip("v"),
        "url": setup["browser_download_url"],
        "size_mb": round((setup.get("size") or 0) / 1e6),
        "notes": str(data.get("body") or "").strip(),
        "page": str(data.get("html_url") or ""),
    }


def download(url: str, on_progress=None) -> str:
    """Скачать установщик во временную папку. Возвращает путь.

    Не рядом с приложением: мы, скорее всего, стоим в %LOCALAPPDATA%\\Programs,
    и класть туда мусор, который сами же не уберём, - плохая манера.
    """
    dst = os.path.join(tempfile.mkdtemp(prefix="flowlocal_update_"),
                       "FlowLocal-setup.exe")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dst, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done / total)
    return dst


def install(setup_path: str) -> None:
    """Запустить установщик и вернуть управление - нас он закроет сам.

    /SILENT, а не /VERYSILENT: человек должен видеть, что происходит, - окно
    само по себе отвечает на вопрос «оно ещё живо?». Вопросов при этом не
    задаёт, тот же AppId ставится поверх.

    CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS обязательны: иначе установщик -
    наш потомок, и когда мы выйдем (а выйти мы должны, чтобы освободить свой
    .exe), Windows может забрать его с собой.
    """
    subprocess.Popen(
        [setup_path, "/SILENT", "/NORESTART"],
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                       | getattr(subprocess, "DETACHED_PROCESS", 0)),
        close_fds=True,
    )


def can_update() -> bool:
    """Обновлять умеем только собранную сборку.

    Из исходников это делается git pull, и подсовывать разработчику установщик
    поверх его рабочей копии - последнее, что стоит делать.
    """
    return bool(getattr(sys, "frozen", False))
