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

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QColor

import theme as T


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

    # ---------- шрифты ----------

    @Property(str, constant=True)
    def sans(self) -> str:
        return T.TK_SANS

    @Property(str, constant=True)
    def mono(self) -> str:
        return T.TK_MONO

    @Property(int, constant=True)
    def t2xs(self) -> int:
        return T.T_2XS

    @Property(int, constant=True)
    def tXs(self) -> int:
        return T.T_XS

    @Property(int, constant=True)
    def tSm(self) -> int:
        return T.T_SM

    @Property(int, constant=True)
    def tBase(self) -> int:
        return T.T_BASE

    @Property(int, constant=True)
    def tMd(self) -> int:
        return T.T_MD

    @Property(int, constant=True)
    def tLg(self) -> int:
        return T.T_LG

    @Property(int, constant=True)
    def tXl(self) -> int:
        return T.T_XL

    @Property(int, constant=True)
    def t3xl(self) -> int:
        return T.T_3XL

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
