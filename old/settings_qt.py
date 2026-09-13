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
import platform_api


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
import language
import models
import notes
import stats
import theme as T
from theme_qt import Tokens
from util import plural

# Канон Korti (templates/app-shell) свёрстан под 1280x820; нам хватает
# скромнее, но 900 узко: широкие подписи настроек становились тесными.
#
# Окно ОДНО на всю программу. Был день, когда его разделили надвое и «Главная»
# с «Историей» и «Статистикой» уехали в 460x560 рядом с треем; владелец
# запустил, увидел маленькое окно и сказал убрать. Второй размер здесь заводить
# больше не надо.
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


def _card_dur(sec) -> str:
    """Длительность для карточки «Истории»: «5.4 с», а дальше минуты.

    Секунды с одним знаком - их так и пишет app (round(dur, 1)), и на короткой
    фразе десятая доля видна. На минутах доли - шум, там отдаёт _dur («3 мин»)."""
    try:
        sec = float(sec)
    except (TypeError, ValueError):
        return ""
    return f"{sec:.1f} с" if sec < 60 else _dur(sec)


def _card_words(text: str) -> str:
    """«8 слов» со склонением. Русские числительные живут в Python (plural),
    как и в _note рядом: собрать их в QML - верный способ получить «1 слов»."""
    n = len((text or "").split())
    return f"{n} {plural(n, 'слово', 'слова', 'слов')}"


def _opts(pairs) -> list:
    """[(подпись, значение)] -> [{label, value}] для QML."""
    return [{"label": lbl, "value": val} for lbl, val in pairs]


