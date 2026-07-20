// Календарь серии: клетка на день, полгода столбцами по неделям.
//
// Раскрывается нажатием на дугу серии («Статистика»). Дуга отвечает «сколько
// дней подряд», а этот вид - «как эти дни прожиты»: где густо, где пусто и где
// всё оборвалось. Одно число такого не покажет.
//
// ---- Про краски, и почему молчащий день не красный ----
//
// Владелец просил «как гитхаб: густо - тёмно-зелёный, ничего не говорил -
// красным, пассивным». Зелёная лестница здесь ровно такая, а вот молчащий день
// красным не заливается, и это не самоволие.
//
// В Korti красный - один и означает одно: ошибка, разрушительное действие. Им
// подсвечено «удалить историю» и им же горит строка, когда настройка не
// сохранилась. Залив им сто дней в календаре, мы сказали бы человеку, что сто
// раз что-то сломалось, - а он просто не диктовал в выходные. Слово
// «пассивным» в просьбе и есть настоящее требование: день молчания должен быть
// ТИХИМ, а не тревожным. Тихий здесь - чернила в семь процентов: клетка на
// месте, видно, что день был, и она не кричит.
//
// Данные зелёные, потому что зелёный в системе значит «получилось». Акцент
// (синий) не берём: он занят фокусом и «сегодня», и на нём же стоит дуга серии
// рядом. Сегодняшняя клетка отмечена тонкой акцентной рамкой - её ищут глазом
// первой.
//
// Насыщенность считает Python (stats.calendar): уровень 0..4 - доля от лучшего
// дня в окне, а не от круглого числа слов. Здесь только краски.

import { useEffect, useRef, useState, type MouseEvent } from "react";

import { cn } from "../cn";

export interface CalendarDay {
  /** 0..4. */
  level: number;
  today: boolean;
  future: boolean;
  /** «17 июля · 12 слов». Собрана в Python; у будущих дней пусто. */
  hint: string;
}

export interface CalendarMonth {
  /** «июл». */
  label: string;
  /** Номер столбца-недели, над которым стоит подпись. */
  col: number;
}

export interface StreakCalendarProps {
  /**
   * Клетки по датам, они же порядок обхода сетки сверху вниз, столбец за
   * столбцом. Порядок задан в Python и совпадает с раскладкой сетки - считать
   * индексы здесь не нужно.
   */
  days: CalendarDay[];
  /** Подписи месяцев над столбцами. */
  months: CalendarMonth[];
  /**
   * «пн»…«вс» - подписи строк. Приходят из stats, а не пишутся здесь: порядок
   * обязан совпадать с сеткой, и держать его в двух местах нельзя.
   */
  weekdays: string[];
  weeks?: number;
}

const GAP = 3;
const LABEL_W = 26;
const MONTHS_H = 16;
// Полоса под подсказку держится всегда, даже когда её не показывают, - иначе
// сетка подпрыгивала бы на каждое наведение мыши (как в недельном графике).
const TIP_BAND = 24;
// Клетка тянется за шириной колонки, но в разумных пределах: мельче восьми
// пикселей в неё не попасть мышью, крупнее шестнадцати она перестаёт читаться
// как сетка и становится плиткой.
const CELL_MIN = 8;
const CELL_MAX = 16;
// Скругление клетки - как у столбиков недельного графика, а не радиус из
// токенов: --radius-sm это шесть, то есть половина клетки, и квадратики
// превратились бы в кружки. Мелкая графика в системе живёт по этому же числу.
const CELL_RADIUS = 3;
// Четыре ступени зелёного. Верхняя - чистый success, ниже он же прозрачностью:
// своих красок не заводим, лестница считается от токена.
const LEVEL_ALPHA = [0, 0.28, 0.48, 0.72, 1];

function cellColor(level: number): string {
  if (level <= 0) return "color-mix(in srgb, var(--color-ink) 7%, transparent)";
  const a = LEVEL_ALPHA[Math.min(4, level)] ?? 1;
  return `color-mix(in srgb, var(--color-success) ${a * 100}%, transparent)`;
}

