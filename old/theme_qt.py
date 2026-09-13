"""Мост theme.py -> QML: дизайн-система Korti как контекстное свойство `T`.

Правило проекта: токены живут в theme.py, один источник правды. Поэтому здесь
нет ни одного своего числа и ни одной своей краски - только переклад.

Свойства, а не константы: тема переключается на живом приложении (system /
light / dark), и QML должен об этом узнать. Отсюда сигнал changed - дёргается
из retheme() после T.set_theme().

Почему `T.px()` умножает на масштаб, а Qt и так знает про DPI: не умножает.
Qt масштабирует логические пиксели сам, и второй раз это делать нельзя -
получится двойное увеличение. Масштаб здесь остаётся 1.0 и живёт только ради
оверлея, где он нужен для попадания в физические пиксели монитора.
"""

import ctypes
import functools
import os
import sys

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QColor

import platform_api
import theme as T


@functools.lru_cache(maxsize=1)
def effects_ok() -> bool:
    """Втянуть в процесс Qt6QuickEffects.dll до загрузки QML. Получилось - в
    QML можно `import QtQuick.Effects`, не получилось - нельзя.

    Грабли PySide6, стоившие часа. QML-плагин (qml/QtQuick/Effects/
    effectsplugin.dll) грузится штатным загрузчиком Windows, а тот ищет
    зависимости по обычным путям - и не видит папку PySide6, которую Python
    прописал себе через os.add_dll_directory. Работает поэтому только то, чей
    Qt6*.dll УЖЕ загружен в процесс импортом Python-модуля.

    Отсюда странная картина: `import QtQuick` живёт (его Qt6Quick.dll притащил
    `from PySide6.QtQuick import QQuickView`), а `import QtQuick.Effects` падает
    с «Не найден указанный модуль» - у MultiEffect Python-модуля нет, тянуть
    его нечем. Правка PATH не помогает и делает хуже: она ломает и базовый
    QtQuick.

    Лечится тем же способом, каким Python тянет остальные: загрузить DLL руками.

    Живёт здесь, а не в overlay_qt, с 19.07.2026: тень появилась и у карточек
    окна настроек, а два одинаковых подъёма одной DLL в двух модулях - это два
    места, где однажды починят только одно. lru_cache держит один ответ на
    процесс: DLL грузится единожды, спрашивать её состояние может кто угодно.
    """
    # Грабли и лечение целиком про Windows: ctypes.WinDLL там нет вовсе, и его
    # вызов упал бы не OSError (который мы ловим), а AttributeError - прямо на
    # импорте overlay_qt, где эта функция и зовётся. На macOS зависимости
    # QtQuick.Effects резолвятся штатным загрузчиком, наш подпорки не нужны;
    # тени сейчас просто не будет, а окно покажется - QML грузит PillShadow/
    # CardShadow через Loader только когда этот флаг True (см. Overlay.qml).
    if not platform_api.IS_WINDOWS:
        return False
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        import PySide6

        base = os.path.dirname(PySide6.__file__)
    try:
        ctypes.WinDLL(os.path.join(base, "Qt6QuickEffects.dll"))
        return True
    except OSError:
        # Без него не будет тени, но окно покажется. Украшение не имеет права
        # ронять программу - ни пилюлю, ни настройки.
        return False