# На чём считает распознавание - словом, а не кодом провайдера. В интерфейсе
# нет ни `cpu`, ни `cuda`: человек, который просто пишет письма, их не
# опознает (CLAUDE.md, «для кого это»). Слова те же, что в выборе устройства
# на странице «Диктовка» (deviceOptions), - одна пара слов на всю программу,
# и переводятся они одним ключом в i18n.
_DEVICE_WORDS = {"cpu": "процессор", "cuda": "видеокарта", "dml": "видеокарта"}


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
    # Видеокарта через DirectML: этап словами и доля; на выходе - вышло ли,
    # фраза об отказе и сам замер (секунды до/после, чем считала).
    dmlStage = Signal(str, float)
    dmlDone = Signal(bool, str, "QVariantMap")
    # Приватный: им колбэк из потока keyboard перебрасывает результат в главный
    # поток. Прямо из чужого потока трогать нельзя ничего - ни QTimer.start()
    # в set(), ни QML. Сигнал с авто-соединением кладётся в очередь получателя,
    # и это ровно то же, чем в tkinter-версии был after(0, ...).
    _captured = Signal(str)
    # Тот же приём и по той же причине: замер видеокарты кончается в своём
    # потоке, а решение по нему пишет конфиг - то есть дёргает QTimer в set().
    _dml_ready = Signal("QVariantMap")
    # «Привести в порядок» на странице «Заметки»: id, готовый текст, жалоба
    # ("" - всё вышло). Публичный, слушает QML (страница обновляет поле и список).
    noteTidied = Signal(str, str, str)
    # Приватный, тот же приём: причёсывание считает рабочий поток, а трогать QML
    # и конфиг можно только из главного - сигнал переносит результат сам.
    _note_ready = Signal(str, str)

    def __init__(self, on_change, on_hotkey_capture, info_fn,
                 history_path: str, log_path: str, on_onboarding=None,
                 update_fn=None, do_update=None,
                 llm_install=None, llm_busy=None, redo_fn=None,
                 tidy_fn=None, transcribe_fn=None) -> None:
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
        self._tidy_fn = tidy_fn      # причесать заметку (app._tidy_note)
        self._transcribe_fn = transcribe_fn   # расшифровать перетащенный файл
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
        self._dml_busy = False       # идёт ли проба видеокарты
        self._captured.connect(self._finish)
        self._dml_ready.connect(self._dml_apply)
        self._note_ready.connect(self._on_note_ready)

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
            self.flashed.emit("настройка не сохранилась", "danger")
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

    # ---------- заметки ----------
    #
    # Заметки - страница главного окна (qml/windows/Settings.qml), а не отдельное
    # окно: диктуют в поле редактора на ней. Хранение, поиск и уборка - в notes.py;
    # «привести в порядок» идёт через ту же правку текста, что и трансформы
    # (app._tidy_note), вторым путём к Ollama не обзаводимся. Прежнее окно
    # (notes_qt.NotesWindow) ретайрено, его логика перенесена сюда как есть.

    @Slot(str, result="QVariantList")
    def notesList(self, query: str = "") -> list:
        """Заметки для страницы, свежие первыми. query - поиск по тексту."""
        return notes.listing(query)

    @Slot(str, result=str)
    def noteText(self, note_id: str) -> str:
        """Текст заметки целиком - страница кладёт его в поле редактора."""
        d = notes.load(note_id)
        return (d or {}).get("text", "") if d else ""

    @Slot(result=str)
    def newNote(self) -> str:
        """Завести пустую заметку, вернуть идентификатор. Пусто - не вышло."""
        return notes.save(notes.new_id(), "")

    @Slot(str, str)
    def saveNote(self, note_id: str, text: str) -> None:
        """Сохранить заметку. Зовётся автосейвом и перед уходом к списку."""
        if note_id:
            notes.save(note_id, text)

    @Slot(str)
    def deleteNote(self, note_id: str) -> None:
        notes.delete(note_id)

    @Slot(str, str)
    def tidyNote(self, note_id: str, text: str) -> None:
        """«Привести в порядок»: причесать заметку моделью в отдельном потоке.

        Тот же путь, что был в notes_qt.improve: работа долгая (целая страница),
        поэтому уходит в поток, а результат возвращается сигналом - QML и конфиг
        трогают только из главного потока (см. _captured).
        """
        def work() -> None:
            got = ""
            try:
                if self._tidy_fn is not None:
                    got = self._tidy_fn(text, notes.TIDY)
            except Exception as e:  # noqa: BLE001 - заметки не должны ронять окно
                _log(f"заметку не причесать: {e}")
            self._note_ready.emit(note_id, got)

        threading.Thread(target=work, daemon=True).start()

    def _on_note_ready(self, note_id: str, text: str) -> None:
        """Итог «привести в порядок», уже в главном потоке (через _note_ready).

        Пусто - правки текста нет или она молчит: говорим словами, почему, и
        разница важна (поставить с нуля против разбудить). Иначе сохраняем
        причёсанное и отдаём странице, чтобы поле и список обновились.
        """
        if not text:
            import i18n
            import ollama_setup as O

            why = ("правка текста не отвечает"
                   if O.state() == O.STATE_SLEEPING
                   else "правка текста не установлена - откройте настройки")
            self.noteTidied.emit(note_id, "", i18n.t(why))
            return
        notes.save(note_id, text)
        self.noteTidied.emit(note_id, text, "")

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
                self.flashed.emit("модель знаков не скачалась", "danger")
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

    @Slot(result="QVariantMap")
    def statusInfo(self) -> dict:
        """Строка состояния «Главной»: готов ли, чем распознаёт, на чём считает.

        Одним заходом и из приложения, а не из своей копии конфига. Модель
        меняют в СОСЕДНЕМ окне (настройки), у которого свой Backend, и своя
        копия узнала бы об этом только со следующего открытия. `info_fn` -
        это живое приложение: оно перегружает модель на лету
        (app._reload_model_bg) и знает, что сейчас загружено на самом деле.

        Ключи с подчёркиванием служебные - см. app._info(): наружу, в «О
        программе», они не идут, их читает только эта страница.
        """
        try:
            info = self._info_fn() or {}
        except Exception:  # noqa: BLE001 - главная не должна падать из-за строки
            info = {}
        state = str(info.get("состояние", ""))
        m = models.get(str(info.get("_model") or ""))
        return {
            # Готовность - отрицанием: состояний «работает» много («готов ·
            # Ctrl + Shift + Space», «не назначено сочетание»), а неготовность
            # ровно одна - модель ещё едет. Проверять список хороших значило бы
            # чинить точку каждый раз, когда добавится новая фраза.
            "ready": not (state.startswith("просыпаюсь")
                          or state.startswith("загрузка")),
            "model": m.title if m else "",
            "device": _DEVICE_WORDS.get(str(info.get("_device") or ""), ""),
        }

    @Slot(str, result=str)
    def ago(self, ts: str) -> str:
        """«2 минуты назад» для карточки последней диктовки.

        Считает stats: там уже живёт разбор истории и её формат времени, и
        второго мнения о том, что такое «вчера», в программе быть не должно.
        """
        return stats.ago(ts)

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
        # Фразы включённых заготовок прячем из таблицы «Подстановки»: они уже
        # показаны блоком «Готовые» выше, и дублировать их там - ровно то, чего
        # задача велит не делать. Живут они при этом в тех же snippets.
        hide = self._preset_says() if key == "snippets" else set()
        # Признак «эту строку принесли мы» - по нему таблица прячет полторы
        # сотни технических терминов под свёрнутый пункт: владелец сказал, что
        # среди них не найти собственных трёх подстановок. Не удаляем и не
        # запираем - убираем с глаз.
        #
        # Критерий тот же, что у techdict.strip_from, и это не совпадение, а
        # условие. Там он решает, что можно снять при выключении терминов, здесь -
        # что можно спрятать; разойдись они, человек получил бы строку, которую
        # прячут как нашу, а при выключении оставляют как его. Сверяем и ключ, и
        # значение: переписал «апи» на своё - строка стала его и уезжает наверх,
        # к своим.
        #
        # Словарь берём один раз на всю таблицу, а не на строку: строк тут под
        # две сотни.
        tech = self._tech_terms(key)
        return [{"k": str(k), "v": str(v),
                 "ready": str(k).lower() in tech and str(v) == tech[str(k).lower()]}
                for k, v in d.items() if k not in hide]

    @staticmethod
    def _tech_terms(key: str) -> dict:
        """Технические термины - или пусто, если таблица не про подстановки.
        Правила тона (второй хозяин PairTable) наших строк не содержат вовсе."""
        if key != "snippets":
            return {}
        import techdict

        return techdict.TERMS

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
        # Заготовки в таблице не показаны (pairs их спрятал), но живут в тех же
        # snippets - вернём их, иначе пересборка словаря из ОДНИХ видимых строк
        # тихо стёрла бы включённую почту-подпись человека.
        if key == "snippets":
            cur = C.get(self.cfg, "snippets", {}) or {}
            for say in self._preset_says():
                if say not in out and say in cur:
                    out[say] = cur[say]
        self.set(key, out)

    def _preset_says(self) -> set:
        """Фразы включённых готовых подстановок (config.snippets_presets_on).

        Одно место, где список id превращается в набор фраз: и pairs, и setPairs
        решают по нему, что прятать из таблицы и что сохранить сверх неё.
        """
        import techdict

        on = set(self.cfg.get("snippets_presets_on") or [])
        return {p["say"] for p in techdict.PRESETS if p["id"] in on}

    @Slot(result="QVariantList")
    def snippetPresets(self) -> list:
        """Готовые подстановки-заготовки для блока «Готовые» на «Словах».

        Список - данными (techdict.PRESETS), не разметкой: тот же приём, что у
        техтерминов (techdict.TERMS) и готовых преобразований (transforms.PRESETS).

        Значение отдаём текущее из snippets (человек мог вписать своё), а до
        включения - заготовочное. preview - что вставится с раскрытыми
        переменными: для готовых заготовок это и есть подпись «Вставит: …».
        """
        import cleaner
        import techdict

        on = set(self.cfg.get("snippets_presets_on") or [])
        snips = self.cfg.get("snippets") or {}
        out = []
        for p in techdict.PRESETS:
            enabled = p["id"] in on
            value = str(snips.get(p["say"], p["put"])) if enabled else p["put"]
            out.append({
                "id": p["id"], "say": p["say"], "put": p["put"],
                # Пустую заготовку человек заполняет сам, у готовой значение есть.
                "fill": p["put"] == "",
                "enabled": enabled,
                "value": value,
                # \n в подпись не тащим - там она разорвала бы строку.
                "preview": cleaner._fill_vars(p["put"]).replace("\n", " ")
                           if p["put"] else "",
            })
        return out

    @Slot(str, bool)
    def setSnippetPreset(self, pid: str, on: bool) -> None:
        """Включить или выключить готовую подстановку.

        Механика - как у setTechTerms: заготовка падает в те же snippets, и
        человек правит её там же. Отличие одно - у заготовки есть id, и он
        копится в snippets_presets_on (как transforms_hidden у преобразований):
        по нему блок «Готовые» знает, что показать включённым, а таблица
        «Подстановки» - что не дублировать.

        Не затираем чужое (merge_into) и не сносим правленое (strip_from):
        включение чужой уже заведённой фразы берёт её значение, а выключение
        снимает только нетронутую заготовку - заполненная остаётся обычной
        подстановкой, чтобы промах по тумблеру не стоил вписанной почты.
        """
        import techdict

        p = techdict.preset(pid)
        if p is None:
            return
        ids = [i for i in (self.cfg.get("snippets_presets_on") or []) if i != pid]
        snips = dict(self.cfg.get("snippets") or {})
        if on:
            ids.append(pid)
            if p["say"] not in snips:
                snips[p["say"]] = p["put"]
        elif snips.get(p["say"]) == p["put"]:
            snips.pop(p["say"], None)
        C.set_(self.cfg, "snippets_presets_on", ids)
        C.set_(self.cfg, "snippets", snips)
        self._flush()
        self.changed.emit()

    @Slot(str, str)
    def setSnippetPresetValue(self, pid: str, value: str) -> None:
        """Человек вписывает своё значение в заготовку прямо в блоке «Готовые».

        Пишем в те же snippets - второго хранилища нет. set() уже склеивает
        частые правки таймером и не дёргает changed, поэтому набор в поле не
        перерисовывает блок под курсором."""
        import techdict

        p = techdict.preset(pid)
        if p is None:
            return
        snips = dict(self.cfg.get("snippets") or {})
        snips[p["say"]] = value
        self.set("snippets", snips)

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

    @Slot(result="QVariantList")
    def pickerItems(self) -> list:
        """Что показать в списке преобразований - с идентификаторами.

        Не customTransforms: тот отдаёт только название и указание, потому что
        обслуживает таблицу правки на странице «Слова», где id ни к чему. А
        выбор без id молча уходит в никуда - применять-то нечего.

        Берём transforms.all_for, то есть ровно тот же список, по которому
        работает Python. Собирать его на странице нельзя: готовые лежат кодом,
        спрятанные - в конфиге, и второй сборщик разъехался бы с первым в
        первый же день.
        """
        import transforms

        return [dict(x) for x in transforms.all_for(self.cfg)]

    @Slot(str, str, result=str)
    def saveText(self, text: str, suggest: str = "") -> str:
        """Спросить, куда сохранить, и сохранить. Возвращает путь или пустое.

        Диалог выбора файла живёт в Python и жить будет: у страницы нет
        доступа к диску, а «сохранить как» из браузера отдаёт файл в загрузки,
        а не туда, куда человек показал.

        Имя предлагаем от исходного, если его дали: человек, расшифровавший
        десять голосовых, иначе получил бы десять «Новый текстовый документ».
        """
        import time

        from PySide6.QtWidgets import QFileDialog

        import i18n

        stem = (os.path.splitext(suggest)[0]
                or time.strftime("Расшифровка-%Y-%m-%d"))
        path, _ = QFileDialog.getSaveFileName(
            None, i18n.t("Куда сохранить"), stem + ".txt",
            i18n.t("Текст") + " (*.txt)")
        if not path:
            return ""
        try:
            # Переводы строк windows-овские: файл откроют Блокнотом, а он до
            # сих пор показывает одинокий \n одной длинной строкой.
            with open(path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(text)
        except OSError as e:
            _log(f"не сохранилось: {e}")
            self.flashed.emit(i18n.t("файл не сохранился"), "danger")
            return ""
        self.flashed.emit(i18n.t("сохранено"), "")
        return path

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
        # `src` - откуда речь. Пусто у всего, что надиктовано в микрофон, то
        # есть у подавляющего большинства строк; помечаем только исключение.
        # Помечать заодно и «с микрофона» значило бы дописать одинаковое слово
        # к каждой строке истории - шум, по которому ничего не отличить.
        #
        # `when`/`dur`/`words` - готовые строки для карточки «Истории»: дата
        # словами и склонение слов держатся в Python (тот же довод, что у
        # _note и stats), а не собираются в QML, где русского склонения нет.
        out = []
        for r in reversed(rows[-400:]):
            text = str(r.get("text", ""))
            out.append({"ts": str(r.get("ts", "")), "sec": r.get("sec", 0),
                        "text": text,
                        "fromFile": str(r.get("src", "")) == "file",
                        "when": stats.human_moment(r.get("ts", "")),
                        "dur": _card_dur(r.get("sec", 0)),
                        "words": _card_words(text)})
        return out

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
            self.flashed.emit("история не очистилась", "danger")
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
        # Неделя, а не тридцать дней. Тридцать столбиков в 372 пикселя - это
        # 12 пикселей на день, и подпись под ними не помещается никакая:
        # график был красивой полоской без единой подписи, по которой нельзя
        # сказать даже, где вчера. Семь дней дают 47 пикселей на столбик -
        # хватает и на «пн», и на попадание мышью ради подсказки.
        week = stats.week(rows)
        best = stats.best_day(rows)

        # Личный множитель «во сколько раз речь быстрее печати» - замер по
        # истории, а не лозунг из рекламы. На паре коротких фраз число ещё
        # случайное, поэтому до минуты записи честнее промолчать: прочерк
        # вместо цифры, взятой с потолка.
        enough = s["seconds"] >= 60 and s["words"] >= 50
        ratio = s["speech_wpm"] / stats.TYPING_WPM
        streak = s["streak_days"]

        # Средние слова за день недели - для линии среднего на графике.
        # Считаем здесь, в Python, а не в QML: правило проекта - числа считает
        # Python, QML их рисует. По семи дням, включая нулевые: это средний
        # день недели, а не средний из «дней, когда диктовал».
        week_avg = round(sum(d["words"] for d in week) / len(week), 1) if week else 0

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
            # Число отдельно от подписи: в метрике наверху «Статистики» слово
            # стоит подписью под цифрой, и «3 дня» под подписью «дней подряд»
            # сказало бы «дней» дважды.
            "streakDays": streak,
            # Рекорд серии - потолок дуги «дней подряд»: текущая серия рисуется
            # долей от него, полная дуга значит «вы на своём рекорде».
            "streakBest": s["best_streak"],
            # Средний день недели - высота линии среднего на графике.
            "weekAvg": week_avg,
            # Столбики недели. Подсказка собрана здесь, а не в QML: русское
            # склонение числительных живёт в Python (plural), и заводить его
            # второй раз на JavaScript - верный способ получить «1 слов».
            "week": [{
                "label": d["label"],
                "value": d["words"],
                "today": d["today"],
                "hint": (f"{d['human']} · {d['words']} "
                         f"{plural(d['words'], 'слово', 'слова', 'слов')}"),
            } for d in week],
            # Рекорд: пусто - ключа хватит проверить в QML одним условием.
            "hasBest": best is not None,
            "bestWords": (f"{best['words']} "
                          f"{plural(best['words'], 'слово', 'слова', 'слов')}"
                          if best else ""),
            "bestDate": best["human"] if best else "",
            "typingWpm": stats.TYPING_WPM,
        }

    @Slot(result="QVariantMap")
    def calendar(self) -> dict:
        """Клетки по дням за полгода - для календаря под серией («Статистика»).

        Отдельным слотом, а не полем _stats, намеренно. Календарь раскрывают
        нажатием на серию, и открывают его далеко не в каждый заход; _stats же
        зовётся и «Главной» (homeData) при каждом открытии окна. Сто восемьдесят
        клеток с подписями, которые Главной не нужны вовсе, ездили бы туда
        просто так. Здесь они считаются, когда на них нажали.

        Подсказки собраны тут, а не в QML, по той же причине, что у недельного
        графика: русское склонение числительных живёт в Python (util.plural), и
        заводить его второй раз на JavaScript - верный способ получить «1 слов».
        """
        cal = stats.calendar(stats.load(self.history_path))
        return {
            "weeks": cal["weeks"],
            "weekdays": cal["weekdays"],
            "months": cal["months"],
            "days": [{
                "level": d["level"],
                "today": d["today"],
                "future": d["future"],
                # У будущих дней подсказки нет: показывать «19 июля · 0 слов»
                # про послезавтра значит утверждать, что там уже ноль.
                "hint": "" if d["future"] else
                        (f"{d['human']} · {d['words']} "
                         f"{plural(d['words'], 'слово', 'слова', 'слов')}"),
            } for d in cal["days"]],
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
                self.flashed.emit("не вышло начать скачивание", "danger")
            finally:
                self._downloading.discard(model_id)
                self.modelsChanged.emit()

        threading.Thread(target=poll, daemon=True).start()
        threading.Thread(target=work, daemon=True).start()

    @Slot(result=bool)
    def englishReady(self) -> bool:
        """Приехала ли модель, которая пишет английский буквами."""
        return language.installed()

    @Slot(result=int)
    def starterMb(self) -> int:
        """Во что обойдётся первый запуск: обе модели вместе.

        Цену называем ДО скачивания, а не после, - как на экране Ollama
        («Скачаем 3.3 ГБ»). Человек должен знать, во что ввязался, до того как
        нажал, а не по проценту на полосе.
        """
        m = models.get(str(self.cfg.get("model") or models.DEFAULT))
        return int((m.size_mb if m else 0) + language.SIZE_MB)

    @Slot(str)
    def downloadStarter(self, model_id: str) -> None:
        """Мастер первого запуска: обе модели одной полосой.

        Английская не выбирается и не ищется в настройках - она приезжает
        вместе с основной. Владелец сказал прямо: «она обязательная, а то
        человек зайдёт, увидит что у нас английский не даётся и не найдёт в
        настройках». Настройка, которую надо найти, для человека не существует.

        Отсюда и одна полоса на две скачки: два места в интерфейсе - это два
        решения, а решать тут нечего.
        """
        from transcriber import model_dir

        m = models.get(model_id)
        if m is None or model_id in self._downloading:
            return
        self._downloading.add(model_id)
        self.modelsChanged.emit()
        dirs = [(model_dir(m.id, m.quant), float(m.size_mb)),
                (language.folder(), float(language.SIZE_MB))]
        total = sum(size for _d, size in dirs)

        def poll() -> None:
            # Прогресс - по росту папок: huggingface_hub наружу процентов не
            # отдаёт, а размер честный (models.py сверен с метаданными
            # репозитория, английский - с настоящей скачкой).
            while model_id in self._downloading:
                got = 0.0
                for d, _size in dirs:
                    try:
                        got += (sum(os.path.getsize(os.path.join(d, f))
                                    for f in os.listdir(d)) / 1e6
                                if os.path.isdir(d) else 0.0)
                    except OSError:
                        pass
                self.modelProgress.emit(model_id, min(0.99, got / total))
                time.sleep(0.4)

        def work() -> None:
            # Отдельными процессами и по очереди, а не двумя сразу: у человека
            # один канал, и параллельная качка только запутает полосу. Про
            # процесс вместо потока - см. app.download_model_cli.
            try:
                for what in (model_id, language.DOWNLOAD_ID):
                    r = subprocess.run(
                        _download_cmd(what), capture_output=True, text=True,
                        encoding="utf-8", errors="replace",
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if r.returncode != 0:
                        _log(f"{what} не скачалась: "
                             + (r.stderr or r.stdout or "").strip()[:300])
                        self.flashed.emit("не удалось скачать - проверьте интернет",
                                          "danger")
                        return
                self.modelProgress.emit(model_id, 1.0)
                self.flashed.emit("всё скачано", "")
            except Exception as e:  # noqa: BLE001
                _log(f"загрузчик модели не запустился: {e}")
                self.flashed.emit("не вышло начать скачивание", "danger")
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
            self.flashed.emit("модель не удалилась", "danger")
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
        # Ключи с подчёркиванием пропускаем: это служебное для статус-строки
        # «Главной» (statusInfo), а не строки для чтения. Ровно за такое
        # «устройство: cpu / int8» когда-то и убрали с этой страницы -
        # человеку, который просто пишет письма, оно не говорит ничего.
        return "\n".join(f"{k}: {v}" for k, v in (self._info_fn() or {}).items()
                         if not k.startswith("_"))

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
        if not platform_api.CAN_HOTKEYS:
            # macOS: библиотеки keyboard нет, ловить сочетание нечем. Не падаем
            # на импорте из QML-слота - поле просто не начнёт захват.
            platform_api.note_unsupported("захват сочетания клавиш")
            return
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
        if not platform_api.CAN_HOTKEYS:
            # На маке захват и не начинался (startCapture вышел рано) - но эту
            # функцию зовут и на закрытии окна, безусловно. Импорт keyboard там
            # уронил бы закрытие настроек, поэтому выходим до него.
            self._cap_field = ""
            return
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

    @Slot(result="QVariantList")
    def oldVersions(self) -> list:
        """Прежние версии (архив 0.x) для выплывающей панели на «О программе».

        В CHANGELOG.md весь 0.x схлопнут в одну строку «1.0» - и правильно
        схлопнут, человеку с новой установкой не нужен список того, чего он не
        видел. Полная история лежит в docs/history-0.x.md, и владелец захотел
        её видеть: показываем по кнопке, выплывающей панелью.

        Путь - тем же механизмом, что у CHANGELOG.md (changelog.path): база это
        _MEIPASS в сборке, иначе папка кода. В сборке файл кладётся под docs/
        (flowlocal.spec), поэтому и здесь docs/ - одно выражение пути на оба
        случая. Разбираем тем же парсером (changelog.parse), второго слоя нет.

        Нет файла (старая сборка, где его не клали) - пустой список, и кнопка
        на странице просто не появится. Никакой ошибки: архив - украшение.
        """
        import changelog as CL

        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "docs", "history-0.x.md")
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return []
        return [{"version": r["version"], "date": r["date"],
                 "title": r["title"], "items": r["items"]}
                for r in CL.parse(text)]

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
            self.flashed.emit("файл не сохранился", "danger")
            return ""
        what = f"{n} {plural(n, 'настройка', 'настройки', 'настроек')}"
        if history:
            what += (f" и {len(history)} "
                     f"{plural(len(history), 'диктовка', 'диктовки', 'диктовок')}")
        self.flashed.emit(f"сохранено: {what}", "accent")
        return path

    @Slot("QVariant")
    def dropFile(self, url) -> None:
        """На окно перетащили файл - отдать его приложению на расшифровку.

        Приезжает QUrl, а не путь: перетаскивание в Qt всегда про URL. Путь
        достаём через toLocalFile() - ручной разбор строки «file:///C:/...»
        споткнулся бы на первом же пробеле в имени папки, а у людей они
        сплошь («Рабочий стол», «Мои документы»).

        Разбираться, годится ли файл, здесь не начинаем: этим занимается
        audiofile.check в приложении, и он там один на обе двери - и на
        перетаскивание, и на пункт трея. Второе мнение о том, какие файлы мы
        открываем, рано или поздно разошлось бы с первым.
        """
        if self._transcribe_fn is None:
            return
        try:
            path = url.toLocalFile() if hasattr(url, "toLocalFile") else str(url)
        except Exception as e:  # noqa: BLE001 - чужая ссылка не должна ронять окно
            _log(f"перетащили что-то нечитаемое: {e}")
            return
        if not path:
            # Перетащили ссылку из браузера, а не файл с диска. Молчать нельзя -
            # человек ждёт хоть какого-то ответа на своё действие.
            self.flashed.emit("это не файл с диска", "danger")
            return
        self._transcribe_fn(path)

    @Slot(result=str)
    def pickInboxPath(self) -> str:
        """Выбрать файл для диктовки в файл. Возвращает путь или пусто.

        Диалог именно СОХРАНЕНИЯ, а не открытия, хотя файл чаще всего уже
        существует. Причина - в том, что инбокс можно завести с нуля: диалог
        открытия не даёт вписать имя несуществующего файла, и человеку пришлось
        бы сначала создавать пустой .md в проводнике. Существующий файл
        getSaveFileName выбирает так же, только спросит про замену - а замены не
        будет: inbox.append дописывает в конец, а не перезаписывает.
        """
        from PySide6.QtWidgets import QFileDialog

        start = str(self.cfg.get("inbox_path") or "").strip()
        if not start:
            start = os.path.join(os.path.expanduser("~"), "входящие.md")
        path, _ = QFileDialog.getSaveFileName(
            None, "Файл для диктовки", start,
            "Заметка (*.md *.txt);;Все файлы (*)",
            options=QFileDialog.DontConfirmOverwrite)
        if not path:
            return ""
        self.set("inbox_path", path)
        self.changed.emit()
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

        return O.state() == O.STATE_READY

    @Slot(result=str)
    def llmState(self) -> str:
        """Почему правки текста нет: ready / sleeping / no_model / absent.

        Окну мало «да/нет»: заголовок и подпись кнопки у «не установлена» и у
        «установлена, но молчит» разные, а действие одно и то же (ensure сам
        разберётся, что доделать). Раньше оба случая назывались «не
        установлена», и человеку с уснувшей Ollama предлагали скачать три
        гигабайта поверх трёх имеющихся.
        """
        import ollama_setup as O

        return O.state()

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
        """Колбэк из потока установки. Сигнал сам перебросит в главный поток.

        Этапы приезжают из ollama_setup готовыми русскими фразами - переводим
        здесь, на границе с окном, как и этапы пробы видеокарты (dmlRun). В
        самом ollama_setup i18n нет намеренно: он работает и из консоли, где
        язык интерфейса ни при чём.
        """
        import i18n

        if done is None:
            self.llmStage.emit(i18n.t(stage), frac, float(total))
        else:
            self.llmDone.emit(bool(done))

    @Slot(result=bool)
    def llmBusy(self) -> bool:
        """Идёт ли установка прямо сейчас. Нужно окну, открытому посреди неё:
        без этого оно показало бы кнопку «Установить», как будто ничего не
        происходит, и человек нажал бы второй раз."""
        return bool(self._llm_busy_fn()) if self._llm_busy_fn else False

    # ---------- видеокарта: DirectML одной кнопкой (PLAN 10) ----------

    @Slot(result="QVariantMap")
    def dmlState(self) -> dict:
        """Что показать в ряду до первого нажатия.

        why - непустая строка, если кнопку нажимать бессмысленно (сборка, не
        Windows). active - считает ли видеокарта ПРЯМО СЕЙЧАС; спрашиваем живое
        приложение через info_fn, а не свой процесс: у окна настроек модели
        нет, и «на чём считает» знает только оно.
        """
        import dml_setup as D

        try:
            dev = str((self._info_fn() or {}).get("_device") or "")
        except Exception:  # noqa: BLE001 - страница не должна падать из-за строки
            dev = ""
        return {"why": D.blocked(), "installed": D.installed(),
                "active": dev in ("dml", "cuda")}

    @Slot()
    def dmlRun(self) -> None:
        """Замерить, поставить колесо, замерить снова. Всё - в своём потоке.

        Хозяин здесь один и он же единственный (в отличие от Ollama, которую
        зовут ещё и из мастера), поэтому поток свой, а не в app.py. Тяжёлое всё
        равно уходит в отдельные процессы - и pip, и оба замера, - так что GIL
        этого окна занят не будет: ровно та беда, из-за которой скачивание
        модели переехало в процесс (см. downloadModel).
        """
        import dml_setup as D
        import i18n

        if self._dml_busy:
            return
        self._dml_busy = True
        self.dmlStage.emit(i18n.t("начинаю"), 0.02)

        def work() -> None:
            try:
                # Этапы приезжают из dml_setup готовыми русскими фразами -
                # переводим здесь, на границе с окном. В самом dml_setup i18n
                # нет намеренно: он работает и из консоли, где язык интерфейса
                # ни при чём.
                res = D.setup(on_stage=lambda n, f: self.dmlStage.emit(i18n.t(n), f),
                              log=_log)
            except Exception as e:  # noqa: BLE001 - ускорение не роняет диктовку
                _log(f"dml: {type(e).__name__}: {e}")
                res = {"ok": False, "error": "не вышло - смотрите журнал работы"}
            self._dml_busy = False
            # Через сигнал, а не вызовом: решение пишет конфиг, а конфиг
            # заводит QTimer - из чужого потока это запрещено (см. _captured).
            self._dml_ready.emit(res)

        threading.Thread(target=work, daemon=True).start()

    def _dml_apply(self, res: dict) -> None:
        """Записать вывод замера в конфиг и сказать человеку цифрами.

        Главное правило: проигравшую видеокарту НЕ оставляем в пути. Если
        короткая фраза на ней медленнее, прибиваем `device: cpu` - иначе после
        перезапуска «авто» взяло бы DirectML и диктовка молча стала бы
        медленнее, а виноватой выглядела бы программа.
        """
        import dml_setup as D
        import i18n

        if res.get("error"):
            self.dmlDone.emit(False, i18n.t(str(res["error"])), res)
            return
        if res.get("ok"):
            # «авто» само возьмёт DirectML после перезапуска (transcriber.
            # _providers). Ставим его явно: у человека мог стоять «процессор».
            self.set("device", "auto")
        else:
            # Колесо оставляем: на длинной записи оно всё равно втрое быстрее,
            # и человек может переключить «Распознавание медленное?» на
            # «видеокарта» сам. А умолчание - процессор, он тут быстрее.
            self.set("device", "cpu")
        _log(f"dml: {'быстрее' if res.get('ok') else 'медленнее'} - "
             f"видеокарта {res.get('gpu')}, процессор {res.get('cpu')}, "
             f"было {res.get('before')} ({res.get('before_device')}); "
             f"колесо {D.PACKAGE} {'на месте' if res.get('installed') else 'снято'}")
        self.dmlDone.emit(bool(res.get("ok")), "", res)



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
    """Окно программы: Главная, История, Статистика и настройки одной панелью.

    Открывается и закрывается, но не пересоздаётся: смена темы не требует
    пересборки - QML перечитывает токены по сигналу.

    В tkinter-версии окно приходилось собирать заново на каждую смену темы:
    часть красок впечатывалась в виджеты при создании. У QML краски - привязки,
    и пересборка не нужна вовсе.

    Окно единственное: и клик по трею, и ярлык из «Пуска», и пункт меню
    «Настройки…» ведут сюда. Имя класса осталось прежним - переименовывать
    его значило бы трогать app.py, витрину и сборку ради слова."""

    def __init__(self, on_change, on_hotkey_capture, info_fn,
                 history_path: str, log_path: str, on_onboarding=None,
                 update_fn=None, do_update=None,
                 llm_install=None, llm_busy=None, redo_fn=None,
                 tidy_fn=None, transcribe_fn=None) -> None:
        self.backend = Backend(on_change, on_hotkey_capture, info_fn,
                               history_path, log_path, on_onboarding=on_onboarding,
                               update_fn=update_fn, do_update=do_update,
                               llm_install=llm_install, llm_busy=llm_busy,
                               redo_fn=redo_fn, tidy_fn=tidy_fn,
                               transcribe_fn=transcribe_fn)
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
        v.setSource(QUrl.fromLocalFile(os.path.join(base, "qml", "windows", "Settings.qml")))
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
        # Прокрутку - в начало. Окно не пересоздаётся, а прячется, поэтому без
        # этого оно открывалось бы там, где его закрыли: с середины страницы,
        # без заголовка и первой карточки. Снаружи это неотличимо от обрезанного
        # окна - строка начинается с середины фразы, - и владелец так это и
        # прочитал, увидев «месте.» первой строкой.
        root = self.view.rootObject()
        if root is not None:
            try:
                root.resetScroll()
            except (AttributeError, RuntimeError) as e:
                _log(f"прокрутка не сбросилась: {e}")
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
