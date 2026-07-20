// Неделя столбиками: «пн»…«вс», сегодня - акцентом, число - под курсором.
//
// ---- Почему неделя, а не тридцать дней ----
//
// Тридцать столбиков раньше и стояли. В окне 460 содержимому достаётся 420, за
// вычетом полей карточки графику остаётся 372 пикселя - это 12 пикселей на
// день. Подпись «пн» туда не влезает никакая, попасть мышью в такой столбик
// тоже нельзя. Получалась красивая полоска, по которой нельзя сказать даже,
// где вчера: график был, чтения не было. Семь дней дают 47 пикселей на
// столбик - хватает и на подпись, и на курсор.
//
// Данные - чернила, а не акцент: это данные, а не статус. Исключение одно -
// сегодняшний столбик: он отвечает на «а сегодня-то я сколько?», и глаз должен
// находить его без счёта слева направо.
//
// Рисуем div'ами. Библиотеку графиков сюда не тащат не из принципа, а по
// счёту: у всего приложения потолок 120 КБ gzip, а здесь семь прямоугольников
// и пунктирная линия. В QML тот же выбор делался по другой причине - Qt Graphs
// GPL-only и утянул бы весь проект в GPL.

import { useEffect, useState, type CSSProperties } from "react";

import { cn } from "../cn";
import { useAfterPaint } from "./metric";

export interface WeekDay {
  /** «пн»…«вс». */
  label: string;
  /** Слов за день. */
  value: number;
  today: boolean;
  /**
   * Готовая подсказка «16 июля · 12 слов». Собрана в Python: русское склонение
   * числительных живёт там (util.plural), и второй раз на JavaScript его
   * заводить нельзя - получится «1 слов».
   */
  hint: string;
}

export interface BarChartProps {
  days: WeekDay[];
  /**
   * Средние слова за день недели - линия-ориентир поверх столбцов. Число
   * считает Python (settings_qt._stats), здесь только рисуем. 0 - линии нет.
   */
  avg?: number;
  /** Высота всего графика вместе с полосой подсказки и подписями. */
  height?: number;
  className?: string;
}

const GAP = 6;
// Полоса под подсказку держится всегда, даже когда её не показывают. Иначе
// столбики подпрыгивали бы на каждое наведение мыши.
const TIP_BAND = 26;
// Подпись дня (18) плюс воздух между ней и столбиком (8). Держим одним числом:
// от низа этой коробки пляшет и основание столбцов, и средняя линия, поэтому
// расходиться им не на чем.
const LABEL_BAND = 26;
// Строка с числом над столбиком. Вычитается из высоты столбца, а не рисуется
// поверх: иначе рекордный день упирался бы числом в полосу подсказки.
const VALUE_LINE = 14;
// Потолок ширины столбика. Колонка тянется за окном, а столбик - нет: на
// колонке содержимого в 760 графику достаётся 712, это по 96 пикселей на день,
// и семь дней превращались в семь плит. Столбик шириной с ладонь перестаёт
// читаться как величина - глаз сравнивает высоты, а ширина только мешает.
const MAX_BAR = 56;