class Tokens(QObject):
    changed = Signal()

    def __init__(self, scale: float = 1.0) -> None:
        super().__init__()
        self._s = scale

    # ---------- служебное ----------

    @staticmethod
    def _c(c, alpha: float | None = None) -> QColor:
        """Цвет Korti -> QColor. Часть токенов уже с альфой (BORDER - это 13%
        чернил поверх бумаги, а не отдельная краска), и терять её нельзя:
        волосяная линия во всю непрозрачность превратит карточку в коробку."""
        if alpha is None:
            a = c[3] if len(c) > 3 else 255
        else:
            a = round(alpha * 255)
        return QColor(c[0], c[1], c[2], a)

    @Slot(float, result=int)
    def px(self, v: float) -> int:
        return round(v * self._s)

    @Slot(float, result="QColor")
    def inkA(self, alpha: float) -> QColor:
        """Чернила с прозрачностью. Все «серые» в системе - это чернила поверх
        бумаги, а не отдельные краски."""
        return self._c(T.INK, alpha)

    def set_scale(self, s: float) -> None:
        if abs(s - self._s) > 0.01:
            self._s = s
            self.changed.emit()

    def retheme(self) -> None:
        self.changed.emit()

    @Property(float, notify=changed)
    def scale(self) -> float:
        return self._s

    @Property(bool, notify=changed)
    def dark(self) -> bool:
        return T.mode() == "dark"

    @Property(bool, constant=True)
    def effects(self) -> bool:
        """Можно ли в QML `import QtQuick.Effects`.

        Живёт среди токенов, потому что спрашивают об этом ровно там же, где
        читают краски, - в компоненте, который рисует тень. Альтернатива была
        одна: пробрасывать признак свойством корня в каждое окно и оттуда вниз
        по дереву до карточки. Токены и так один общий объект на окно, и это
        уже тот самый «один источник правды», ради которого он заведён.

        constant, а не notify: DLL либо поднялась при старте процесса, либо нет.
        Переменной эта величина не бывает.
        """
        return effects_ok()

    @Property(str, notify=changed)
    def layout(self) -> str:
        """cards | lines. Здесь, а не в конфиге напрямую: раскладка - такой же
        токен оформления, как краска, и меняться должна тем же сигналом."""
        return T.layout()

    # ---------- краски ----------

    @Property(QColor, notify=changed)
    def bg(self) -> QColor:
        return self._c(T.BG)

    @Property(QColor, notify=changed)
    def paper(self) -> QColor:
        return self._c(T.PAPER)

    @Property(QColor, notify=changed)
    def ink(self) -> QColor:
        return self._c(T.INK)

    @Property(QColor, notify=changed)
    def surface(self) -> QColor:
        return self._c(T.SURFACE)

    @Property(QColor, notify=changed)
    def text(self) -> QColor:
        return self._c(T.TEXT)

    @Property(QColor, notify=changed)
    def textSecondary(self) -> QColor:
        return self._c(T.TEXT_SECONDARY)

    @Property(QColor, notify=changed)
    def textMuted(self) -> QColor:
        return self._c(T.TEXT_MUTED)

    @Property(QColor, notify=changed)
    def textFaint(self) -> QColor:
        return self._c(T.TEXT_FAINT)

    @Property(QColor, notify=changed)
    def border(self) -> QColor:
        return self._c(T.BORDER)

    @Property(QColor, notify=changed)
    def borderFlat(self) -> QColor:
        return self._c(T.BORDER_FLAT)

    @Property(QColor, notify=changed)
    def borderStrong(self) -> QColor:
        return self._c(T.BORDER_STRONG)

    @Property(QColor, notify=changed)
    def fill(self) -> QColor:
        return self._c(T.FILL)

    @Property(QColor, notify=changed)
    def fillSubtle(self) -> QColor:
        return self._c(T.FILL_SUBTLE)

    @Property(QColor, notify=changed)
    def fillStrong(self) -> QColor:
        return self._c(T.FILL_STRONG)

    @Property(QColor, notify=changed)
    def accent(self) -> QColor:
        return self._c(T.ACCENT)

    @Property(QColor, notify=changed)
    def accentHover(self) -> QColor:
        return self._c(T.ACCENT_HOVER)

    @Property(QColor, notify=changed)
    def accentFg(self) -> QColor:
        return self._c(T.ACCENT_FG)

    @Property(QColor, notify=changed)
    def success(self) -> QColor:
        return self._c(T.SUCCESS)

    @Property(QColor, notify=changed)
    def danger(self) -> QColor:
        return self._c(T.DANGER)

    @Property(QColor, notify=changed)
    def shadowNear(self) -> QColor:
        return QColor(*T.SHADOW_NEAR)

    @Property(QColor, notify=changed)
    def shadowFar(self) -> QColor:
        return QColor(*T.SHADOW_FAR)

    @Property(QColor, constant=True)
    def shadowOver(self) -> QColor:
        """Тень над ЧУЖИМ экраном - только чёрная, почему - в шапке theme.py."""
        return QColor(*T.SHADOW_OVER)

    # ---------- шрифты ----------

    @Property(str, constant=True)
    def sans(self) -> str:
        return T.TK_SANS

    @Property(str, constant=True)
    def mono(self) -> str:
        return T.TK_MONO

    # Пять кеглей, ни одного шестого. Почему именно пять и куда делись
    # остальные четыре - в theme.py, там же и роли каждого.
    @Property(int, constant=True)
    def t2xs(self) -> int:
        return T.T_2XS

    @Property(int, constant=True)
    def tSm(self) -> int:
        return T.T_SM

    @Property(int, constant=True)
    def tMd(self) -> int:
        return T.T_MD

    @Property(int, constant=True)
    def tXl(self) -> int:
        return T.T_XL

    @Property(int, constant=True)
    def tDisplay(self) -> int:
        return T.T_DISPLAY

    # ---------- метрика ----------

    @Property(int, constant=True)
    def radiusSm(self) -> int:
        return T.RADIUS_SM

    @Property(int, constant=True)
    def radiusMd(self) -> int:
        return T.RADIUS_MD

    @Property(int, constant=True)
    def radiusLg(self) -> int:
        return T.RADIUS_LG

    @Property(int, notify=changed)
    def pillH(self) -> int:
        return round(T.PILL_H * self._s)

    @Property(int, notify=changed)
    def pillWMax(self) -> int:
        return round(T.PILL_W_MAX * self._s)

    @Property(int, notify=changed)
    def pillPad(self) -> int:
        return round(T.PILL_PAD * self._s)

    @Property(int, notify=changed)
    def pillPadBottom(self) -> int:
        return round(T.PILL_PAD_BOTTOM * self._s)

    @Property(int, notify=changed)
    def waveW(self) -> int:
        return round(T.WAVE_W * self._s)

    @Property(int, notify=changed)
    def waveH(self) -> int:
        return round(T.WAVE_H * self._s)

    @Property(int, constant=True)
    def waveBars(self) -> int:
        return T.WAVE_BARS

    # ---------- движение ----------

    @Property(float, constant=True)
    def durFast(self) -> float:
        return T.T_FAST

    @Property(float, constant=True)
    def durBase(self) -> float:
        return T.T_DUR

    @Property(float, constant=True)
    def durSlow(self) -> float:
        return T.T_SLOW

    @Property("QVariantList", constant=True)
    def easeOut(self) -> list:
        """cubic-bezier(.2,.8,.2,1) - единственная кривая системы, без пружин."""
        return [0.2, 0.8, 0.2, 1.0]


class Lang(QObject):
    """Переводчик для QML: L.t("строка").

    Отдельным объектом, а не методом токенов: язык и оформление меняются по
    разным поводам, и мешать их в одном сигнале значит перерисовывать окно
    из-за темы, когда сменился язык, и наоборот.
    """

    changed = Signal()

    @Slot(str, result=str)
    def t(self, text: str) -> str:
        import i18n

        return i18n.t(text)

    def retranslate(self) -> None:
        self.changed.emit()