export function StreakCalendar({
  days,
  months,
  weekdays,
  weeks = 26,
}: StreakCalendarProps) {
  const grid = useRef<HTMLDivElement>(null);
  // Какая клетка под курсором. -1 - мышь ушла или наведена на пустое место.
  const [hovered, setHovered] = useState(-1);

  // Данные сменились - подсказка от прошлого наведения не должна их пережить.
  useEffect(() => setHovered(-1), [days]);

  const tip = hovered >= 0 ? (days[hovered] ?? null) : null;
  const tipCol = Math.floor(hovered / 7);

  // Одна мышь на всю сетку, а не сто восемьдесят обработчиков по клеткам:
  // индекс считается из координат, и промежутки между клетками при этом тоже
  // ведут к ближайшему дню - попадать в девять пикселей точно не нужно.
  function onMove(e: MouseEvent<HTMLDivElement>) {
    const box = grid.current;
    if (!box) return;
    const rect = box.getBoundingClientRect();
    // Шаг меряем от настоящей ширины: клетка тянется за окном, и своего числа
    // здесь быть не может. Клетка квадратная, поэтому шаг один на обе оси.
    const step = (rect.width + GAP) / weeks;
    if (step <= 0) return;
    const col = Math.floor((e.clientX - rect.left) / step);
    const row = Math.floor((e.clientY - rect.top) / step);
    const index = col * 7 + row;
    const inside =
      col >= 0 && col < weeks && row >= 0 && row < 7 && index < days.length;
    setHovered(inside ? index : -1);
  }

  return (
    <div
      role="img"
      aria-label="Календарь диктовок по дням"
      className="w-full"
      style={{ maxWidth: LABEL_W + weeks * CELL_MAX + (weeks - 1) * GAP }}
    >
      {/* ---- подсказка ---- */}
      <div
        className="relative"
        style={{ height: TIP_BAND, marginLeft: LABEL_W }}
      >
        {tip && tip.hint ? (
          <div
            className={cn(
              "absolute top-0 flex h-[20px] items-center rounded-sm bg-ink px-2",
              "font-sans text-2xs font-medium whitespace-nowrap text-bg",
            )}
            // По центру своего столбца, но не за краем сетки: у крайних недель
            // плашка шире клетки и иначе уезжала бы за карточку.
            style={
              tipCol <= 0
                ? { left: 0 }
                : tipCol >= weeks - 1
                  ? { right: 0 }
                  : {
                      left: `calc((100% + ${GAP}px) / ${weeks} * ${tipCol + 0.5} - ${GAP / 2}px)`,
                      transform: "translateX(-50%)",
                    }
            }
          >
            {tip.hint}
          </div>
        ) : null}
      </div>

      {/* ---- месяцы ---- */}
      <div
        className="relative"
        style={{ height: MONTHS_H, marginLeft: LABEL_W }}
      >
        {months.map((m) => (
          <span
            key={`${m.label}-${m.col}`}
            className="absolute top-0 font-sans text-2xs text-text-faint"
            style={{ left: `calc((100% + ${GAP}px) / ${weeks} * ${m.col})` }}
          >
            {m.label}
          </span>
        ))}
      </div>

      {/* ---- сетка ---- */}
      <div className="flex">
        {/* Подписи строк - через одну: семь надписей подряд при клетке в десять
            пикселей сливаются в серую полосу. «пн», «ср», «пт» хватает, чтобы
            понять, где верх недели и где выходные.

            Колонка растягивается по высоте сетки, а семь коробок делят её
            поровну - тем же числом строк и тем же зазором. Поэтому подписи
            стоят напротив своих рядов, не зная размера клетки. */}
        <div
          className="flex shrink-0 flex-col"
          style={{ width: LABEL_W, gap: GAP }}
        >
          {weekdays.map((w, i) => (
            <span
              key={`${w}-${i}`}
              className={cn(
                "flex flex-1 items-center font-sans text-2xs leading-none text-text-faint",
                i % 2 === 1 && "invisible",
              )}
            >
              {w}
            </span>
          ))}
        </div>

        <div
          ref={grid}
          className="grid min-w-0 flex-1"
          onMouseMove={onMove}
          onMouseLeave={() => setHovered(-1)}
          style={{
            // Столбец - это неделя, поэтому заполняем сверху вниз: порядок
            // клеток совпадает с порядком дат в days, и арифметики по индексам
            // не нужно вовсе.
            gridAutoFlow: "column",
            gridTemplateRows: "repeat(7, auto)",
            gridTemplateColumns: `repeat(${weeks}, minmax(${CELL_MIN}px, 1fr))`,
            gap: GAP,
          }}
        >
          {days.map((day, i) => (
            <div
              key={i}
              className={cn(
                "aspect-square transition-opacity duration-[var(--dur-fast)]",
                // Дни после сегодняшнего не рисуем вовсе. Даже пустая клетка в
                // завтра утверждала бы, что мы что-то знаем про завтра; место
                // при этом занято, и сетка не съезжает.
                day.future && "invisible",
              )}
              style={{
                borderRadius: CELL_RADIUS,
                background: cellColor(day.level),
                // Рамка обводкой, а не border: border забрал бы пиксель из
                // клетки, и сегодняшний день оказался бы мельче соседних.
                outline: day.today ? "1px solid var(--color-accent)" : undefined,
                // Под курсором клетка проявляется - отклик на наведение,
                // подсказка сверху его продолжение, а не единственный знак.
                opacity: hovered === i ? 0.75 : 1,
              }}
            />
          ))}
        </div>
      </div>

      {/* ---- лестница ---- */}
      <div className="flex items-center justify-end pt-1.5" style={{ gap: GAP }}>
        <span className="pr-1 font-sans text-2xs text-text-faint">тише</span>
        {LEVEL_ALPHA.map((_unused, level) => (
          <span
            key={level}
            className="block"
            style={{
              width: 12,
              height: 12,
              borderRadius: CELL_RADIUS,
              background: cellColor(level),
            }}
          />
        ))}
        <span className="pl-1 font-sans text-2xs text-text-faint">гуще</span>
      </div>
    </div>
  );
}
