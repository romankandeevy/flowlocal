"""Окно настроек на Qt/QML - этап 7 плана. Замена settings.py (tkinter+PIL).

Здесь только данные и действия; вся вёрстка - в qml/Settings.qml. Это и есть
смысл переезда: раньше «карточка со скруглением 12px» была недостижима, потому
что tkinter рисует рамку исключительно прямоугольником, и приходилось лепить
фон в PIL суперсэмплом x3. Теперь это `radius: 12`, а известное расхождение с
Korti (HANDOFF, раздел 4) закрыто само собой.

Сохранение - сразу по изменению, кнопки «Применить» нет намеренно: лишний шаг,
о котором легко забыть. Частые правки (перетаскивание ползунка) склеиваются в
одну запись таймером.

Захват хоткея остаётся на библиотеках keyboard/mouse, а не на событиях Qt:
приложение вешает хоткей через них же, и имена клавиш обязаны совпадать - иначе
поле и хук поймут «ctrl» по-разному (такой баг уже был). Плюс Qt отдаёт события
только когда окно в фокусе, а боковые кнопки мыши не отдаёт вовсе.
"""

import os
import shutil
import subprocess
import sys
import threading
import time

from PySide6.QtCore import (Property, QEvent, QObject, QSize, QTimer, QUrl,
                            Signal, Slot)
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

import app_paths
import config as C


def _log(msg: str) -> None:
    """Подробность - в журнал, человеку - фразу без питоновских потрохов.

    Текст исключения раньше уходил прямо в подпись окна: человек видел
    «не удалось сохранить: [Errno 13] Permission denied». Это ровно
    тот случай, ради которого в правилах написано «служебное живёт в flow.log,
    и кнопка рядом» - кнопка «Журнал работы» тут же, на странице «О программе».

    Импорт внутри функции, а не сверху: app импортирует settings_qt, и сверху
    получилось бы кольцо. К моменту вызова app давно загружен.
    """
    try:
        from app import log
        log(msg)
    except Exception:  # noqa: BLE001 - молчащий журнал не должен ронять окно
        pass


import inputspec
import models
import stats
import theme as T
from theme_qt import Tokens
from util import plural

# Канон Korti (templates/app-shell) свёрстан под 1280x820; нам хватает
# скромнее, но 900 узко: ряд из трёх метрик на главной становился тесным.
W, H = 1060, 700
MIN_W, MIN_H = 940, 620


def _dur(sec: float) -> str:
    """Секунды по-человечески. «4361 с» не читается, а статистика - про то,
    чтобы с одного взгляда понять, много это или мало."""
    sec = max(0, round(sec))
    if sec < 60:
        return f"{sec} с"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} мин"
    h, m = divmod(m, 60)
    return f"{h} ч {m:02d} мин"


def _opts(pairs) -> list:
    """[(подпись, значение)] -> [{label, value}] для QML."""
    return [{"label": lbl, "value": val} for lbl, val in pairs]


