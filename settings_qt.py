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

import json
import os
import shutil
import subprocess
import threading
import time

from PySide6.QtCore import (Property, QEvent, QObject, QTimer, QUrl, Signal, Slot)
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

import app_paths
import config as C
import inputspec
import models
import stats
import theme as T
from theme_qt import Tokens
from util import plural

W, H = 900, 660


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


class Backend(QObject):
    """Мост между QML и конфигом. Всё, что QML умеет, - здесь."""

    changed = Signal()               # конфиг перечитан целиком
    flashed = Signal(str, str)       # текст, цвет ("", "danger", "accent")
    captureDone = Signal(str, str)   # поле, спецификация
    # Приватный: им колбэк из потока keyboard перебрасывает результат в главный
    # поток. Прямо из чужого потока трогать нельзя ничего - ни QTimer.start()
    # в set(), ни QML. Сигнал с авто-соединением кладётся в очередь получателя,
    # и это ровно то же, чем в tkinter-версии был after(0, ...).
    _captured = Signal(str)

    def __init__(self, on_change, on_hotkey_capture, info_fn,
                 history_path: str, log_path: str, on_onboarding=None) -> None:
        super().__init__()
        self._on_change = on_change
        self._on_hotkey_capture = on_hotkey_capture
        self._info_fn = info_fn
        self._on_onboarding = on_onboarding
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
        size = f"{m.size_mb} МБ, {m.langs}. " if m else ""
        self.flashed.emit(f"{size}Загружается в фоне, перезапуск не нужен", "accent")

    def _flush(self) -> None:
        try:
            C.save(self.cfg)
        except OSError as e:
            self.flashed.emit(f"не удалось сохранить: {e}", "danger")
            return
        self._on_change(dict(self.cfg))

    # ---------- списки для QML ----------

    @Property("QVariantList", constant=True)
    def modelOptions(self) -> list:
        return _opts([(m.title, m.id) for m in models.CATALOG])

    @Property("QVariantList", constant=True)
    def langOptions(self) -> list:
        return _opts([("авто", None), ("рус", "ru"), ("eng", "en")])

    @Property("QVariantList", constant=True)
    def deviceOptions(self) -> list:
        return _opts([("авто", "auto"), ("GPU", "cuda"), ("CPU", "cpu")])

    @Property("QVariantList", constant=True)
    def themeOptions(self) -> list:
        return _opts([("система", "system"), ("светлая", "light"), ("тёмная", "dark")])

    @Property("QVariantList", constant=True)
    def insertOptions(self) -> list:
        return _opts([("вставка", "paste"), ("посимвольно", "type")])

    @Property("QVariantList", notify=changed)
    def micOptions(self) -> list:
        """Один физический микрофон PortAudio показывает по разу на каждый
        host-api, поэтому имя без api - это три одинаковые строки и гадание."""
        from recorder import default_input_name, list_input_devices

        out = [{"label": f"по умолчанию · {default_input_name()}", "value": None}]
        for i, name, api in list_input_devices():
            out.append({"label": f"{name} · {api}", "value": i})
        return out

    # ---------- строки-подсказки ----------

    @Slot(str, result=str)
    def pretty(self, spec: str) -> str:
        return inputspec.pretty(spec or "")

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
                       "на вкладке «Распознавание».")

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

    # ---------- история ----------

    @Slot(result="QVariantList")
    def history(self) -> list:
        rows = []
        try:
            with open(self.history_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except ValueError:
                            pass
        except OSError:
            pass
        return [{"ts": str(r.get("ts", "")), "sec": r.get("sec", 0),
                 "text": str(r.get("text", ""))} for r in reversed(rows[-400:])]

    @Slot(result=str)
    def historyNote(self) -> str:
        rows = self.history()
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
        self.flashed.emit("скопировано в буфер", "")

    @Slot()
    def clearHistory(self) -> None:
        try:
            open(self.history_path, "w", encoding="utf-8").close()
        except OSError as e:
            self.flashed.emit(f"не удалось очистить: {e}", "danger")
            return
        self.flashed.emit("история очищена", "")

    # ---------- статистика ----------

    @Slot(result="QVariantMap")
    def stats(self) -> dict:
        rows = stats.load(self.history_path)
        s = stats.summary(rows)
        days = stats.by_day(rows, 30)
        top = max((v for _d, v in days), default=0)
        return {
            "dictations": f"{s['dictations']}",
            "words": f"{s['words']}",
            "avg_words": f"{s['avg_words']:.0f}",
            "seconds": _dur(s["seconds"]),
            "saved_sec": _dur(s["saved_sec"]),
            "values": [v for _d, v in days],
            "range": (f"{days[0][0]} - {days[-1][0]}   ·   пик {top} "
                      f"{plural(top, 'слово', 'слова', 'слов')} в день") if days
                     else "Пока пусто. Продиктуйте что-нибудь.",
            "speechWpm": stats.SPEECH_WPM,
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
            try:
                import onnx_asr

                # load_model и качает, и грузит; загруженный экземпляр тут же
                # выбрасывается - это «скачать заранее», а не «включить».
                onnx_asr.load_model(m.id, path=d, quantization=m.quant,
                                    providers=["CPUExecutionProvider"])
                self.modelProgress.emit(model_id, 1.0)
                self.flashed.emit(f"{m.title} скачана", "")
            except Exception as e:  # noqa: BLE001
                self.flashed.emit(f"не удалось скачать: {e}", "danger")
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
            self.flashed.emit(f"не удалось удалить: {e}", "danger")
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
            self.flashed.emit(f"не удалось: {e}", "danger")

    @Slot(result=str)
    def about(self) -> str:
        return "\n".join(f"{k}: {v}" for k, v in (self._info_fn() or {}).items())

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
                 history_path: str, log_path: str, on_onboarding=None) -> None:
        self.backend = Backend(on_change, on_hotkey_capture, info_fn,
                               history_path, log_path, on_onboarding=on_onboarding)
        self.tokens = Tokens()
        self.view: QQuickView | None = None
        self._filter = _CloseFilter(self.backend.cancelCapture)

    def _build(self) -> None:
        v = QQuickView()
        v.setTitle("FlowLocal")
        v.setColor(QColor(*T.BG))
        v.setResizeMode(QQuickView.SizeRootObjectToView)
        v.resize(W, H)
        v.setMinimumSize(v.size())
        ctx = v.rootContext()
        ctx.setContextProperty("T", self.tokens)
        ctx.setContextProperty("B", self.backend)
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