export function BarChart({
  days,
  avg = 0,
  height = 150,
  className,
}: BarChartProps) {
  const grown = useAfterPaint();
  const [hovered, setHovered] = useState(-1);

  // Данные сменились - подсказка от прошлого наведения не должна их пережить:
  // под курсором окажется другое число, а надпись осталась бы старой.
  useEffect(() => setHovered(-1), [days]);

  const n = days.length;
  const maxValue = Math.max(1, ...days.map((d) => d.value));
  const tip = hovered >= 0 ? (days[hovered] ?? null) : null;

  if (n === 0) {
    return (
      <div
        className={cn("flex items-center justify-center", className)}
        style={{ height }}
      >
        <span className="font-sans text-sm text-text-faint">пока пусто</span>
      </div>
    );
  }

  return (
    <div className={cn("flex w-full flex-col", className)} style={{ height }}>
      {/* ---- подсказка ----
          Чернильная плашка в полосе НАД столбиками, а не всплывающее окно
          поверх графика: у окна 420 пикселей ширины, и всплывашка накрыла бы
          половину недели. */}
      <div className="relative shrink-0" style={{ height: TIP_BAND }}>
        {tip && tip.hint ? (
          <div
            className={cn(
              "absolute top-0 flex h-[22px] items-center rounded-sm bg-ink px-2",
              "font-sans text-2xs font-medium whitespace-nowrap text-bg",
            )}
            style={tipPosition(hovered, n)}
          >
            {tip.hint}
          </div>
        ) : null}
      </div>

      {/* ---- столбцы ---- */}
      <div className="relative flex min-h-0 flex-1" style={{ gap: GAP }}>
        {/* Средняя линия недели - тонкий пунктир поверх столбцов. Пунктиром, а
            не сплошной: сплошная читается как ось графика, пунктир - как
            ориентир «вот ваш обычный день». Основание у неё то же, что у
            столбцов, поэтому совпадают они до пикселя. */}
        {avg > 0 ? (
          <div
            className="pointer-events-none absolute inset-x-0"
            style={{
              bottom: `calc((100% - ${VALUE_LINE}px) * ${clamp01(avg / maxValue)})`,
            }}
          >
            <div
              className="h-px w-full"
              style={{
                backgroundImage:
                  "repeating-linear-gradient(to right, var(--color-border-strong) 0 6px, transparent 6px 10px)",
              }}
            />
            {/* Подпись у ПРАВОГО конца линии, над ней, и с фоном карточки.
                Слева, как было, она печаталась поверх числа первого столбца:
                значение подписывается над столбиком, а столбик, близкий к
                среднему, - самый обычный случай, среднее ровно для этого и
                считают. «среднее» и «190» налезали друг на друга.

                Справа так не выходит: над линией у правого края пусто, потому
                что короткий столбец подписан ниже неё, а высокий - заметно
                выше. Фон карточки оставлен на случай плотных данных: пусть
                лучше подпись перекроет столбик, чем два текста смешаются в
                нечитаемое пятно.

                Ловится это только глазами. Ни tsc, ни axe, ни проверка ролей
                про наложение текста не знают ничего - разметка при этом
                совершенно правильная. */}
            <span
              className={cn(
                "absolute -top-1.5 right-0 bg-paper pl-1.5 font-sans",
                "text-2xs text-text-faint",
              )}
            >
              среднее
            </span>
          </div>
        ) : null}

        {days.map((day, i) => {
          const lit = hovered === i;
          // Рекордный день недели - самый высокий столбик. Ничья возможна:
          // подсветим оба, врать про «единственный» рекорд не станем.
          const record = day.value > 0 && day.value === maxValue;
          const frac = grown ? day.value / maxValue : 0;

          return (
            <div
              key={day.label + i}
              // Цель мыши - вся колонка, а не столбик. Попасть в двухпиксельную
              // ниточку пустого дня нельзя, а узнать, что в тот день было ровно
              // ноль, человек имеет право.
              className="flex h-full min-w-0 flex-1 flex-col items-center justify-end"
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered((prev) => (prev === i ? -1 : prev))}
            >
              {/* Число над столбиком - чтобы читать график, не наводя мышь.
                  Едет вместе с вершиной столбика, поэтому всплывает снизу вверх
                  заодно с ростом. Нулевой день числа не показывает - ниточка и
                  так говорит «здесь ноль». */}
              <span
                className={cn(
                  "flex shrink-0 items-end font-sans text-2xs tabular-nums",
                  day.today
                    ? "font-semibold text-accent"
                    : record
                      ? "font-semibold text-text"
                      : "text-text-muted",
                )}
                style={{ height: VALUE_LINE }}
              >
                {day.value > 0 ? day.value : ""}
              </span>

              <div
                className={cn(
                  "w-full rounded-[3px] transition-[height,opacity] ease-out",
                  day.today ? "bg-accent" : "bg-ink",
                )}
                style={{
                  maxWidth: MAX_BAR,
                  // Пустой день - ниточка, а не пустота: иначе не видно, что
                  // день вообще был. Она же служит начальным состоянием роста.
                  minHeight: 2,
                  height: `calc((100% - ${VALUE_LINE}px) * ${frac})`,
                  // Сегодня во всю силу, прочие дни вполголоса. Под курсором
                  // столбик дотягивается до полной непрозрачности: это и есть
                  // отклик на наведение, подсказка сверху - его продолжение, а
                  // не единственный признак. Рекорд недели тоже во всю силу -
                  // так он выделен и без акцента, который занят «сегодня»:
                  // сегодня синим, рекорд плотными чернилами.
                  opacity:
                    day.value > 0
                      ? day.today || lit || record
                        ? 1
                        : 0.72
                      : lit
                        ? 0.3
                        : 0.16,
                  transitionDuration: "var(--dur-slow)",
                  // Столбцы вырастают снизу волной слева направо. Шаг волны -
                  // треть быстрого токена, а не своё число: задержка тут часть
                  // того же движения и обязана ехать за токеном. К седьмому дню
                  // набегает 240 мс - под потолком системы; рост высоты не
                  // пружина, Korti это разрешает.
                  transitionDelay: `calc(var(--dur-fast) / 3 * ${i})`,
                }}
              />
            </div>
          );
        })}
      </div>

      {/* ---- подписи ----
          Текст прижат к низу коробки: так низ подписи стоит ровно на дне
          графика, а её верх - предсказуемо на LABEL_BAND выше. */}
      <div className="flex shrink-0" style={{ height: LABEL_BAND, gap: GAP }}>
        {days.map((day, i) => (
          <span
            key={day.label + i}
            className={cn(
              "flex min-w-0 flex-1 items-end justify-center font-sans text-2xs",
              day.today
                ? "font-semibold text-text"
                : hovered === i
                  ? "text-text-secondary"
                  : "text-text-muted",
            )}
          >
            {day.label}
          </span>
        ))}
      </div>

      {/* Мышью читают график, а диктору нужен тот же список словами. Подписи
          уже собраны в Python со склонением - просто отдаём их подряд. */}
      <span className="sr-only">
        {days.map((d) => d.hint).filter(Boolean).join(". ")}
      </span>
    </div>
  );
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

/**
 * Плашка по центру своего столбца, но не за краем графика.
 *
 * У «пн» и «вс» она шире колонки и иначе уезжала бы за карточку. В QML это
 * решал Math.min по измеренной ширине; здесь ширину мерить нечем и незачем -
 * крайние столбцы просто прижимают плашку к своему краю, а это ровно то, во
 * что вырождался тот Math.min.
 */
function tipPosition(index: number, count: number): CSSProperties {
  if (index <= 0) return { left: 0 };
  if (index >= count - 1) return { right: 0 };
  return {
    left: `calc((100% - ${GAP * (count - 1)}px) / ${count} * ${index + 0.5} + ${GAP * index}px)`,
    transform: "translateX(-50%)",
  };
}