def _download_cmd(model_id: str) -> list:
    """Чем звать загрузчик модели: собранный .exe или свой же исходник.

    В сборке python рядом не лежит - зовём сам .exe со служебным флагом
    (app.download_model_cli). Из исходников зовём тот же интерпретатор, что
    выполняет нас: `sys.executable` в этом случае и есть python.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--download-model", model_id]
    return [sys.executable, os.path.join(app_paths.APP_DIR, "app.py"),
            "--download-model", model_id]


class Backend(QObject):
    """Мост между QML и конфигом. Всё, что QML умеет, - здесь."""

    changed = Signal()               # конфиг перечитан целиком
    flashed = Signal(str, str)       # текст, цвет ("", "danger", "accent")
    captureDone = Signal(str, str)   # поле, спецификация
    # Установка Ollama прямо из настроек: этап словами, доля, общий размер.
    llmStage = Signal(str, float, float)
    llmDone = Signal(bool)
    # Приватный: им колбэк из потока keyboard перебрасывает результат в главный
    # поток. Прямо из чужого потока трогать нельзя ничего - ни QTimer.start()
    # в set(), ни QML. Сигнал с авто-соединением кладётся в очередь получателя,
    # и это ровно то же, чем в tkinter-версии был after(0, ...).
    _captured = Signal(str)

    def __init__(self, on_change, on_hotkey_capture, info_fn,
                 history_path: str, log_path: str, on_onboarding=None,
                 update_fn=None, do_update=None,
                 llm_install=None, llm_busy=None, redo_fn=None,
                 notes_fn=None) -> None:
        super().__init__()
        self._on_change = on_change
        self._on_hotkey_capture = on_hotkey_capture
        self._info_fn = info_fn
        self._on_onboarding = on_onboarding
        self._update_fn = update_fn
        self._do_update = do_update
        self._llm_install = llm_install
        self._llm_busy_fn = llm_busy
        self._redo_fn = redo_fn      # распознать сохранённую запись заново
        self._punct_busy = False     # идёт ли скачивание модели знаков
        self._notes_fn = notes_fn    # открыть окно заметок
        self.history_path = history_path
        self.log_path = log_path
        self.cfg = C.load()

        self._save = QTimer()
        self._save.setSingleShot(True)
        self._save.timeout.connect(self._flush)

        self._cap_field = ""
        self._hook = None
        self._mouse_hook = None
        self._mods: list[str] = []
        self._downloading: set[str] = set()
        self._captured.connect(self._finish)

    # ---------- конфиг ----------

    def reload(self) -> None:
        """Свежий конфиг с диска. Каждое открытие окна: иначе правка
        config.json руками осталась бы не видна, а первое же изменение в окне
        записало бы поверх неё старые значения."""
        self.cfg = C.load()
        self.changed.emit()

    @Slot(str, result="QVariant")
    def get(self, path: str):
        return C.get(self.cfg, path)

    @Slot(str, "QVariant")
    def set(self, path: str, value) -> None:
        C.set_(self.cfg, path, value)
        self.flashed.emit("сохранено", "")
        self._save.start(350)        # склеиваем частые правки в одну запись

    @Slot(str, "QVariant")
    def setRestart(self, path: str, value) -> None:
        self.set(path, value)
        self.flashed.emit("применится после перезапуска FlowLocal", "accent")

    @Slot(str)
    def setModel(self, model_id: str) -> None:
        """Модель едет вместе со своей квантизацией: у каждой в каталоге своя.
        Без этого выбор Whisper поверх int8-настройки GigaAM отправил бы
        загрузчик искать несуществующий файл.

        Применяется без перезапуска: app.py увидит смену ключа и перегрузит
        модель в фоне, старая работает до готовности новой (PLAN 2.4)."""
        m = models.get(model_id)
        C.set_(self.cfg, "quantization", models.quant_for(model_id))
        self.set("model", model_id)
        # Строка «используется» стоит рядом, на той же карточке, и обязана
        # переехать вместе с выбором - иначе она врёт до закрытия окна.
        self.modelsChanged.emit()
        size = f"{m.size_mb} МБ, {m.langs}. " if m else ""
        self.flashed.emit(f"{size}Загружается в фоне, перезапуск не нужен", "accent")

    def _flush(self) -> None:
        try:
            C.save(self.cfg)
        except OSError as e:
            _log(f"настройки не сохранились: {e}")
            self.flashed.emit("не удалось сохранить - смотрите журнал работы", "danger")
            return
        self._on_change(dict(self.cfg))

    # ---------- списки для QML ----------

    @Slot(bool)
    def setTechTerms(self, on: bool) -> None:
        """Включить или выключить технические термины.

        Термины кладём в те же подстановки, что и свои: механика одна, и
        человек видит их в «Словах» - может поправить или удалить поштучно.
        Выключение снимает только наши записи, свои не трогает.
        """
        import techdict

        snips = self.cfg.get("snippets") or {}
        snips = techdict.merge_into(snips) if on else techdict.strip_from(snips)
        C.set_(self.cfg, "snippets", snips)
        C.set_(self.cfg, "tech_terms", bool(on))
        self._flush()
        self.changed.emit()
        n = len(techdict.TERMS)
        self.flashed.emit(f"{n} технических терминов "
                          + ("добавлено" if on else "убрано"), "accent")

    @Slot()
    def openNotes(self) -> None:
        """Открыть окно заметок из панели."""
        if self._notes_fn is not None:
            self._notes_fn()

    @Slot(str, str)
    def addToDictionary(self, heard: str, correct: str) -> None:
        """Добавить пару «услышано - правильно» в словарь одним нажатием.

        Смысл в том, чтобы не заставлять человека открывать «Слова» и
        вспоминать, как пишется слово, которое программа путает. Мы это уже
        знаем: слово и его исправление лежат в истории.
        """
        if not heard or not correct:
            return
        words = list(self.cfg.get("dictionary") or [])
        if correct in words:
            self.flashed.emit(f"«{correct}» уже в словаре", "")
            return
        words.append(correct)
        C.set_(self.cfg, "dictionary", words)
        self._flush()
        self.changed.emit()
        self.flashed.emit(f"«{correct}» добавлено в словарь", "accent")

    @Slot(result="QVariantMap")
    def insights(self) -> dict:
        """Разбор своей речи. Считается здесь же, по накопленной истории."""
        import insights
        import stats

        try:
            rows = stats.load(self.history_path)
        except OSError:
            rows = []
        d = insights.summary(rows)
        # Часы приводим к виду, который читает человек, а не к числу.
        h = d.get("hour", -1)
        d["hourText"] = f"{h}:00-{h + 1}:00" if h >= 0 else ""
        return d

    @Slot(result="QVariantList")
    def savedRecordings(self) -> list:
        """Записи, которые не удалось распознать. Свежие первыми."""
        import recordings

        out = []
        for r in recordings.kept():
            mins = int(r["sec"] // 60)
            how = (f"{mins} мин {int(r['sec'] % 60)} с" if mins
                   else f"{int(r['sec'])} с")
            out.append({"path": r["path"], "name": r["name"],
                        "note": f"{how} · {r['mb']:.0f} МБ"})
        return out

    @Slot(str)
    def redoRecording(self, path: str) -> None:
        """Распознать сохранённую запись заново.

        Текст кладём в буфер обмена, а не вставляем: окно программы сейчас в
        фокусе, и вставлять было бы некуда. Куда его деть, решает человек.
        """
        if self._redo_fn is None:
            self.flashed.emit("распознавание недоступно", "danger")
            return
        self.flashed.emit("распознаю - на длинной записи это займёт минуту", "")
        self._redo_fn(path)

    @Slot(str)
    def dropRecording(self, path: str) -> None:
        import recordings

        recordings.drop(path)
        self.changed.emit()
        self.flashed.emit("запись удалена", "")

    @Slot(result=bool)
    def punctModelReady(self) -> bool:
        import punct_model

        return punct_model.installed()

    @Slot(result=str)
    def punctModelNote(self) -> str:
        import punct_model

        if punct_model.installed():
            return f"скачана, {punct_model.size_mb():.0f} МБ"
        return "не скачана, нужно 30 МБ"

    @Slot()
    def punctModelInstall(self) -> None:
        """Скачать модель знаков. Своим потоком - тридцать мегабайт это минуты."""
        import threading

        import punct_model

        if self._punct_busy:
            return
        self._punct_busy = True
        self.flashed.emit("качаю модель знаков препинания…", "")

        def work() -> None:
            err = punct_model.download()
            self._punct_busy = False
            if err:
                _log(f"модель знаков не скачалась: {err}")
                self.flashed.emit("не скачалось - смотрите журнал работы", "danger")
            else:
                self.set("punctuation", "model")
                self.flashed.emit("модель знаков готова", "accent")
            self.changed.emit()

        threading.Thread(target=work, daemon=True).start()

    @Slot(result=bool)
    def punctBusy(self) -> bool:
        return self._punct_busy

    @Property("QVariantList", constant=True)
    def modelOptions(self) -> list:
        return _opts([(m.title, m.id) for m in models.CATALOG])

    # Выбора языка распознавания здесь нет намеренно, и это не пропущенная
    # настройка. В каталоге остались две модели, обе русские (models.py), и
    # ключ `language` читает только загрузчик многоязычных - для тех, кто
    # вернёт Whisper обратно. Показывать переключатель, который сейчас ни на
    # что не влияет, хуже, чем не показывать ничего.

    @Property("QVariantList", constant=True)
    def deviceOptions(self) -> list:
        return _opts([("авто", "auto"), ("видеокарта", "cuda"), ("процессор", "cpu")])

    @Property("QVariantList", constant=True)
    def themeOptions(self) -> list:
        return _opts([("система", "system"), ("светлая", "light"), ("тёмная", "dark")])

    @Property("QVariantList", constant=True)
    def insertOptions(self) -> list:
        """«Посимвольно» человеку ничего не говорит - это слово из кода.

        Владелец назвал формулировку непонятной, и справедливо: выбор здесь не
        между двумя способами набора, а между «мгновенно» и «медленно, зато
        доходит везде». Так и подписываем - по результату, а не по механике.
        """
        return _opts([("сразу целиком", "paste"), ("по одной букве", "type")])

    @Property("QVariantList", constant=True)
    def pillOptions(self) -> list:
        return _opts([("снизу", "bottom"), ("сверху", "top"), ("скрыть", "off")])

    @Property("QVariantList", notify=changed)
    def micOptions(self) -> list:
        """Один физический микрофон PortAudio показывает по разу на каждый
        host-api, поэтому имя без api - это три одинаковые строки и гадание."""
        import i18n
        from recorder import default_input_name, list_input_devices

        # Имя микрофона внутри строки - от системы, его не перевести. Переводим
        # только своё слово перед ним, иначе L.t в QML не найдёт ключ: там
        # строка целиком, вместе с «Микрофон (Realtek High Definition)».
        out = [{"label": f"{i18n.t('по умолчанию')} · {default_input_name()}",
                "value": None}]
        for i, name, api in list_input_devices():
            out.append({"label": f"{name} · {api}", "value": i})
        return out

    # ---------- строки-подсказки ----------

    @Slot(str, result=str)
    def pretty(self, spec: str) -> str:
        return inputspec.pretty(spec or "")

    @Property(str, notify=changed)
    def userName(self) -> str:
        """Как обращаться к человеку на «Главной».

        Берём имя учётной записи Windows: спрашивать его отдельным экраном
        мастера ради одной строки приветствия - плохая сделка, а имя у системы
        уже есть. Ключ `name` в конфиге перебивает его для тех, у кого учётка
        называется «user» или «Admin».

        Возвращаем пустоту, если имя не похоже на имя: «Administrator»,
        «user», «пользователь» - это не обращение, а строка из системы, и
        поздороваться с ней хуже, чем не здороваться вовсе. По той же причине
        не берём слишком длинные и составные: «DESKTOP-4F2K1\\roman» - не имя.
        """
        import os

        name = str(self.cfg.get("name") or "").strip()
        if not name:
            name = str(os.environ.get("USERNAME") or "").strip()
        if not name or len(name) > 20 or not name.replace("-", "").isalpha():
            return ""
        if name.lower() in ("user", "admin", "administrator", "администратор",
                            "пользователь", "owner", "default"):
            return ""
        return name

    @Property(bool, constant=True)
    def ready(self) -> bool:
        """Готово ли приложение записывать - для точки на главной.

        Спрашиваем то же, что и «О программе»: своего состояния у окна нет и
        быть не должно, иначе оно разойдётся с настоящим. Модель грузится
        секунды, а окно живёт минуты - к моменту его открытия ответ уже
        окончательный, поэтому constant, без сигнала.
        """
        try:
            return not str((self._info_fn() or {}).get("состояние", "")).startswith(
                "загрузка")
        except Exception:  # noqa: BLE001 - главная не должна падать из-за точки
            return False

    @Property(str, notify=changed)
    def toneNote(self) -> str:
        """Тон целиком зависит от Ollama - если полировка выключена, правила
        лежат мёртвым грузом. Честнее сказать это прямо здесь, чем оставить
        человека гадать, почему ничего не меняется."""
        base = ("В почте пишем строго, в чате свободно - а говорите вы одинаково. "
                "Слева программа (outlook.exe), справа как писать: «формально», "
                "«дружелюбно», «коротко». Текст станет появляться чуть медленнее.")
        return base + ("  Работает." if C.get(self.cfg, "llm.enabled") else
                       "  Сейчас не работает: включите «Понимать поправки на ходу» "
                       "на странице «Диктовка».")

    # ---------- словарь и таблицы ----------

    @Property(str, notify=changed)
    def dictionaryText(self) -> str:
        return "\n".join(C.get(self.cfg, "dictionary", []) or [])

    @Slot(str)
    def setDictionary(self, text: str) -> None:
        words = [w.strip() for w in text.splitlines()]
        self.set("dictionary", [w for w in words if w])

    @Slot(str, result="QVariantList")
    def pairs(self, key: str) -> list:
        d = C.get(self.cfg, key, {}) or {}
        return [{"k": str(k), "v": str(v)} for k, v in d.items()]

    @Slot(str, "QVariantList")
    def setPairs(self, key: str, rows) -> None:
        """Значение собирается из полей ЗАНОВО, а не правится по ключу: ключ
        редактируют прямо на месте, и «переименование» иначе превращалось бы в
        удалить-плюс-добавить с потерей значения на полпути."""
        out = {}
        for r in rows:
            k = str(r["k"]).strip()
            if k:
                out[k] = str(r["v"])
        self.set(key, out)

    # ---------- программы, которым слать Enter ----------
    #
    # Раньше здесь было поле, куда вписывали `telegram.exe` через запятую.
    # Владелец спросил: откуда человеку взять это имя? Ниоткуда - он его не
    # знает и не обязан. Теперь имена берутся из запущенных программ, а
    # человек выбирает из того, что видит на экране.

    @Slot(result="QVariantList")
    def runningApps(self) -> list:
        """Запущенные программы для выбора. Уже выбранные не показываем."""
        import layered

        chosen = {str(a).lower() for a in (self.cfg.get("auto_enter_apps") or [])}
        try:
            apps = layered.visible_apps()
        except Exception as e:  # noqa: BLE001 - список не стоит окна настроек
            _log(f"список запущенных программ не собрался: {e}")
            return []
        return [{"label": f"{name} · {exe}" if name else exe, "value": exe}
                for name, exe in apps if exe not in chosen]

    @Property("QVariantList", notify=changed)
    def autoEnterApps(self) -> list:
        """Выбранные программы с человеческим именем, если его удалось узнать.

        Имя ищем среди запущенных: программа могла быть выбрана вчера и сейчас
        не работать - тогда покажем просто exe. Врать про то, чего нет на
        экране, не будем.
        """
        import layered

        try:
            names = {exe: name for name, exe in layered.visible_apps()}
        except Exception:  # noqa: BLE001
            names = {}
        out = []
        for exe in (self.cfg.get("auto_enter_apps") or []):
            exe = str(exe)
            out.append({"exe": exe, "label": names.get(exe.lower()) or exe})
        return out

    @Slot(str)
    def addAutoEnterApp(self, exe: str) -> None:
        exe = str(exe or "").strip().lower()
        if not exe:
            return
        apps = [str(a) for a in (self.cfg.get("auto_enter_apps") or [])]
        if exe in apps:
            return
        apps.append(exe)
        self.set("auto_enter_apps", apps)
        self.changed.emit()

    @Slot(str)
    def removeAutoEnterApp(self, exe: str) -> None:
        apps = [str(a) for a in (self.cfg.get("auto_enter_apps") or [])
                if str(a) != str(exe)]
        self.set("auto_enter_apps", apps)
        self.changed.emit()

    # ---------- преобразования ----------
    #
    # До этого свои преобразования правились только руками в config.json, а
    # спрятать готовое было нельзя вовсе. Список открывается по хоткею посреди
    # работы - значит и собирать его надо в окне, а не в текстовом редакторе.

    @Slot(result="QVariantList")
    def transformPresets(self) -> list:
        """Готовые преобразования и то, показываем ли каждое.

        Спрятать - не то же, что удалить: список задан кодом, удалять из него
        нечего. Но тот, кто никогда не переводит на английский, не обязан
        видеть этот пункт вечно.
        """
        import transforms

        hidden = set(self.cfg.get("transforms_hidden") or [])
        return [{"id": p["id"], "title": p["title"], "hint": p["hint"],
                 "shown": p["id"] not in hidden} for p in transforms.PRESETS]

    @Slot(str, bool)
    def setTransformShown(self, tid: str, shown: bool) -> None:
        hidden = [i for i in (self.cfg.get("transforms_hidden") or []) if i != tid]
        if not shown:
            hidden.append(tid)
        self.set("transforms_hidden", hidden)

    @Slot(result="QVariantList")
    def customTransforms(self) -> list:
        import transforms

        return [{"title": t["title"], "instruction": t["instruction"]}
                for t in transforms.custom_of(self.cfg)]

    @Slot("QVariantList")
    def setCustomTransforms(self, rows) -> None:
        import transforms

        self.set("transforms", transforms.pack_custom(
            [dict(r) for r in (rows or [])]))

    @Property(int, constant=True)
    def maxTransforms(self) -> int:
        import transforms

        return transforms.MAX_CUSTOM

    # ---------- история ----------

    @Slot(result="QVariantMap")
    def historyData(self) -> dict:
        """Записи и подпись под ними одним заходом: подпись считается из тех же
        строк, и читать history.jsonl дважды за одно открытие «Истории» незачем
        (та же экономия, что у homeData)."""
        rows = self._rows(stats.load(self.history_path))
        return {"rows": rows, "note": self._note(rows)}

    @Slot(result="QVariantList")
    def history(self) -> list:
        """Последние 400 диктовок, свежие сверху. Чтение и терпимость к битым
        строкам - в stats.load(): свой парсер тут был бы вторым мнением о том,
        что считать целой строкой, и однажды разошёлся бы со статистикой."""
        return self._rows(stats.load(self.history_path))

    @staticmethod
    def _rows(rows: list[dict]) -> list:
        return [{"ts": str(r.get("ts", "")), "sec": r.get("sec", 0),
                 "text": str(r.get("text", ""))} for r in reversed(rows[-400:])]

    @staticmethod
    def _note(rows: list) -> str:
        if not rows:
            return "Пока пусто. Продиктуйте что-нибудь."
        total = sum(len(r["text"].split()) for r in rows)
        n = len(rows)
        return (f"{n} {plural(n, 'диктовка', 'диктовки', 'диктовок')} · "
                f"примерно {total} {plural(total, 'слово', 'слова', 'слов')}")

    @Slot(str)
    def copyText(self, text: str) -> None:
        """Клик по записи истории кладёт её в буфер - чтобы «переиспользовать
        вчерашнюю диктовку» не требовало выделять текст мышью."""
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(text)
        self.flashed.emit("скопировано", "")

    @Slot()
    def clearHistory(self) -> None:
        try:
            open(self.history_path, "w", encoding="utf-8").close()
        except OSError as e:
            _log(f"история не очистилась: {e}")
            self.flashed.emit("не удалось очистить - смотрите журнал работы", "danger")
            return
        self.flashed.emit("история очищена", "")

    # ---------- статистика ----------

    @Slot(result="QVariantMap")
    def homeData(self) -> dict:
        """Всё для «Главной» одним заходом: числа плюс пять последних диктовок.
        Раньше страница звала stats() и history() подряд, и history.jsonl
        читался с диска дважды на каждое открытие окна."""
        rows = stats.load(self.history_path)
        return {"stats": self._stats(rows), "recent": self._rows(rows)[:5]}

    @Slot(result="QVariantMap")
    def stats(self) -> dict:
        return self._stats(stats.load(self.history_path))

    def _stats(self, rows: list[dict]) -> dict:
        s = stats.summary(rows)
        days = stats.by_day(rows, 30)
        top = max((v for _d, v in days), default=0)

        # Личный множитель «во сколько раз речь быстрее печати» - замер по
        # истории, а не лозунг из рекламы. На паре коротких фраз число ещё
        # случайное, поэтому до минуты записи честнее промолчать: прочерк
        # вместо цифры, взятой с потолка.
        enough = s["seconds"] >= 60 and s["words"] >= 50
        ratio = s["speech_wpm"] / stats.TYPING_WPM
        streak = s["streak_days"]

        return {
            # Признак «есть что показывать» считаем здесь, а не разбираем в QML
            # уже отформатированные строки: там «0» - непустая строка, и любая
            # проверка на месте выходит враньём.
            "hasData": s["dictations"] > 0,
            "dictations": f"{s['dictations']}",
            "words": f"{s['words']}",
            "seconds": _dur(s["seconds"]),
            "saved_sec": _dur(s["saved_sec"]),
            "speedOk": enough,
            "speed": ("в " + f"{ratio:.1f}".replace(".", ",") + " раза")
                     if enough else "-",
            "userWpm": round(s["speech_wpm"]),
            "streak": f"{streak} {plural(streak, 'день', 'дня', 'дней')}",
            "values": [v for _d, v in days],
            "range": (f"{days[0][0]} - {days[-1][0]}   ·   пик {top} "
                      f"{plural(top, 'слово', 'слова', 'слов')} в день") if days
                     else "",
            "typingWpm": stats.TYPING_WPM,
        }

    # ---------- экран «Модели» (PLAN 2.4) ----------

    modelsChanged = Signal()
    modelProgress = Signal(str, float)     # id, 0..1

    @Slot(result="QVariantList")
    def modelsInfo(self) -> list:
        from transcriber import model_dir

        active = str(self.cfg.get("model") or "")
        out = []
        for m in models.CATALOG:
            d = model_dir(m.id, m.quant)
            try:
                on_disk = sum(os.path.getsize(os.path.join(d, f))
                              for f in os.listdir(d)) / 1e6 if os.path.isdir(d) else 0.0
            except OSError:
                on_disk = 0.0
            out.append({
                "id": m.id, "title": m.title, "sizeMb": m.size_mb,
                "langs": m.langs, "device": m.device, "license": m.license,
                "why": m.why,
                # «скачана» - когда на диске почти весь заявленный объём:
                # оборванная скачка не должна выглядеть готовой моделью
                "installed": on_disk >= m.size_mb * 0.9,
                "onDiskMb": round(on_disk),
                "active": m.id == active,
                "downloading": m.id in self._downloading,
            })
        return out

    @Slot(str)
    def downloadModel(self, model_id: str) -> None:
        """Скачать модель заранее, не выбирая её. Прогресс - по росту папки:
        huggingface_hub наружу процентов не отдаёт, а размер честный, потому
        что в каталоге он сверен с метаданными репозитория (models.py)."""
        from transcriber import model_dir

        m = models.get(model_id)
        if m is None or model_id in self._downloading:
            return
        self._downloading.add(model_id)
        self.modelsChanged.emit()
        d = model_dir(m.id, m.quant)

        def poll() -> None:
            while model_id in self._downloading:
                try:
                    size = sum(os.path.getsize(os.path.join(d, f))
                               for f in os.listdir(d)) / 1e6 if os.path.isdir(d) else 0.0
                except OSError:
                    size = 0.0
                self.modelProgress.emit(model_id, min(0.99, size / m.size_mb))
                time.sleep(0.4)

        def work() -> None:
            # ОТДЕЛЬНЫМ ПРОЦЕССОМ, а не потоком. Потоком было так: скачивание
            # идёт по сети (GIL свободен), а следом onnxruntime собирает сессию
            # в C и держит GIL секундами - и всё это время окно не отвечает.
            # Владелец на мастере первого запуска увидел ровно это: «после
            # появления полоски всё зависло». GIL один на процесс, поэтому
            # лечится только вторым процессом.
            try:
                r = subprocess.run(_download_cmd(model_id),
                                   capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   creationflags=getattr(subprocess,
                                                         "CREATE_NO_WINDOW", 0))
                if r.returncode == 0:
                    self.modelProgress.emit(model_id, 1.0)
                    self.flashed.emit(f"{m.title} скачана", "")
                else:
                    _log("модель не скачалась: "
                         + (r.stderr or r.stdout or "").strip()[:300])
                    self.flashed.emit("не удалось скачать - проверьте интернет",
                                      "danger")
            except Exception as e:  # noqa: BLE001
                _log(f"загрузчик модели не запустился: {e}")
                self.flashed.emit("не удалось скачать - смотрите журнал работы",
                                  "danger")
            finally:
                self._downloading.discard(model_id)
                self.modelsChanged.emit()

        threading.Thread(target=poll, daemon=True).start()
        threading.Thread(target=work, daemon=True).start()

    @Slot(str)
    def deleteModel(self, model_id: str) -> None:
        from transcriber import model_dir

        m = models.get(model_id)
        if m is None:
            return
        if model_id == self.cfg.get("model"):
            self.flashed.emit("эта модель сейчас используется - сначала выберите другую",
                              "danger")
            return
        d = model_dir(m.id, m.quant)
        freed = 0.0
        try:
            if os.path.isdir(d):
                freed = sum(os.path.getsize(os.path.join(d, f))
                            for f in os.listdir(d)) / 1e6
                shutil.rmtree(d)
        except OSError as e:
            _log(f"модель не удалилась: {e}")
            self.flashed.emit("не удалось удалить - смотрите журнал работы", "danger")
            return
        self.flashed.emit(f"удалена, освобождено {freed:.0f} МБ", "")
        self.modelsChanged.emit()

    # ---------- система ----------

    @Property(bool, notify=changed)
    def autostart(self) -> bool:
        return app_paths.autostart_enabled()

    @Slot(bool)
    def setAutostart(self, value: bool) -> None:
        try:
            app_paths.set_autostart(bool(value))
            self.flashed.emit("автозапуск включён" if value else "автозапуск выключен", "")
        except OSError as e:
            _log(f"автозапуск не переключился: {e}")
            self.flashed.emit("не вышло переключить автозапуск", "danger")

    @Slot(result=str)
    def about(self) -> str:
        return "\n".join(f"{k}: {v}" for k, v in (self._info_fn() or {}).items())

    @Slot(result="QVariantMap")
    def pendingUpdate(self) -> dict:
        """Найденное обновление или пустой словарь.

        Показываем на Главной, а не всплывающим окном. Всплыть поверх чужой
        работы с новостью «вышла версия» - это ровно то, за что программы
        ненавидят. Но и прятать в меню трея, как было, - значит не сказать
        вовсе: владелец обновление так и не увидел.
        """
        upd = (self._update_fn() if self._update_fn else None) or {}
        if not upd:
            return {}
        return {
            "version": str(upd.get("version") or ""),
            "size_mb": int(upd.get("size_mb") or 0),
            # Первая строка заметок - фраза о релизе целиком. Весь список тут
            # не нужен: подробности человек прочтёт в «Как обновлялось».
            "title": str(upd.get("notes") or "").splitlines()[0] if upd.get("notes") else "",
        }

    @Slot()
    def applyUpdate(self) -> None:
        """Поставить обновление. Приложение закроется - его закроет установщик."""
        if self._do_update is not None:
            self._do_update()

    @Slot()
    def restartOnboarding(self) -> None:
        """«Пройти знакомство заново» - мастер открывается из настроек (PLAN 4)."""
        if self._on_onboarding is not None:
            self._on_onboarding()

    @Slot()
    def openFolder(self) -> None:
        self._reveal(C.APP_DIR)

    @Slot()
    def openConfig(self) -> None:
        self._open(C.CONFIG_PATH)

    @Slot()
    def openLog(self) -> None:
        self._open(self.log_path)

    @staticmethod
    def _reveal(path: str) -> None:
        try:
            subprocess.Popen(["explorer", os.path.normpath(path)])
        except OSError:
            pass

    @staticmethod
    def _open(path: str) -> None:
        try:
            os.startfile(path)  # noqa: S606 - открыть свой же файл системой
        except OSError:
            pass

    # ---------- захват хоткея ----------

    @Slot(str)
    def startCapture(self, field: str) -> None:
        """Ловим и клавиши, и боковые кнопки мыши: «ctrl+mouse4» - законный
        бинд. Клавиши - библиотекой keyboard, а не событиями Qt: приложение
        вешает хоткей через неё же, и имена должны совпадать."""
        import keyboard
        from pynput import mouse as pmouse

        if self._cap_field:
            self.cancelCapture()
        self._cap_field = field
        self._mods = []
        self._on_hotkey_capture(True)          # приложение снимает свои хоткеи
        self._hook = keyboard.hook(self._key_event)
        # Кнопки мыши ловим и ГЛОТАЕМ: пока идёт захват, боковая кнопка не
        # должна уходить в приложение под окном (X1 там - «Назад»).
        self._mouse_hook = pmouse.Listener(win32_event_filter=self._mouse_event)
        self._mouse_hook.start()

    @Slot()
    def cancelCapture(self) -> None:
        """Прервать захват. Безопасно звать всегда - в том числе при закрытии
        окна: иначе хук остался бы висеть, а приложение - вообще без хоткея."""
        import keyboard

        if not self._cap_field:
            return
        # Снимаем ПОИМЁННО, не unhook_all: иначе снесутся и хоткеи приложения.
        try:
            if self._hook is not None:
                keyboard.unhook(self._hook)
        except (KeyError, ValueError):
            pass
        try:
            if self._mouse_hook is not None:
                self._mouse_hook.stop()
        except Exception:  # noqa: BLE001 - слушатель мог уже умереть
            pass
        self._hook = self._mouse_hook = None
        self._cap_field = ""
        self._on_hotkey_capture(False)         # приложение вешает хоткеи обратно

    def _finish(self, spec: str) -> None:
        """Уже в главном потоке: сюда попадают только через сигнал _captured.

        spec == "\\x00" - это Esc, то есть отмена без записи. Отдельный маркер,
        а не пустая строка: пустая строка - законное значение «бинд выключен».
        """
        field = self._cap_field
        self.cancelCapture()
        if not field:
            return
        if spec == "\x00":
            self.captureDone.emit(field, str(C.get(self.cfg, field) or ""))
            return
        self.set(field, spec)
        self.captureDone.emit(field, spec)

    # Колбэки ниже исполняются в потоке библиотеки keyboard/mouse. Из них
    # можно только считать своё состояние и эмитить сигнал - больше ничего.

    def _key_event(self, e) -> None:
        if not self._cap_field:
            return
        name = (e.name or "").lower()
        if e.event_type == "down":
            if name == "esc":
                self._captured.emit("\x00")        # \x00 = отмена, см. _finish
                return
            # Без модификаторов - значит именно «стереть», а не «Ctrl+Backspace».
            if name in ("backspace", "delete") and not self._mods:
                self._captured.emit("")
                return
            canon = inputspec.canon_modifier(name)
            if canon:
                if canon not in self._mods:
                    self._mods.append(canon)
                return
            self._captured.emit(inputspec.build(self._mods, key=name))
        elif e.event_type == "up":
            canon = inputspec.canon_modifier(name)
            if canon and self._mods:
                # Отпустили модификатор, ничего больше не нажав, - это
                # одноклавишный хоткей вида «right ctrl», законный случай.
                if len(self._mods) == 1 and self._mods[0] == canon:
                    self._captured.emit(name)
                else:
                    self._mods = [m for m in self._mods if m != canon]

    # Сообщения WH_MOUSE_LL. Левую и правую кнопки не ловим намеренно: ими
    # человек кликает по этому же окну, и захват сделал бы настройки
    # неуправляемыми.
    _WM_XDOWN, _WM_MDOWN = 0x020B, 0x0207

    def _mouse_event(self, msg, data) -> None:
        """Фильтр WH_MOUSE_LL. suppress_event() подавляет событие ИСКЛЮЧЕНИЕМ -
        поэтому решение принимаем в защищённом блоке, а глотаем за его
        пределами: свой except иначе съел бы подавление."""
        btn = None
        try:
            if not self._cap_field:
                return
            if msg == self._WM_XDOWN:
                btn = "x" if (data.mouseData >> 16) == 1 else "x2"
            elif msg == self._WM_MDOWN:
                btn = "middle"
            else:
                return
            self._captured.emit(inputspec.build(self._mods, mouse=btn))
        except Exception:  # noqa: BLE001 - падение в хуке роняет весь ввод
            return
        self._mouse_hook.suppress_event()      # бросает - и это норма


    @Slot(result="QVariantList")
    def changelog(self) -> list:
        """История версий для «О программе».

        Из файла рядом с приложением, а не из GitHub: страница, которая
        объясняет, что интернет нужен один раз, не имеет права показывать
        пустоту без сети.

        Текущую версию помечаем здесь, а не в QML: сравнение версий - работа
        для того, кто их и так знает.
        """
        import changelog as CL
        from version import __version__

        out = []
        for rel in CL.load():
            out.append({
                "version": rel["version"],
                "date": rel["date"],
                "title": rel["title"],
                "items": rel["items"],
                "current": rel["version"] == __version__,
            })
        return out

    # ---------- выгрузка и загрузка личного ----------

    @Slot(bool, result=str)
    def exportData(self, with_history: bool) -> str:
        """Сохранить словарь, замены и сочетания в файл. Возвращает отчёт.

        Диалог сохранения - системный: своё окно выбора файла человеку
        объяснять не надо, а системное он видел тысячу раз.
        """
        import backup
        from PySide6.QtWidgets import QFileDialog

        name = time.strftime("FlowLocal-%Y-%m-%d.json")
        path, _ = QFileDialog.getSaveFileName(
            None, "Куда сохранить", os.path.join(os.path.expanduser("~"), name),
            "Файл FlowLocal (*.json)")
        if not path:
            return ""
        history = None
        if with_history:
            import stats

            try:
                history = stats.load(self.history_path)
            except OSError:
                history = []
        try:
            n = backup.save(path, self.cfg, history)
        except OSError as e:
            _log(f"выгрузка не сохранилась: {e}")
            self.flashed.emit("не сохранилось - смотрите журнал работы", "danger")
            return ""
        what = f"{n} {plural(n, 'настройка', 'настройки', 'настроек')}"
        if history:
            what += (f" и {len(history)} "
                     f"{plural(len(history), 'диктовка', 'диктовки', 'диктовок')}")
        self.flashed.emit(f"сохранено: {what}", "accent")
        return path

    @Slot(result=str)
    def importData(self) -> str:
        """Загрузить из файла. Сливает, а не затирает - см. backup.merge."""
        import backup
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            None, "Откуда загрузить", os.path.expanduser("~"),
            "Файл FlowLocal (*.json)")
        if not path:
            return ""
        try:
            data = backup.load(path)
        except Exception as e:  # noqa: BLE001 - чужой файл не должен ронять окно
            _log(f"файл выгрузки не подошёл: {e}")
            self.flashed.emit("файл не подошёл - выберите другой", "danger")
            return ""
        added, replaced = backup.merge(self.cfg, data)
        self._flush()
        self.changed.emit()
        note = f"добавлено {added} {plural(added, 'запись', 'записи', 'записей')}"
        if replaced:
            note += f", заменено {len(replaced)}"
        self.flashed.emit(note if added or replaced else "всё это уже было", "accent")
        return path

    # ---------- подстановки, найденные по истории ----------

    @Slot(result="QVariantList")
    def suggestions(self) -> list:
        """Что программа заметила в истории и предлагает превратить в фразу.

        Считается на лету, а не хранится: история меняется каждый день, и
        держать рядом второй файл с находками - значит завести ещё одну правду,
        которая разъедется с первой.
        """
        import stats
        import suggest

        try:
            rows = stats.load(self.history_path)
        except OSError:
            return []
        found = suggest.find(rows, self.cfg.get("snippets") or {},
                             self.cfg.get("snippets_declined") or [])
        from util import plural

        # Согласование числительного считаем здесь, а не в QML: plural() живёт
        # в Python, и «3 раз» вместо «3 раза» - ровно та мелочь, по которой
        # видно, что текст писала программа, а не человек.
        return [{"value": c["value"], "count": int(c["count"]), "kind": c["kind"],
                 "times": f"{c['count']} {plural(c['count'], 'раз', 'раза', 'раз')}"}
                for c in found]

    @Slot(str)
    def declineSuggestion(self, value: str) -> None:
        """«Не надо». Запоминаем навсегда: предложить то же второй раз - значит
        не услышать ответ."""
        declined = list(self.cfg.get("snippets_declined") or [])
        if value and value not in declined:
            declined.append(value)
            self.set("snippets_declined", declined)
        self.changed.emit()

    @Property(int, notify=changed)
    def declinedCount(self) -> int:
        return len(self.cfg.get("snippets_declined") or [])

    @Slot()
    def clearDeclined(self) -> None:
        """Забыть отказы, чтобы находки предложились заново.

        «Не надо» запоминается навсегда - иначе программа спрашивала бы одно и
        то же каждую неделю. Но навсегда без пути назад означало бы, что один
        промах мыши стоит человеку находки, о которой он больше не узнает.
        """
        n = len(self.cfg.get("snippets_declined") or [])
        self.set("snippets_declined", [])
        self.changed.emit()
        self.flashed.emit(f"{n} {plural(n, 'находка', 'находки', 'находок')} "
                          "вернутся, если повторятся снова", "accent")

    @Slot(str, str)
    def acceptSuggestion(self, phrase: str, value: str) -> None:
        """Завести подстановку: сказал «фразу» - вставилось «значение»."""
        if not phrase.strip() or not value.strip():
            return
        snippets = dict(self.cfg.get("snippets") or {})
        snippets[phrase.strip()] = value
        self.set("snippets", snippets)
        self.flashed.emit(f"запомнил: «{phrase.strip()}»", "accent")

    # ---------- правка текста: ставим Ollama за человека ----------

    @Slot(result=bool)
    def llmReady(self) -> bool:
        """Всё ли уже готово: сервер отвечает и модель на месте."""
        import ollama_setup as O

        return O.serving() and O.has_model(O.DEFAULT_MODEL)

    @Slot()
    def llmInstall(self) -> None:
        """Попросить приложение поставить Ollama и слушать ход.

        Своего потока здесь больше нет намеренно. Раньше качали двое - это
        окно и мастер первого запуска, - и нажатие в обоих местах давало две
        качалки на одну машину. Плюс ход установки жил внутри окна: закрыл -
        и не знаешь, идёт ли что-нибудь, хотя три гигабайта качаются минутами.

        Теперь хозяин один (App.install_ollama), ход показывает пилюля поверх
        всех окон, а мы лишь подписываемся, чтобы нарисовать полосу у себя.
        """
        if self._llm_install is None:
            return
        self._llm_install(self._llm_stage)

    def _llm_stage(self, stage: str, frac: float, total: float, done) -> None:
        """Колбэк из потока установки. Сигнал сам перебросит в главный поток."""
        if done is None:
            self.llmStage.emit(stage, frac, float(total))
        else:
            self.llmDone.emit(bool(done))

    @Slot(result=bool)
    def llmBusy(self) -> bool:
        """Идёт ли установка прямо сейчас. Нужно окну, открытому посреди неё:
        без этого оно показало бы кнопку «Установить», как будто ничего не
        происходит, и человек нажал бы второй раз."""
        return bool(self._llm_busy_fn()) if self._llm_busy_fn else False



class _CloseFilter(QObject):
    """Ловит закрытие окна. Отдельным объектом, потому что сигнал closing в
    PySide неисправен: QQuickCloseEvent* не маршалится."""

    def __init__(self, on_close) -> None:
        super().__init__()
        self._on_close = on_close

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Close:
            self._on_close()
        return False          # событие не съедаем, окно должно закрыться


class SettingsWindow:
    """Окно. Открывается и закрывается, но не пересоздаётся: смена темы теперь
    не требует пересборки - QML перечитывает токены по сигналу.

    В tkinter-версии окно приходилось собирать заново на каждую смену темы:
    часть красок впечатывалась в виджеты при создании. У QML краски - привязки,
    и пересборка не нужна вовсе."""

    def __init__(self, on_change, on_hotkey_capture, info_fn,
                 history_path: str, log_path: str, on_onboarding=None,
                 update_fn=None, do_update=None,
                 llm_install=None, llm_busy=None, redo_fn=None,
                 notes_fn=None) -> None:
        self.backend = Backend(on_change, on_hotkey_capture, info_fn,
                               history_path, log_path, on_onboarding=on_onboarding,
                               update_fn=update_fn, do_update=do_update,
                               llm_install=llm_install, llm_busy=llm_busy,
                               redo_fn=redo_fn, notes_fn=notes_fn)
        self.tokens = Tokens()
        self.view: QQuickView | None = None
        self._filter = _CloseFilter(self.backend.cancelCapture)

    def _build(self) -> None:
        v = QQuickView()
        v.setTitle("FlowLocal")
        v.setColor(QColor(*T.BG))
        v.setResizeMode(QQuickView.SizeRootObjectToView)
        v.resize(W, H)
        v.setMinimumSize(QSize(MIN_W, MIN_H))
        ctx = v.rootContext()
        ctx.setContextProperty("T", self.tokens)
        ctx.setContextProperty("B", self.backend)
        # Переводчик - в каждое окно: строки интерфейса ходят через L.t().
        from theme_qt import Lang

        self.lang = Lang()
        ctx.setContextProperty("L", self.lang)
        base = os.path.dirname(os.path.abspath(__file__))
        import sys
        base = getattr(sys, "_MEIPASS", None) or base
        v.setSource(QUrl.fromLocalFile(os.path.join(base, "qml", "Settings.qml")))
        if v.status() == QQuickView.Error:
            raise RuntimeError("; ".join(e.toString() for e in v.errors()))
        # Окно могут закрыть прямо во время захвата - тогда хук keyboard остался
        # бы висеть, а приложение вообще без хоткея: снять-то мы его сняли, а
        # вернуть было бы уже некому.
        #
        # Ловим фильтром событий, а не сигналом closing: PySide не умеет
        # маршалить QQuickCloseEvent* и роняет вызов с TypeError.
        v.installEventFilter(self._filter)
        self.view = v
        self._style_titlebar()

    def _style_titlebar(self) -> None:
        """Заголовок окна - под нашу тему, средствами DWM.

        Рамка системная (нужны родные snap, alt-tab и кнопки), но белая полоса
        над тёмным интерфейсом - это чужеродно. Красим через DwmSetWindowAttribute:
        то же самое делала tkinter-версия, и при переезде это потерялось.

        create() обязателен: до него у окна нет HWND, и красить нечего.
        """
        import layered

        if self.view is None:
            return
        self.view.create()
        try:
            layered.style_titlebar(int(self.view.winId()), T.BG,
                                   dark=T.mode() == "dark")
        except Exception as e:  # noqa: BLE001 - косметика не должна ронять окно
            print(f"titlebar style failed: {e}")

    def open(self) -> None:
        if self.view is None:
            self._build()
        self.backend.reload()
        self.view.show()
        self.view.raise_()
        self.view.requestActivate()

    def close(self) -> None:
        self.backend.cancelCapture()
        if self.view is not None:
            self.view.hide()

    def retheme(self) -> None:
        self.tokens.retheme()
        if self.view is not None:
            self.view.setColor(QColor(*T.BG))
            self._style_titlebar()      # заголовок рисует Windows, сам он не узнает
