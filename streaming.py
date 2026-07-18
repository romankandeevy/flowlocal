"""Распознавать, пока человек ещё говорит.

Замысел владельца, и он верный. Раньше конвейер был строго последовательным:
человек договорил - и только тогда начинается работа. На пятнадцати минутах это
минута ожидания перед пустым экраном.

Но сказанное минуту назад уже не изменится. Его можно разбирать сразу, не дожидаясь
конца. Тогда после отпускания клавиши остаётся распознать только хвост - несколько
последних секунд, - и ожидание перестаёт зависеть от длины речи вообще.

Следствие, которое важнее самой скорости: **скорость модели перестаёт решать**.
Пока идёт речь, разница между моделью на 17 и на 38 «быстрее реального времени»
не видна никому - обе успевают за говорящим с большим запасом. Значит выбирать
модель можно по точности, а не по скорости. Спор «взять лёгкую и быструю» этим
и закрывается: брать надо точную.

Как режем. Только по паузам и только в уже сказанном:

    [-------- сказано --------][ ещё говорит ]
     ^^^^^^^^^^^^^^^^^^^ ищем паузу здесь
                        ^ режем, отдаём модели, забываем

Никогда не режем по счётчику времени: разрез посреди слова даёт две половинки,
которых модель не узнает ни ту, ни другую. Нет паузы - ждём, ничего страшного:
хвост доберём в конце.

Чего здесь НЕТ и не будет: показа текста по ходу речи. Это отдельная задача с
другими граблями (мигающий текст, который сам себя переписывает), и она не
нужна для скорости - ради которой всё и делается.
"""

import numpy as np

SAMPLE_RATE = 16000

# С какой длины берёмся разбирать на ходу.
#
# Было 12 секунд - и это обесценивало всю затею: обычная диктовка короче, то
# есть девять фраз из десяти уходили в хвост целиком и никакого разбора на ходу
# не видели. Оптимизация работала только там, где её и так почти не ждали.
#
# 5 секунд: при KEEP_TAIL_SEC = 1.8 остаётся больше трёх секунд, в которых
# можно искать паузу. Меньше делать нельзя - паузу негде будет искать.
MIN_TAIL_SEC = 5.0

# Хвост, который НЕ отдаём: человек в этот момент говорит, и последняя пауза
# может оказаться серединой фразы, а не её концом.
KEEP_TAIL_SEC = 1.8

# На слабой машине разбор на ходу отбирает процессор у микрофона, а потерянный
# звук хуже медленной работы. Там порог оставляем прежним: длинные диктовки
# всё равно выигрывают, а короткие не рискуют.
WEAK_CPU_CORES = 4
WEAK_MIN_TAIL_SEC = 12.0


def min_tail_sec(cfg: dict | None = None) -> float:
    """С какой длины берёмся за разбор на ходу. Читается из конфига."""
    import os

    if cfg is not None and cfg.get("stream_min_tail_sec"):
        return float(cfg["stream_min_tail_sec"])
    if (os.cpu_count() or 8) <= WEAK_CPU_CORES:
        return WEAK_MIN_TAIL_SEC
    return MIN_TAIL_SEC

# Окно поиска паузы и порог тишины.
_WIN_SEC = 0.2
# Порог берём от громкости самого куска, а не абсолютный: у одного микрофон
# шепчет, у другого фонит. Пауза - это место, где заметно тише, чем в среднем.
_QUIET_RATIO = 0.18

# Сколько отдаём модели за один заход. Больше - и отпускание клавиши будет
# ждать, пока она дожуёт начатое.
MAX_FEED_SEC = 20.0

# Упреждающий хвост.
#
# Человек замолкает раньше, чем отпускает клавишу: договорил, secunda на
# «всё ли сказал», и только потом палец уходит. Эти 200-500 мс сейчас пропадают
# впустую, хотя за них модель успевает разобрать весь остаток.
#
# Замечаем тишину в конце - разбираем остаток заранее. Отпустил, а нового
# звука с тех пор не было (только тишина) - готовый ответ уже лежит, и ждать
# нечего вовсе.
SPEC_SILENCE_SEC = 0.35      # столько тишины в конце считаем «договорил»
SPEC_MIN_GAP_SEC = 2.0       # не чаще раза в две секунды - лишние прогоны не нужны
SPEC_MAX_TAIL_SEC = 15.0     # длинный хвост спекулятивно не гоняем: дорого


def trailing_silence(audio: np.ndarray, sec: float = SPEC_SILENCE_SEC) -> bool:
    """Кончается ли кусок тишиной. Признак того, что человек договорил.

    Зеркало find_pause: та же мера громкости, только смотрим в самый конец.
    """
    win = int(_WIN_SEC * SAMPLE_RATE)
    need = int(sec * SAMPLE_RATE)
    if audio.size < need + win * 3:
        return False
    n = audio.size // win
    power = np.abs(audio[:n * win].reshape(n, win)).mean(axis=1)
    loud = float(power.mean())
    if loud <= 0:
        return False
    tail_wins = max(1, need // win)
    return bool(power[-tail_wins:].max() < loud * _QUIET_RATIO)


def find_pause(audio: np.ndarray) -> int | None:
    """Где разрезать, чтобы не попасть в середину слова. None - паузы нет.

    Ищем в пределах куска, но не ближе KEEP_TAIL_SEC к его концу.
    """
    win = int(_WIN_SEC * SAMPLE_RATE)
    keep = int(KEEP_TAIL_SEC * SAMPLE_RATE)
    usable = audio.size - keep
    if usable < win * 3:
        return None
    zone = audio[:usable]
    n = zone.size // win
    if n < 3:
        return None
    power = np.abs(zone[:n * win].reshape(n, win)).mean(axis=1)
    loud = float(power.mean())
    if loud <= 0:
        return None
    quiet = np.flatnonzero(power < loud * _QUIET_RATIO)
    if quiet.size == 0:
        return None
    # Берём САМУЮ ПОЗДНЮЮ паузу, а не самую тихую: чем больше отдадим модели
    # сейчас, тем меньше останется на конец, ради чего всё и затевалось.
    idx = int(quiet[-1])
    return idx * win + win // 2


class Stream:
    """Состояние потокового разбора одной диктовки.

    Живёт от нажатия до отпускания. Всё, что успели разобрать, лежит в parts;
    сколько образцов уже разобрано - в consumed. Конец диктовки дочитывает
    хвост с этой позиции и склеивает.
    """

    def __init__(self, transcribe, log, min_tail: float | None = None) -> None:
        self._transcribe = transcribe
        self._log = log
        self._min_tail = MIN_TAIL_SEC if min_tail is None else float(min_tail)
        self.parts: list[str] = []
        self.consumed = 0
        self.runs = 0
        self.waited_feed = False     # finish() ждал текущий кусок
        # Готовый ответ на хвост, разобранный заранее: (позиция, текст).
        self.spec: tuple[int, str] | None = None
        self.spec_hit = False
        self._spec_at = 0            # где спекулировали в прошлый раз

    def feed(self, audio: np.ndarray, total: int) -> bool:
        """Отдать модели то, что уже можно. True - что-то разобрали.

        audio - кусок начиная с self.consumed, total - сколько записано всего.
        """
        if audio.size < self._min_tail * SAMPLE_RATE:
            return False
        cut = find_pause(audio)
        if cut is None:
            return False
        # Кусок не длиннее MAX_FEED_SEC. Модель одна и считает по очереди:
        # отпустил клавишу, пока она жуёт сорокасекундный кусок, - и хвост
        # ждёт в очереди за ним. Режем по последней паузе внутри окна.
        limit = int(MAX_FEED_SEC * SAMPLE_RATE)
        if cut > limit:
            inner = find_pause(audio[:limit])
            cut = inner if inner is not None else limit
        piece = audio[:cut]
        text = str(self._transcribe(piece) or "").strip()
        self.consumed += cut
        self.runs += 1
        if text:
            self.parts.append(text)
        self._log(f"на ходу: разобрано {piece.size / SAMPLE_RATE:.0f} с, "
                  f"осталось {(total - self.consumed) / SAMPLE_RATE:.0f} с")
        return True

    def speculate(self, audio: np.ndarray, total: int) -> bool:
        """Разобрать остаток заранее, раз человек замолчал. True - разобрали.

        audio - остаток начиная с consumed. Результат кладём в spec вместе с
        позицией, на которой он снят: если человек заговорит снова, позиция
        перестанет совпадать и заготовка сама себя отменит.
        """
        if audio.size == 0 or audio.size > SPEC_MAX_TAIL_SEC * SAMPLE_RATE:
            return False
        if total - self._spec_at < SPEC_MIN_GAP_SEC * SAMPLE_RATE:
            return False
        if not trailing_silence(audio):
            return False
        self._spec_at = total
        self.spec = (total, str(self._transcribe(audio) or "").strip())
        return True

    def finish(self, tail: np.ndarray) -> str:
        """Дочитать хвост и склеить всё в одну речь.

        Если заготовка снята ровно на том же месте, где кончилась запись, -
        берём её и не считаем ничего. Это и есть выигрыш: пока человек
        собирался отпустить клавишу, работа уже сделана.
        """
        end = self.consumed + tail.size
        if self.spec is not None and self.spec[0] == end:
            self.spec_hit = True
            if self.spec[1]:
                self.parts.append(self.spec[1])
        elif tail.size >= SAMPLE_RATE // 20:
            text = str(self._transcribe(tail) or "").strip()
            if text:
                self.parts.append(text)
        return " ".join(p for p in self.parts if p).strip()
